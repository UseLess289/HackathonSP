"""Generate the fictitious demo data (DEMO-004/007).

Creates, under demo_data/:
- documents/cni_demo.pdf               (fake ID card, watermarked)
- documents/carte_vitale_demo.pdf     (fake health card, watermarked)
- documents/justificatif_domicile_demo.pdf (fake proof of address, watermarked)
- formulaire_demo.ods                 (empty template with named fields)

All data is fictitious and every PDF carries the watermark
`DOCUMENT FICTIF — DÉMONSTRATION`. Generated files are gitignored.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from .documents import WATERMARK
from .ods_form import create_template

DEMO_DIR = Path(__file__).resolve().parent.parent / "demo_data"
DOCS_DIR = DEMO_DIR / "documents"

FICTIVE_PERSON = {
    "nom": "DUPONT",
    "prenom": "Marie",
    "date_naissance": "12/03/1985",
    "lieu_naissance": "Lyon (69)",
    "adresse": "12 rue des Lilas, 75020 Paris",
    "nir": "2 85 03 75 123 456 78",
    "email": "marie.dupont@example.test",
}


def _pdf(path: Path, lines: list[str]) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(72, 800, WATERMARK)
    c.setFont("Helvetica", 12)
    y = 760
    for line in lines:
        c.drawString(72, y, line)
        y -= 22
    c.save()


def make_documents(out_dir: Path = DOCS_DIR) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = FICTIVE_PERSON
    files = []
    cni = out_dir / "cni_demo.pdf"
    _pdf(cni, [
        "RÉPUBLIQUE FRANÇAISE — CARTE NATIONALE D'IDENTITÉ (FICTIVE)",
        f"NOM : {p['nom']}",
        f"Prénom : {p['prenom']}",
        f"Date de naissance : {p['date_naissance']}",
        f"Lieu de naissance : {p['lieu_naissance']}",
        f"Adresse : {p['adresse']}",
    ])
    files.append(cni)

    cv = out_dir / "carte_vitale_demo.pdf"
    _pdf(cv, [
        "CARTE VITALE (FICTIVE)",
        f"Titulaire : {p['prenom']} {p['nom']}",
        f"NIR : {p['nir']}",
    ])
    files.append(cv)

    justif = out_dir / "justificatif_domicile_demo.pdf"
    _pdf(justif, [
        "JUSTIFICATIF DE DOMICILE (FICTIF) — facture d'électricité",
        f"Adresse : {p['adresse']}",
        "Titulaire : Marie DUPONT",
    ])
    files.append(justif)
    return files


def make_template(out_path: Path = DEMO_DIR / "formulaire_demo.ods") -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    create_template(out_path)
    return out_path


def main() -> None:
    docs = make_documents()
    tpl = make_template()
    print(f"Documents fictifs créés : {[d.name for d in docs]}")
    print(f"Modèle de formulaire créé : {tpl}")


if __name__ == "__main__":
    main()
