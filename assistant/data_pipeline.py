"""Data pipeline service exposed to Dev 1 (interface from dev2-data-services.md).

Single entry point combining the local document scan (DEMO-005) and the
normalization of personal data (DEMO-006). Extraction is 100% local
(pdftotext); only the normalized dict leaves this module, and only toward
the user-configured AI backend — never the raw PDFs.
"""

from __future__ import annotations

from pathlib import Path

from .documents import DocumentError, normalize_personal_data, scan_documents
from .models import PersonalData


def scan_and_extract_local_docs(docs_dir: Path) -> dict:
    """Scan the PDFs in `docs_dir` and return the identified fields.

    Returns a dict of normalized personal fields (nom, prenom,
    date_naissance, lieu_naissance, adresse, numero_securite_sociale,
    email, telephone) plus a "_sources" entry mapping each field to its
    source document name. Raises DocumentError with a readable message if
    a document is missing or unreadable (DEMO-005/016).
    """
    docs = scan_documents(Path(docs_dir))
    data: PersonalData = normalize_personal_data(docs)
    result = data.to_form_fields()
    result["_sources"] = dict(data.sources)  # type: ignore[assignment]
    return result
