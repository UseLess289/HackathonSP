"""Entry points — accessible assistant (DEMO-001/002/016).

Two equivalent UIs:
- CLI (default, guaranteed keyboard-only fallback):
    python -m assistant.main
- Local accessible web UI (big buttons, optional voice, badges):
    python -m assistant.ui_server   then open http://127.0.0.1:8765

Voice is optional (Web Speech API in the browser); the keyboard path in the
CLI is always available. Run the local test inbox in another terminal:
    python -m assistant.smtp_sink
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .ai_backend import backend_from_env
from .models import Profile
from .orchestrator import STATE_LABELS, Orchestrator

ROOT = Path(__file__).resolve().parent.parent

PRIVACY_BADGE = {
    "local": "🔒 Traitement 100 % local",
    "cloud": "☁️ Échange chiffré avec le modèle IA",
    "neutral": "Assistant local",
}


def build_orchestrator(args: argparse.Namespace) -> Orchestrator:
    return Orchestrator(
        backend=backend_from_env(),
        documents_dir=Path(args.documents),
        template_path=Path(args.template),
        output_dir=Path(args.out),
        recipient=args.recipient,
        smtp_host=args.smtp_host,
        smtp_port=args.smtp_port,
        profile=Profile(args.profil),
    )


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--documents", default=str(ROOT / "demo_data" / "documents"))
    parser.add_argument("--template", default=str(ROOT / "demo_data" / "formulaire_demo.ods"))
    parser.add_argument("--out", default=str(ROOT / "demo_data"))
    parser.add_argument("--recipient", default="demarche-accessibilite@prefecture.test")
    parser.add_argument("--smtp-host", default="127.0.0.1")
    parser.add_argument("--smtp-port", type=int, default=1025)
    parser.add_argument("--profil", choices=[p.value for p in Profile],
                        default=Profile.SIMPLE.value,
                        help="profil d'accompagnement : simple (FALC) ou standard")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Assistant d'accessibilité (démo, mode clavier).")
    parser.add_argument("--ui", choices=("cli", "web"), default="web",
                        help="cli = terminal clavier (secours garanti) ; web = interface locale http://127.0.0.1:8765")
    parser.add_argument("--port", type=int, default=8765, help="port de l'interface web")
    add_common_args(parser)
    args = parser.parse_args(argv)

    if args.ui == "web":
        from . import ui_server
        ui_server.main([
            "--host", "127.0.0.1", "--port", str(args.port),
            "--documents", args.documents, "--template", args.template,
            "--out", args.out, "--recipient", args.recipient,
            "--smtp-host", args.smtp_host, "--smtp-port", str(args.smtp_port),
        ])
        return

    orch = build_orchestrator(args)
    print("=== Assistant d'accessibilité — démo (mode clavier) ===")
    print("Tapez votre demande (ex. : « Remplis le formulaire avec ma CNI et ma carte Vitale »).")
    print("Commandes : 'aide', 'recommencer', 'retour', 'annuler', 'profil simple', 'profil standard', 'quitter'.")
    print("L'envoi d'email demandera toujours une confirmation explicite.\n")

    while True:
        try:
            user_input = input("Vous > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAu revoir.")
            break
        if not user_input:
            continue
        if user_input.lower() in ("quitter", "exit", "quit"):
            print("Au revoir.")
            break
        reply = orch.handle_user_input(user_input)
        print(f"[{PRIVACY_BADGE.get(orch.privacy.value, '')}] [état : {STATE_LABELS.get(orch.state, orch.state.value)}]")
        print(f"Assistant > {reply}\n")


if __name__ == "__main__":
    main()
