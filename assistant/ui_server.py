"""Local web UI server for the accessible assistant (DEMO-002/015/016).

Serves a single local HTML page on 127.0.0.1 only (never on the network) and
exposes one JSON endpoint (/api/turn) that forwards user turns to the
Orchestrator. The page has:
- a big push-to-talk "Parler" button (voice is OPTIONAL, Web Speech API);
- a full keyboard fallback (text field + Confirmer/Annuler/Réessayer buttons,
  Tab/Enter/Escape navigation, visible focus, high contrast, ARIA live regions);
- a large-text transcript of the voice transcription and assistant replies;
- a live state indicator and a privacy badge (🔒 local / ☁️ cloud, DEMO-015).

Usage:
    python -m assistant.ui_server [--port 8765]
then open http://127.0.0.1:8765 in a browser.
The CLI in assistant.main remains the guaranteed keyboard-only fallback.
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .ai_backend import backend_from_env
from .emailer import DEFAULT_RECIPIENT
from .models import Profile
from .orchestrator import STATE_LABELS, Orchestrator

ROOT = Path(__file__).resolve().parent.parent
UI_DIR = Path(__file__).resolve().parent / "ui"


def build_orchestrator(args: argparse.Namespace) -> Orchestrator:
    return Orchestrator(
        backend=backend_from_env(),
        documents_dir=Path(args.documents),
        template_path=Path(args.template),
        output_dir=Path(args.out),
        recipient=args.recipient,
        smtp_host=args.smtp_host,
        smtp_port=args.smtp_port,
        profile=Profile(getattr(args, "profil", Profile.SIMPLE.value)),
    )


def make_handler(orch: Orchestrator):
    class UIHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # keep the demo screen clean
            pass

        def _send_json(self, obj: dict, status: int = 200) -> None:
            body = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path in ("/", "/index.html"):
                body = (UI_DIR / "index.html").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if path != "/api/turn":
                self.send_response(404)
                self.end_headers()
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length) or b"{}")
                text = str(payload.get("text", ""))
                reply = orch.handle_user_input(text)
                self._send_json({
                    "reply": reply,
                    "state": orch.state.value,
                    "state_label": STATE_LABELS.get(orch.state, orch.state.value),
                    "privacy": orch.privacy.value,
                })
            except Exception:
                # DEMO-016: user-facing JSON error, never a traceback.
                self._send_json({"reply": "Un problème est arrivé. Tapez « recommencer ».",
                                 "state": orch.state.value,
                                 "state_label": STATE_LABELS.get(orch.state, orch.state.value),
                                 "privacy": orch.privacy.value}, status=200)

    return UIHandler


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Interface web locale et accessible de l'assistant (démo).")
    parser.add_argument("--host", default="127.0.0.1",
                        help="hôte d'écoute (toujours 127.0.0.1, jamais le réseau)")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--documents", default=str(ROOT / "demo_data" / "documents"))
    parser.add_argument("--template", default=str(ROOT / "demo_data" / "formulaire_demo.ods"))
    parser.add_argument("--out", default=str(ROOT / "demo_data"))
    parser.add_argument("--recipient", default=DEFAULT_RECIPIENT)
    parser.add_argument("--smtp-host", default="127.0.0.1")
    parser.add_argument("--smtp-port", type=int, default=1025)
    parser.add_argument("--profil", choices=[p.value for p in Profile],
                        default=Profile.SIMPLE.value)
    args = parser.parse_args(argv)

    orch = build_orchestrator(args)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(orch))
    print(f"Interface accessible ouverte sur http://{args.host}:{args.port}")
    print("(écoute uniquement en local — Ctrl+C pour arrêter)")
    print("Lancez aussi la boîte de test : python -m assistant.smtp_sink")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt.")
        server.shutdown()


if __name__ == "__main__":
    main()
