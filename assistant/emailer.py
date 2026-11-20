"""Email preparation and sending (DEMO-012/013/014).

The email is *prepared* (draft + recap) and only *sent* after the user
explicitly confirms (DEMO-013: `send_email` refuses to emit anything unless
`draft.user_confirmed` is True, set only by the orchestrator after a "oui").
Sending goes to a local test SMTP sink (aiosmtpd, Mailpit alternative) on
127.0.0.1:1025 — no real email is ever sent in the demo, and no credentials
are stored in git.
"""

from __future__ import annotations

import smtplib
import socket
from email.message import EmailMessage
from pathlib import Path

from .models import EmailDraft, PersonalData

DEFAULT_SINK_HOST = "127.0.0.1"
DEFAULT_SINK_PORT = 1025
# Fictitious prefecture address required by DEMO-012.
DEFAULT_RECIPIENT = "demarche-accessibilite@prefecture.test"


class EmailError(Exception):
    """User-facing error when the mail sink is unavailable (DEMO-016)."""


def build_subject(data: PersonalData | None = None) -> str:
    """DEMO-012: `Dépôt de dossier administratif — Marie DUPONT`."""
    if data and (data.prenom or data.nom):
        return f"Dépôt de dossier administratif — {data.prenom} {data.nom}".strip()
    return "Dépôt de dossier administratif (démo)"


def prepare_email(form_path: Path, attachments: list[Path],
                  recipient: str = DEFAULT_RECIPIENT,
                  data: PersonalData | None = None) -> EmailDraft:
    """Build the email draft WITHOUT sending it (DEMO-012).

    The draft contains an explanatory body, the filled form and the given
    attachments, plus a recap text usable by the UI (Dev 1). It is kept in
    memory only; nothing is sent here.
    """
    for att in [form_path, *attachments]:
        if not att.is_file():
            raise EmailError(f"Pièce jointe introuvable : {att.name}")
    person = f"{data.prenom} {data.nom}".strip() if data else ""
    body = (
        "Bonjour,\n\n"
        + (f"Veuillez trouver ci-joint le dossier administratif de {person}.\n\n" if person else
           "Veuillez trouver ci-joint le formulaire administratif rempli.\n\n")
        + "Pièces jointes : le formulaire rempli (.ods) et le justificatif de domicile.\n\n"
        "Ceci est un email de démonstration envoyé vers une boîte de test locale.\n"
    )
    draft = EmailDraft(
        to=recipient,
        subject=build_subject(data),
        body=body,
        form_path=str(form_path),
        attachments=[str(a) for a in attachments],
        user_confirmed=False,  # DEMO-013: never sent without explicit confirmation
    )
    return draft


def send_email(draft: EmailDraft, host: str = DEFAULT_SINK_HOST,
               port: int = DEFAULT_SINK_PORT) -> None:
    """Send the prepared email to the local test sink.

    DEMO-013: refuses formally if `draft.user_confirmed` is not explicitly
    True. Must only be called by the orchestrator AFTER the user answered
    "oui" to the recap.
    """
    if not draft.user_confirmed:
        raise EmailError("Envoi refusé : aucune confirmation explicite de l'utilisateur.")

    msg = EmailMessage()
    msg["From"] = "assistant@localhost"
    msg["To"] = draft.to
    msg["Subject"] = draft.subject
    msg.set_content(draft.body)

    form_path = Path(draft.form_path)
    msg.add_attachment(
        form_path.read_bytes(), maintype="application",
        subtype="vnd.oasis.opendocument.spreadsheet", filename=form_path.name,
    )
    for att in draft.attachments:
        p = Path(att)
        subtype = "pdf" if p.suffix.lower() == ".pdf" else "octet-stream"
        msg.add_attachment(p.read_bytes(), maintype="application",
                           subtype=subtype, filename=p.name)

    try:
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.send_message(msg)
    except (socket.error, smtplib.SMTPException) as exc:
        raise EmailError(
            "La boîte de test locale n'est pas disponible. "
            "Lancez `python -m assistant.smtp_sink` dans un autre terminal."
        ) from exc
