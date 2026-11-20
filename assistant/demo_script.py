"""DEMO-017 — timed 90-second demo script.

Drives the full scenario automatically (the same turns a user would say),
printing each step with a timestamp so the presenter can follow along:

  1. vocal request (simulated here by text)
  2. local reading of the documents
  3. one missing-data question
  4. deterministic ODS form filling
  5. email draft recap
  6. explicit human confirmation
  7. send to the local test inbox
  8. result check in the mailbox

Usage:
    python -m assistant.smtp_sink        # terminal 2: local test inbox
    python -m assistant.demo_script      # terminal 1

Every step has a fallback message (DEMO-017 criterion): if something goes
wrong the script says so in plain language and stops without sending.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from .ai_backend import RuleBackend
from .orchestrator import STATE_LABELS, Orchestrator

ROOT = Path(__file__).resolve().parent.parent

STEPS = [
    "Présentation du profil utilisateur",
    "Demande : remplir le formulaire et envoyer par email",
    "Lecture locale des documents",
    "Question sur la donnée manquante (email)",
    "Remplissage du formulaire .ods",
    "Récapitulatif de l'email (destinataire + pièces jointes)",
    "Confirmation humaine explicite",
    "Envoi vers la boîte de test + vérification",
]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Scénario de démo chronométré (90 s).")
    parser.add_argument("--documents", default=str(ROOT / "demo_data" / "documents"))
    parser.add_argument("--template", default=str(ROOT / "demo_data" / "formulaire_demo.ods"))
    parser.add_argument("--out", default=str(ROOT / "demo_data"))
    parser.add_argument("--mailbox", default=str(ROOT / "demo_data" / "mailbox"))
    parser.add_argument("--recipient", default="demarche-accessibilite@prefecture.test")
    parser.add_argument("--smtp-host", default="127.0.0.1")
    parser.add_argument("--smtp-port", type=int, default=1025)
    args = parser.parse_args(argv)

    orch = Orchestrator(
        backend=RuleBackend(),
        documents_dir=Path(args.documents),
        template_path=Path(args.template),
        output_dir=Path(args.out),
        recipient=args.recipient,
        smtp_host=args.smtp_host,
        smtp_port=args.smtp_port,
    )
    mailbox = Path(args.mailbox)

    start = time.monotonic()

    def step(i: int, text: str) -> None:
        t = time.monotonic() - start
        print(f"\n[{t:5.1f}s] — Étape {i}/8 : {STEPS[i-1]}")
        print(f"  {text}")

    def turn(user: str) -> str:
        reply = orch.handle_user_input(user)
        print(f"  Vous > {user}")
        print(f"  Assistant > {reply}")
        print(f"  [état : {STATE_LABELS.get(orch.state, orch.state.value)}]")
        return reply

    print("=== Scénario de démo — 90 secondes ===")
    step(1, "Profil : accompagnement simple (FALC), une question à la fois.")
    step(2, "Demande de l'utilisateur.")
    turn("Remplis le formulaire avec ma CNI et ma carte Vitale, puis envoie-le par email.")
    step(3, "Les documents sont lus localement (aucun envoi de PDF).")
    step(4, "Réponse à la question manquante.")
    turn("marie.dupont@example.test")
    step(5, "Le formulaire .ods est rempli de façon déterministe.")
    step(6, "Récapitulatif avant envoi (garde-fou humain).")
    step(7, "Confirmation explicite « oui », puis envoi SMTP local.")
    turn("oui")
    step(8, "Vérification du message reçu dans la boîte de test.")
    emls = sorted(mailbox.glob("*.eml")) if mailbox.is_dir() else []
    if emls:
        print(f"  ✔ {len(emls)} message(s) dans {mailbox} : {[e.name for e in emls]}")
    else:
        print(f"  ✘ Aucun message dans {mailbox} — lancez `python -m assistant.smtp_sink`.")
    print(f"\nTerminé en {time.monotonic() - start:.1f}s.")


if __name__ == "__main__":
    main()
