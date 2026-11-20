"""Local test mail sink — Mailpit/MailHog alternative (DEMO-014).

Run:  python -m assistant.smtp_sink [--port 1025] [--web-port 8025] [--out demo_data/mailbox]

SMTP on 127.0.0.1:1025: every received email is stored as an .eml file.
Web UI on http://127.0.0.1:8025 (Mailpit-style): list messages, view one,
download its attachments (.ods, .pdf). Everything stays on the machine:
no real email is ever sent, nothing leaves localhost.
"""

from __future__ import annotations

import argparse
import email
from email import policy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from aiosmtpd.controller import Controller


class MailSink:
    """aiosmtpd handler: stores every received message as an .eml file."""

    def __init__(self, out_dir: Path):
        self.out_dir = out_dir

    async def handle_DATA(self, server, session, envelope):
        self.out_dir.mkdir(parents=True, exist_ok=True)
        n = len(list(self.out_dir.glob("*.eml"))) + 1
        path = self.out_dir / f"message_{n:03d}.eml"
        path.write_bytes(envelope.content)
        print(f"[mail-sink] message reçu -> {path} "
              f"(destinataire: {envelope.rcpt_tos})")
        return "250 OK"


# --------------------------------------------------------------------- web UI
_PAGE = """<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<title>Boîte de test locale (démo)</title>
<style>
body{{font-family:sans-serif;margin:2em;max-width:60em}}
h1{{font-size:1.3em}}
table{{border-collapse:collapse}} td,th{{border:1px solid #ccc;padding:.3em .8em;text-align:left}}
.att{{margin-left:1em}}
</style></head><body>
<h1>Boîte de test locale — démo (aucun vrai email n'est envoyé)</h1>
{body}
</body></html>"""


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _index(out_dir: Path) -> str:
    rows = []
    for f in sorted(out_dir.glob("*.eml")):
        try:
            msg = email.message_from_bytes(f.read_bytes(), policy=policy.default)
            subj = _esc(str(msg.get("Subject", "(sans objet)")))
            to = _esc(str(msg.get("To", "")))
            att = sum(1 for _ in msg.iter_attachments())
            rows.append(
                f"<tr><td><a href='/view/{f.name}'>{f.name}</a></td>"
                f"<td>{subj}</td><td>{to}</td><td>{att} pièce(s) jointe(s)</td></tr>"
            )
        except Exception:
            rows.append(f"<tr><td><a href='/view/{f.name}'>{f.name}</a></td><td colspan='3'>illisible</td></tr>")
    if not rows:
        body = "<p>Aucun message pour le moment.</p>"
    else:
        body = ("<table><tr><th>Fichier</th><th>Objet</th><th>Destinataire</th>"
                "<th>Pièces jointes</th></tr>" + "".join(rows) + "</table>")
    return _PAGE.format(body=body)


def _view(out_dir: Path, name: str) -> tuple[str, dict]:
    f = out_dir / Path(name).name  # no path traversal
    if not f.is_file():
        return _PAGE.format(body="<p>Message introuvable.</p>"), {"status": 404}
    msg = email.message_from_bytes(f.read_bytes(), policy=policy.default)
    lines = [
        f"<h1>{_esc(str(msg.get('Subject', '(sans objet)')))}</h1>",
        f"<p><b>De :</b> {_esc(str(msg.get('From', '')))}<br>"
        f"<b>À :</b> {_esc(str(msg.get('To', '')))}</p>",
        "<hr><pre>" + _esc(msg.get_body(preferencelist=("plain",)).get_content()
                           if msg.get_body(preferencelist=("plain",)) else "") + "</pre>",
        "<h2>Pièces jointes</h2><ul>",
    ]
    for i, part in enumerate(msg.iter_attachments()):
        fname = part.get_filename() or f"piece_{i}"
        lines.append(
            f"<li class='att'><a href='/attach/{f.name}/{i}'>{_esc(fname)}</a> "
            f"({_esc(part.get_content_type())})</li>"
        )
    lines.append("</ul><p><a href='/'>← retour à la liste</a></p>")
    return _PAGE.format(body="".join(lines)), {}


def _attachment(out_dir: Path, name: str, index: str):
    f = out_dir / Path(name).name
    if not f.is_file():
        return None, None, {"status": 404}
    msg = email.message_from_bytes(f.read_bytes(), policy=policy.default)
    parts = list(msg.iter_attachments())
    try:
        part = parts[int(index)]
    except (ValueError, IndexError):
        return None, None, {"status": 404}
    payload = part.get_payload(decode=True) or b""
    return payload, part.get_filename() or "piece_jointe", {}


class _Handler(BaseHTTPRequestHandler):
    out_dir: Path  # set by make_web_server

    def log_message(self, *args):  # keep the terminal quiet
        pass

    def _send(self, body: str, status: int = 200, ctype: str = "text/html; charset=utf-8"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path in ("/", "/index.html"):
            self._send(_index(self.out_dir))
        elif path.startswith("/view/"):
            body, extra = _view(self.out_dir, unquote(path[len("/view/"):]))
            self._send(body, extra.get("status", 200))
        elif path.startswith("/attach/"):
            rest = unquote(path[len("/attach/"):]).split("/", 1)
            payload, fname, extra = _attachment(self.out_dir, rest[0], rest[1] if len(rest) > 1 else "0")
            if payload is None:
                self._send(_PAGE.format(body="<p>Pièce jointe introuvable.</p>"), extra.get("status", 404))
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        else:
            self._send(_PAGE.format(body="<p>Page introuvable.</p>"), 404)


def make_web_server(out_dir: Path, host: str, port: int) -> ThreadingHTTPServer:
    """Mailpit-style web UI bound to localhost only (DEMO-014)."""
    handler = type("BoundHandler", (_Handler,), {"out_dir": out_dir})
    return ThreadingHTTPServer((host, port), handler)


# ------------------------------------------------------------------------ main
def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Local test SMTP sink (démo).")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1025)
    parser.add_argument("--web-port", type=int, default=8025)
    parser.add_argument("--out", default="demo_data/mailbox")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    controller = Controller(MailSink(out_dir), hostname=args.host, port=args.port)
    controller.start()
    print(f"[mail-sink] SMTP sur {args.host}:{args.port} — emails sauvés dans {out_dir}/")

    web = None
    try:
        web = make_web_server(out_dir, args.host, args.web_port)
        import threading
        t = threading.Thread(target=web.serve_forever, daemon=True)
        t.start()
        print(f"[mail-sink] interface web : http://{args.host}:{args.web_port} "
              "(pièces jointes téléchargeables)")
    except OSError as exc:
        print(f"[mail-sink] interface web indisponible sur le port {args.web_port} ({exc}) — mode SMTP seul.")

    print("[mail-sink] Ctrl+C pour arrêter.")
    try:
        import time
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        controller.stop()
        if web is not None:
            web.shutdown()
        print("\n[mail-sink] arrêté.")


if __name__ == "__main__":
    main()
