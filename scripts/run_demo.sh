#!/usr/bin/env bash
# run_demo.sh — lance la démo complète en une commande.
#
#   ./scripts/run_demo.sh            # assistant en mode clavier + boîte de test
#   ./scripts/run_demo.sh web        # assistant en interface web (127.0.0.1:8765)
#   ./scripts/run_demo.sh script     # scénario chronométré 90 s (DEMO-017)
#   ./scripts/run_demo.sh test       # lance uniquement les tests
#
# Le script : crée le venv si besoin, installe le projet, génère les données
# fictives, démarre la boîte email de test (SMTP :1025 + UI http://127.0.0.1:8025)
# en arrière-plan, puis lance l'assistant. La boîte de test est arrêtée à la fin.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODE="${1:-cli}"
SMTP_PORT="${SMTP_PORT:-1025}"
WEB_PORT="${WEB_PORT:-8025}"
UI_PORT="${UI_PORT:-8765}"

PY="$ROOT/.venv/bin/python"

log() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }

# --- 1. environnement virtuel ---------------------------------------------
if [ ! -x "$PY" ]; then
    log "Création du venv (.venv)..."
    python3 -m venv .venv
fi
if [ ! -f "$ROOT/.venv/.deps_ok" ]; then
    log "Installation des dépendances..."
    "$PY" -m pip install -q -e .
    touch "$ROOT/.venv/.deps_ok"
fi

# --- 2. données fictives ----------------------------------------------------
if [ ! -f "$ROOT/demo_data/formulaire_demo.ods" ] || [ -z "$(ls "$ROOT/demo_data/documents"/*.pdf 2>/dev/null)" ]; then
    log "Génération des documents fictifs filigranés..."
    "$PY" -m assistant.make_demo_data
fi

# --- 3. tests uniquement -----------------------------------------------------
if [ "$MODE" = "test" ]; then
    log "Lancement des tests (scénario rejoué 3x)..."
    exec "$PY" -m unittest discover -s tests -v
fi

# --- 4. boîte email de test en arrière-plan ---------------------------------
cleanup() {
    if [ -n "${SINK_PID:-}" ] && kill -0 "$SINK_PID" 2>/dev/null; then
        log "Arrêt de la boîte de test..."
        kill "$SINK_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT

log "Démarrage de la boîte de test : SMTP 127.0.0.1:$SMTP_PORT, UI http://127.0.0.1:$WEB_PORT"
"$PY" -m assistant.smtp_sink --port "$SMTP_PORT" --web-port "$WEB_PORT" --out "$ROOT/demo_data/mailbox" &
SINK_PID=$!
sleep 1.5
if ! kill -0 "$SINK_PID" 2>/dev/null; then
    echo "ERREUR : la boîte de test n'a pas démarré (port $SMTP_PORT déjà utilisé ?)." >&2
    exit 1
fi

# --- 5. l'assistant ----------------------------------------------------------
log "Lancement de l'assistant..."
case "$MODE" in
    web)
        echo "Interface web accessible : http://127.0.0.1:$UI_PORT  (Ctrl+C pour quitter)"
        exec "$PY" -m assistant.main --ui web --port "$UI_PORT" --smtp-port "$SMTP_PORT"
        ;;
    script)
        "$PY" -m assistant.demo_script --smtp-port "$SMTP_PORT"
        log "Vérifiez le message reçu sur http://127.0.0.1:$WEB_PORT"
        ;;
    cli|*)
        echo "Mode clavier. Tapez par exemple :"
        echo "  Remplis le formulaire avec ma CNI et ma carte Vitale, puis envoie-le par email."
        echo "Puis répondez à la question (email), et confirmez par « oui »."
        echo "Boîte de test : http://127.0.0.1:$WEB_PORT   ('quitter' pour sortir)"
        echo
        "$PY" -m assistant.main --ui cli --smtp-port "$SMTP_PORT"
        ;;
esac
