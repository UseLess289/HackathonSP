#!/usr/bin/env bash
# Launch chrome-devtools-mcp for this project.
#
# Chrome is not installed system-wide on this machine, so the script looks for
# a usable browser in this order:
#   1. $CHROME_DEVTOOLS_EXECUTABLE
#   2. google-chrome / chromium / brave in PATH
#   3. the Chromium build shipped with Playwright in ~/.cache/ms-playwright
#
# Override the browser at any time with:
#   CHROME_DEVTOOLS_EXECUTABLE=/path/to/chrome opencode
set -euo pipefail

find_browser() {
  if [ -n "${CHROME_DEVTOOLS_EXECUTABLE:-}" ] && [ -x "$CHROME_DEVTOOLS_EXECUTABLE" ]; then
    printf '%s\n' "$CHROME_DEVTOOLS_EXECUTABLE"
    return 0
  fi

  local name path
  for name in google-chrome google-chrome-stable chromium chromium-browser brave-browser brave; do
    if path=$(command -v "$name" 2>/dev/null); then
      printf '%s\n' "$path"
      return 0
    fi
  done

  local playwright
  playwright=$(ls -d "$HOME"/.cache/ms-playwright/chromium-*/chrome-linux64/chrome 2>/dev/null \
    | sort -V | tail -n 1 || true)
  if [ -n "$playwright" ] && [ -x "$playwright" ]; then
    printf '%s\n' "$playwright"
    return 0
  fi

  return 1
}

if ! browser=$(find_browser); then
  echo "chrome-devtools-mcp: no Chrome/Chromium found." >&2
  echo "Install Google Chrome, or set CHROME_DEVTOOLS_EXECUTABLE to a browser binary." >&2
  exit 1
fi

exec npx -y chrome-devtools-mcp@latest \
  --isolated \
  --no-usage-statistics \
  --no-performance-crux \
  --executablePath="$browser"
