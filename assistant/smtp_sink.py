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
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Boîte de test locale — démo</title>
<style>
  :root { --bg:#0E1116; --surface:#161B22; --border:#2A3340; --fg:#F5F7FA; --muted:#A9B1BE; --accent:#8FB3FF; --accent-ink:#0E1116; --ok:#3ED089; --bad:#FF7A7A; --focus:#F9F871; --radius:14px; --font:"DejaVu Sans","Noto Sans","Segoe UI",system-ui,sans-serif; }
  *{box-sizing:border-box;} body{margin:0;background:var(--bg);color:var(--fg);font-family:var(--font);line-height:1.55;padding:1.5rem 1rem;}
  .wrap{max-width:64rem;margin:0 auto;display:flex;flex-direction:column;gap:1.2rem;}
  .top{display:flex;align-items:center;gap:.8rem;flex-wrap:wrap;}
  .mark{width:2.2rem;height:2.2rem;border-radius:8px;background:linear-gradient(135deg,var(--accent),#ffffff22);display:grid;place-items:center;font-weight:900;color:var(--accent-ink);}
  h1{margin:0;font-size:1.3rem;font-weight:800;flex:1 1 12rem;}
  .badge{display:inline-flex;align-items:center;gap:.4rem;padding:.4rem .8rem;border-radius:999px;border:2px solid var(--ok);color:var(--ok);font-size:.85rem;font-weight:700;}
  .card{background:var(--surface);border:2px solid var(--border);border-radius:var(--radius);padding:1.1rem;}
  table{width:100%;border-collapse:separate;border-spacing:0 6px;}
  th{color:var(--muted);font-size:.85rem;text-align:left;padding:.4rem .7rem;font-weight:700;}
  td{background:var(--bg);padding:.7rem;border-top:1px solid var(--border);border-bottom:1px solid var(--border);}
  td:first-child{border-left:1px solid var(--border);border-radius:8px 0 0 8px;}
  td:last-child{border-right:1px solid var(--border);border-radius:0 8px 8px 0;}
  tr:hover td{background:#1a2029;}
  a{color:var(--accent);text-decoration:none;font-weight:700;}
  a:hover{text-decoration:underline;}
  .empty{color:var(--muted);text-align:center;padding:2rem 0;}
  .msg-title{margin:0 0 1rem 0;font-size:1.25rem;font-weight:800;}
  .kv{color:var(--muted);font-size:.9rem;margin:.25rem 0;}
  .kv b{color:var(--fg);}
  pre{background:var(--bg);border:2px solid var(--border);border-radius:8px;padding:1rem;white-space:pre-wrap;word-break:break-word;max-height:50vh;overflow:auto;}
  .attach{list-style:none;padding:0;margin:.5rem 0 0;}
  .attach li{padding:.6rem .8rem;border:1px solid var(--border);border-radius:8px;margin-bottom:.5rem;background:var(--bg);}
  .attach a{display:inline-flex;align-items:center;gap:.5rem;}
  .back{display:inline-block;margin-top:1rem;font-size:.9rem;}
  button:focus-visible,a:focus-visible{outline:4px solid var(--focus);outline-offset:3px;}
</style></head><body>
<div class="wrap">
  <div class="top">
    <div class="mark">M</div>
    <h1>Boîte de test locale — démo</h1>
    <span class="badge">✅ Aucun vrai email envoyé</span>
  </div>
{body}
</div></body></html>"""


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
        body = "<div class='card'><p class='empty'>Aucun message pour le moment. Envoyez un email depuis l'assistant pour le voir apparaître ici.</p></div>"
    else:
        body = ("<div class='card'><table><tr><th>Fichier</th><th>Objet</th><th>Destinataire</th>"
                "<th>Pièces jointes</th></tr>" + "".join(rows) + "</table></div>")
    return _PAGE.format(body=body)


def _view(out_dir: Path, name: str) -> tuple[str, dict]:
    f = out_dir / Path(name).name  # no path traversal
    if not f.is_file():
        return _PAGE.format(body="<div class='card'><p class='empty'>Message introuvable.</p><a class='back' href='/'>← retour à la liste</a></div>"), {"status": 404}
    msg = email.message_from_bytes(f.read_bytes(), policy=policy.default)
    body_text = ""
    b = msg.get_body(preferencelist=("plain",))
    if b:
        body_text = b.get_content()
    att_html = ""
    for i, part in enumerate(msg.iter_attachments()):
        fname = part.get_filename() or f"piece_{i}"
        att_html += (
            f"<li><a href='/attach/{f.name}/{i}'>⬇ {_esc(fname)}</a> "
            f"<span style='color:var(--muted);font-size:.8rem'>({ _esc(part.get_content_type())})</span></li>"
        )
    if not att_html:
        att_html = "<li style='color:var(--muted)'>Aucune pièce jointe.</li>"
    lines = [
        "<div class='card'>",
        f"<h1 class='msg-title'>{_esc(str(msg.get('Subject', '(sans objet)')))}</h1>",
        f"<p class='kv'><b>De :</b> {_esc(str(msg.get('From', '')))}</p>",
        f"<p class='kv'><b>À :</b> {_esc(str(msg.get('To', '')))}</p>",
        f"<pre>{_esc(body_text)}</pre>",
        "<h2 style='font-size:1rem;margin:1rem 0 .4rem'>Pièces jointes</h2>",
        f"<ul class='attach'>{att_html}</ul>",
        "<a class='back' href='/'>← retour à la liste</a>",
        "</div>",
    ]
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
