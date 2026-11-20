"""Deterministic filling of the demo ODS form (DEMO-007/008).

The form uses FIXED target cells (DEMO-007): each field has a stable cell
(Nom B3, Prénom B4, ... Téléphone B10). We write values directly into those
cells with odfpy — we never drive LibreOffice by clicking. The output file
is created separately from the template, which stays intact. Missing
REQUIRED data blocks the workflow instead of being invented.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from odf.opendocument import load
from odf.table import Table, TableRow, TableCell
from odf.text import P

from .models import FORM_CELLS, FORM_FIELDS, PersonalData

# Row layout of the template sheet "Formulaire":
#   row 1: title, row 2: headers, rows 3..10: fields (cell B<row> per FORM_CELLS),
#   row 12: status row.
_TITLE_ROW = 1
_HEADER_ROW = 2
_STATUS_ROW = 12

# field -> row number, derived from the fixed cells (B3 -> row 3, ...).
_FIELD_ROWS = {field: int(cell[1:]) for field, cell in FORM_CELLS.items()}
# In insertion order of the form: nom, prenom, date_naissance, lieu_naissance,
# adresse, numero_securite_sociale, email, telephone.
_FORM_ORDER = sorted(_FIELD_ROWS, key=lambda f: _FIELD_ROWS[f])


class FormError(Exception):
    """User-facing error when the form cannot be written (DEMO-016)."""


def _cell(text: str = "") -> TableCell:
    c = TableCell()
    if text:
        c.addElement(P(text=text))
    return c


def _row(cells: int, values: list[str]) -> TableRow:
    row = TableRow()
    for i in range(cells):
        row.addElement(_cell(values[i] if i < len(values) else ""))
    return row


def create_template(template_path: Path) -> None:
    """Create the empty demo form with fixed target cells (DEMO-007).

    Row 1: title. Row 2: column headers (Champ / Valeur). Rows 3-10: one
    labelled field per row, value cell in column B. Row 12: status.
    """
    from odf.opendocument import OpenDocumentSpreadsheet

    doc = OpenDocumentSpreadsheet()
    table = Table(name="Formulaire")
    table.addElement(_row(2, ["Formulaire administratif (démo fictive)"]))
    table.addElement(_row(2, ["Champ", "Valeur"]))
    for field_id in _FORM_ORDER:
        table.addElement(_row(2, [FORM_FIELDS[field_id], ""]))
    # rows 11 left blank, row 12 = status
    table.addElement(_row(2, [""]))
    table.addElement(_row(2, ["Statut", ""]))
    doc.spreadsheet.addElement(table)
    doc.save(str(template_path))


def _set_cell_value(cell: TableCell, value: str) -> None:
    for p in cell.getElementsByType(P):
        cell.removeChild(p)
    cell.addElement(P(text=value))


def _cell_text(cell: TableCell) -> str:
    ps = cell.getElementsByType(P)
    return str(ps[0]) if ps else ""


def fill_form(template_path: Path, output_path: Path, data: PersonalData) -> Path:
    """Write `data` into a copy of the template at the fixed cells (DEMO-008).

    Missing REQUIRED fields raise FormError (the workflow must ask the user
    instead of inventing data). The template itself is never modified.
    """
    missing = data.missing_fields()
    if missing:
        from .models import REQUIRED_FIELDS
        labels = ", ".join(REQUIRED_FIELDS[f] for f in missing)
        raise FormError(f"Donnée manquante, impossible de remplir le formulaire : {labels}")
    if not template_path.is_file():
        raise FormError(f"Modèle de formulaire introuvable : {template_path}")

    shutil.copy(template_path, output_path)
    doc = load(str(output_path))
    values = data.to_form_fields()
    for table in doc.spreadsheet.getElementsByType(Table):
        if table.getAttribute("name") != "Formulaire":
            continue
        rows = table.getElementsByType(TableRow)
        for field_id, row_number in _FIELD_ROWS.items():
            if row_number > len(rows):
                raise FormError(f"Ligne {row_number} absente du modèle (cellule {FORM_CELLS[field_id]})")
            cells = rows[row_number - 1].getElementsByType(TableCell)
            if len(cells) < 2:
                raise FormError(f"Cellule {FORM_CELLS[field_id]} absente du modèle")
            _set_cell_value(cells[1], values[field_id])  # column B
        if _STATUS_ROW <= len(rows):
            cells = rows[_STATUS_ROW - 1].getElementsByType(TableCell)
            if len(cells) >= 2:
                _set_cell_value(cells[1], "REMPLI — en attente de confirmation avant envoi")
    doc.save(str(output_path))
    return output_path


def read_form_values(path: Path) -> dict[str, str]:
    """Read back field values from the fixed cells (DEMO-008: values are
    re-read and verified right after writing)."""
    doc = load(str(path))
    values: dict[str, str] = {}
    for table in doc.spreadsheet.getElementsByType(Table):
        rows = table.getElementsByType(TableRow)
        for field_id, row_number in _FIELD_ROWS.items():
            if row_number > len(rows):
                continue
            cells = rows[row_number - 1].getElementsByType(TableCell)
            if len(cells) >= 2:
                values[field_id] = _cell_text(cells[1])
        if _STATUS_ROW <= len(rows):
            cells = rows[_STATUS_ROW - 1].getElementsByType(TableCell)
            if len(cells) >= 2:
                values["statut"] = _cell_text(cells[1])
    return values
