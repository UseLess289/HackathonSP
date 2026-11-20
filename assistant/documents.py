"""Local scanning of demo documents (DEMO-004/005/006).

Text extraction is done **locally** with pdftotext. The full PDF is never
sent anywhere; only normalized fields are used afterwards. Documents are
classified by filename keywords and must be marked as fictitious.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .models import PersonalData

WATERMARK = "DOCUMENT FICTIF — DÉMONSTRATION"

# Document types recognized by filename keyword (lowercase).
DOC_TYPES = {
    "cni_demo": "cni",
    "carte_vitale_demo": "carte_vitale",
    "justificatif_domicile_demo": "justificatif_domicile",
}


@dataclass
class ScannedDocument:
    path: Path
    doc_type: str
    text: str
    fictitious: bool


class DocumentError(Exception):
    """User-facing error: missing or unreadable document (DEMO-016)."""


def extract_text(pdf_path: Path) -> str:
    """Extract text from a PDF locally via pdftotext (poppler-utils)."""
    if not pdf_path.is_file():
        raise DocumentError(f"Document introuvable : {pdf_path.name}")
    try:
        proc = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            capture_output=True, text=True, timeout=30, check=True,
        )
    except FileNotFoundError as exc:
        raise DocumentError("Outil 'pdftotext' introuvable (installer poppler-utils).") from exc
    except subprocess.CalledProcessError as exc:
        raise DocumentError(f"Impossible de lire le document : {pdf_path.name}") from exc
    text = proc.stdout.strip()
    if not text:
        raise DocumentError(f"Le document semble vide ou scanné (pas de texte) : {pdf_path.name}")
    return text


def classify(path: Path) -> str:
    name = path.name.lower()
    for keyword, doc_type in DOC_TYPES.items():
        if keyword in name:
            return doc_type
    return "inconnu"


def scan_documents(directory: Path) -> list[ScannedDocument]:
    """Scan every PDF in `directory`, extract text locally, check the watermark."""
    if not directory.is_dir():
        raise DocumentError(f"Dossier de documents introuvable : {directory}")
    pdfs = sorted(directory.glob("*.pdf"))
    if not pdfs:
        raise DocumentError(f"Aucun PDF trouvé dans {directory}")
    docs: list[ScannedDocument] = []
    for pdf in pdfs:
        text = extract_text(pdf)
        fictitious = WATERMARK in text
        docs.append(ScannedDocument(path=pdf, doc_type=classify(pdf), text=text,
                                    fictitious=fictitious))
    return docs


def _find(pattern: str, text: str) -> str:
    m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    return m.group(1).strip() if m else ""


DATE_RE = re.compile(r"\d{2}/\d{2}/\d{4}")


def _valid_date(value: str) -> bool:
    """Basic format validation for a birth date (DEMO-006)."""
    return bool(DATE_RE.fullmatch(value.strip()))


def _valid_nir(value: str) -> bool:
    """Basic format validation: a NIR is exactly 15 digits after removing
    spaces (DEMO-006)."""
    digits = re.sub(r"\s+", "", value)
    return len(digits) == 15 and digits.isdigit()


def normalize_personal_data(docs: list[ScannedDocument]) -> PersonalData:
    """Build structured personal data from scanned documents (DEMO-006).

    Each field keeps a reference to its source document. Values are never
    invented: missing values stay empty and will be asked later. Extracted
    values are validated against simple formats (date, NIR length); an
    invalid value is dropped (left empty) so it gets asked instead.
    """
    data = PersonalData()
    for doc in docs:
        t = doc.text
        if doc.doc_type == "cni" or (data.nom == "" and "NOM" in t.upper()):
            nom = _find(r"NOM\s*:\s*(.+)", t)
            prenom = _find(r"Pr[ée]nom\s*:\s*(.+)", t)
            ddn = _find(r"Date de naissance\s*:\s*(.+)", t)
            lieu = _find(r"Lieu de naissance\s*:\s*(.+)", t)
            if nom:
                data.nom = nom
                data.sources["nom"] = doc.path.name
            if prenom:
                data.prenom = prenom
                data.sources["prenom"] = doc.path.name
            if ddn and _valid_date(ddn):
                data.date_naissance = ddn
                data.sources["date_naissance"] = doc.path.name
            if lieu:
                data.lieu_naissance = lieu
                data.sources["lieu_naissance"] = doc.path.name
        if doc.doc_type == "carte_vitale" or "sécurité sociale" in t.lower():
            nir = _find(r"(?:NIR|Numéro de sécurité sociale)\s*:\s*([0-9][0-9 ]*[0-9])", t)
            if nir:
                digits = re.sub(r"\s+", "", nir)
                if _valid_nir(digits):
                    data.numero_securite_sociale = digits
                    data.sources["numero_securite_sociale"] = doc.path.name
        if doc.doc_type == "justificatif_domicile" or "adresse" in t.lower():
            adr = _find(r"Adresse\s*:\s*(.+)", t)
            if adr:
                data.adresse = adr
                data.sources["adresse"] = doc.path.name
    return data
