#!/bin/bash
# launcher.sh — Analiza_Biegowa Streamlit lifecycle manager
# Called by the macOS .app wrapper (Analiza Biegowa.app, built via osacompile).
# Starts the Streamlit server if not running, then opens the browser.

export PATH="$HOME/.local/bin:$HOME/Library/Python/3.14/bin:$HOME/Library/Python/3.13/bin:$HOME/Library/Python/3.12/bin:/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

APP_DIR="/Users/wielkikrzychmbp/Documents/Analiza_Biegowa"
LOG="/tmp/analiza_biegowa_launch.log"
PORT=8502
URL="http://localhost:$PORT"

exec > "$LOG" 2>&1
echo "[launcher] $(date) Started"
echo "[launcher] HOME=$HOME USER=$(whoami)"

# ---- Already running? just open the browser ----
if lsof -ti :"$PORT" >/dev/null 2>&1; then
  echo "[launcher] Port $PORT already in use — opening browser"
  open "$URL"
  exit 0
fi

cd "$APP_DIR" || { echo "[launcher] FATAL: cannot cd to $APP_DIR"; exit 1; }
export PYTHONPATH="$APP_DIR:$PYTHONPATH"

# ---- Resolve a run command: prefer `python -m streamlit` (most robust) ----
RUN_CMD=""

# 1) A python that can import streamlit
for py in \
  "$HOME/Library/Python/3.14/bin/python3" \
  "$HOME/Library/Python/3.13/bin/python3" \
  "$HOME/Library/Python/3.12/bin/python3" \
  "/opt/homebrew/bin/python3" \
  "/usr/local/bin/python3" \
  "$(command -v python3 2>/dev/null)"
do
  if [ -n "$py" ] && [ -x "$py" ] && "$py" -c "import streamlit" >/dev/null 2>&1; then
    RUN_CMD="$py -m streamlit"
    echo "[launcher] Using: $RUN_CMD"
    break
  fi
done

# 2) Fall back to a streamlit console script on PATH
if [ -z "$RUN_CMD" ]; then
  SB="$(command -v streamlit 2>/dev/null)"
  if [ -n "$SB" ]; then
    RUN_CMD="$SB"
    echo "[launcher] Using streamlit binary: $SB"
  fi
fi

# 3) Nothing found — tell the user how to fix it
if [ -z "$RUN_CMD" ]; then
  echo "[launcher] FATAL: streamlit not found"
  osascript -e 'display dialog "Streamlit nie jest zainstalowany dla Twojego Pythona.\n\nOtwórz Terminal i uruchom:\n    pip3 install -r ~/Documents/Analiza_Biegowa/requirements.txt\n\nPotem kliknij ikonę ponownie." buttons {"OK"} default button "OK" with title "Analiza Biegowa"' 2>/dev/null
  exit 1
fi

# ---- Launch Streamlit ----
# shellcheck disable=SC2086
nohup $RUN_CMD run app.py \
  --server.port "$PORT" \
  --server.headless true \
  --browser.gatherUsageStats false \
  >> "$LOG" 2>&1 &

# ---- Wait for the server, then open the browser ----
for _ in $(seq 1 60); do
  if lsof -ti :"$PORT" >/dev/null 2>&1; then
    sleep 1
    open "$URL"
    echo "[launcher] Opened $URL"
    exit 0
  fi
  sleep 0.5
done

echo "[launcher] Server did not start within timeout — see log above"
osascript -e 'display dialog "Serwer nie wystartował. Sprawdź log:\n    /tmp/analiza_biegowa_launch.log\n\nSzybki test w Terminalu:\n    cd ~/Documents/Analiza_Biegowa\n    python3 -m streamlit run app.py --server.port 8502" buttons {"OK"} default button "OK" with title "Analiza Biegowa"' 2>/dev/null
open "$URL"
exit 0
