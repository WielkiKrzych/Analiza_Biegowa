#!/bin/bash
# launcher.sh — Analiza_Biegowa Streamlit lifecycle manager
# Called by the macOS .app wrapper (Analiza_Biegowa.app).
# Starts the Streamlit server if not running, then opens the browser.

export PATH="$HOME/.local/bin:$HOME/Library/Python/3.14/bin:$HOME/Library/Python/3.13/bin:$HOME/Library/Python/3.12/bin:/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

APP_DIR="/Users/wielkikrzychmbp/Documents/Analiza_Biegowa"
LOG="/tmp/analiza_biegowa_launch.log"
PORT=8502
URL="http://localhost:$PORT"

exec > "$LOG" 2>&1
echo "[launcher] $(date) Started"

# ---- Find streamlit binary ----
STREAMLIT_BIN=""
for candidate in \
  "$HOME/Library/Python/3.14/bin/streamlit" \
  "$HOME/Library/Python/3.13/bin/streamlit" \
  "$HOME/Library/Python/3.12/bin/streamlit" \
  "$HOME/.local/bin/streamlit" \
  "/usr/local/bin/streamlit" \
  "/opt/homebrew/bin/streamlit"
do
  if [ -x "$candidate" ]; then
    STREAMLIT_BIN="$candidate"
    break
  fi
done

if [ -z "$STREAMLIT_BIN" ]; then
  STREAMLIT_BIN="$(command -v streamlit 2>/dev/null)"
fi

if [ -z "$STREAMLIT_BIN" ]; then
  echo "[launcher] FATAL: streamlit binary not found. Install with: pip3 install streamlit"
  osascript -e 'display dialog "Streamlit nie jest zainstalowany.\n\nUruchom w terminalu:\n    pip3 install -r ~/Documents/Analiza_Biegowa/requirements.txt" buttons {"OK"} default button "OK" with icon caution' 2>/dev/null
  exit 1
fi
echo "[launcher] Using streamlit: $STREAMLIT_BIN"

# ---- Already running? just open the browser ----
if lsof -ti :"$PORT" >/dev/null 2>&1; then
  echo "[launcher] Port $PORT already in use — opening browser"
  open "$URL"
  exit 0
fi

# ---- Launch Streamlit ----
cd "$APP_DIR" || { echo "[launcher] FATAL: cannot cd to $APP_DIR"; exit 1; }
export PYTHONPATH="$APP_DIR:$PYTHONPATH"

nohup "$STREAMLIT_BIN" run app.py \
  --server.port "$PORT" \
  --server.headless true \
  --browser.gatherUsageStats false \
  >> "$LOG" 2>&1 &

# ---- Wait for the server, then open the browser ----
for _ in $(seq 1 40); do
  if lsof -ti :"$PORT" >/dev/null 2>&1; then
    sleep 1
    open "$URL"
    echo "[launcher] Opened $URL"
    exit 0
  fi
  sleep 0.5
done

echo "[launcher] Server did not start within timeout — check $LOG"
open "$URL"
exit 0
