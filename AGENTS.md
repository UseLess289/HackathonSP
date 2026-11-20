# AGENTS.md — Compagnon Linux accessible (HackathonSP)

## 1. Demo constraints (hard rules, never break)

- Use **only fictitious documents**, watermarked `DOCUMENT FICTIF — DÉMONSTRATION`.
- Never commit or use a real CNI, carte Vitale, or any real personal data.
- Never store email credentials or API keys in git, logs, or `.env` committed files.
- Never send an email (or any sensitive action) **without explicit user confirmation**.
- The keyboard-only fallback path must always work (voice is optional).
- Generated files under `demo_data/documents/` and `demo_data/mailbox/` are gitignored.

## 2. Privacy / ZDR (zéro rétention de données)

- Document text extraction (pdftotext) happens **locally**; full PDFs are never sent to any cloud/LLM.
- Only normalized fields (name, birth date, address, NIR, email) may leave the machine, and only to the user-configured AI provider.
- No API key, prompt, or personal data in logs. Sensitive fields are never printed in logs.

## 3. Architecture

- The product app is a **separate entry point** from `anthony-mcp` (we do not modify anthony code here).
- ODS form filling is **deterministic** via `odfpy` (write into known cells). Never drive LibreOffice by visual clicking.
- Workflow is an explicit **state machine** (see `assistant/models.py`); the current state is always visible to the user.
- LLM actions are restricted to a **validated JSON contract**: `read_documents`, `ask_question`, `fill_form`, `prepare_email`, `request_confirmation`, `send_email`, `cancel`. Unknown types are rejected. `send_email` is impossible before `request_confirmation` + user confirmation.
- AI calls go through the `AIBackend` interface (`assistant/ai_backend.py`); a deterministic offline backend guarantees demo reliability.

## 4. Stack & layout

- Python 3.11+, package `assistant/` at repo root, deps: `odfpy`, `reportlab`, `aiosmtpd` (see `pyproject.toml`, venv in `.venv/`).
- Fake demo PDFs + ODS template: `assistant/make_demo_data.py` → `demo_data/`.
- Local mail sink (Mailpit alternative): `python -m assistant.smtp_sink` on port 1025.
- User-facing strings in **French, simple language** (FALC: one question at a time, short sentences). Code and comments in English.

## 5. Working style

- Semantic commit prefixes: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`.
- Never push to `main`; use a feature branch. Show the diff before committing.
- Tests: `python -m unittest discover -s tests` (the full demo scenario must pass 3x consecutively).
