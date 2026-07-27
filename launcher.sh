#!/bin/bash
# launcher.sh — Analiza_Biegowa Streamlit lifecycle manager
# Called by the macOS .app wrapper (Analiza Biegowa.app, built via osacompile).
#
# Why this is not just "is the port busy?":
# several Streamlit projects live side by side (Analiza_Biegowa, Analiza_Kolarska,
# Tri_Dashboard) and they used to hardcode overlapping ports. A naive
# "port busy -> open browser" check would happily hand you the *cycling* app.
# So we identify servers by their working directory, not by the port alone.
#
# Behaviour:
#   1. Find a Streamlit server whose cwd is THIS project.
#   2. If it is serving stale code (started before the newest .py edit), restart it.
#   3. Otherwise reuse it.
#   4. If none exists, start one on the first free port in our range.

export PATH="$HOME/.local/bin:$HOME/Library/Python/3.14/bin:$HOME/Library/Python/3.13/bin:$HOME/Library/Python/3.12/bin:/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

APP_DIR="/Users/wielkikrzychmbp/Documents/Analiza_Biegowa"
LOG="/tmp/analiza_biegowa_launch.log"
PORT_MIN=8510
PORT_MAX=8519

exec > "$LOG" 2>&1
echo "[launcher] $(date) Started"
echo "[launcher] HOME=$HOME USER=$(whoami)"

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

# cwd of the process listening on a port ("" if the port is free)
port_owner_dir() {
  local pid
  pid="$(lsof -ti :"$1" -sTCP:LISTEN 2>/dev/null | head -1)"
  [ -z "$pid" ] && return 0
  lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | grep '^n' | cut -c2-
}

port_owner_pid() {
  lsof -ti :"$1" -sTCP:LISTEN 2>/dev/null | head -1
}

# epoch seconds of the newest .py file in the project (ignoring caches/worktrees)
newest_source_mtime() {
  find "$APP_DIR" -name '*.py' -not -path '*/.claude/*' -not -path '*/__pycache__/*' \
    -not -path '*/.git/*' -exec stat -f '%m' {} + 2>/dev/null | sort -rn | head -1
}

# epoch seconds when a pid started
pid_start_epoch() {
  local lstart
  lstart="$(ps -o lstart= -p "$1" 2>/dev/null)"
  [ -z "$lstart" ] && return 1
  date -j -f "%a %b %e %T %Y" "$lstart" "+%s" 2>/dev/null
}

open_and_exit() {
  echo "[launcher] Opening http://localhost:$1"
  open "http://localhost:$1"
  exit 0
}

# --------------------------------------------------------------------------
# 1. Is one of OUR servers already up?
# --------------------------------------------------------------------------
OUR_PORT=""
for p in $(seq "$PORT_MIN" "$PORT_MAX"); do
  if [ "$(port_owner_dir "$p")" = "$APP_DIR" ]; then
    OUR_PORT="$p"
    break
  fi
done

if [ -n "$OUR_PORT" ]; then
  PID="$(port_owner_pid "$OUR_PORT")"
  SRC_MTIME="$(newest_source_mtime)"
  PROC_START="$(pid_start_epoch "$PID")"

  if [ -n "$SRC_MTIME" ] && [ -n "$PROC_START" ] && [ "$SRC_MTIME" -gt "$PROC_START" ]; then
    # Streamlit does not reliably hot-reload imported modules, so a server
    # started before the last code change would quietly serve old analysis logic.
    echo "[launcher] Server on $OUR_PORT predates the newest code change — restarting"
    kill "$PID" 2>/dev/null
    sleep 2
    kill -9 "$PID" 2>/dev/null
  else
    echo "[launcher] Reusing healthy server on port $OUR_PORT"
    open_and_exit "$OUR_PORT"
  fi
fi

# --------------------------------------------------------------------------
# 2. Pick a free port
# --------------------------------------------------------------------------
PORT=""
for p in $(seq "$PORT_MIN" "$PORT_MAX"); do
  if [ -z "$(port_owner_pid "$p")" ]; then
    PORT="$p"
    break
  fi
  echo "[launcher] Port $p taken by: $(port_owner_dir "$p")"
done

if [ -z "$PORT" ]; then
  echo "[launcher] FATAL: no free port in $PORT_MIN-$PORT_MAX"
  osascript -e 'display dialog "Wszystkie porty 8510-8519 sa zajete.\n\nZamknij inne instancje Streamlita i sprobuj ponownie." buttons {"OK"} default button "OK" with title "Analiza Biegowa"' 2>/dev/null
  exit 1
fi
echo "[launcher] Using port $PORT"

cd "$APP_DIR" || { echo "[launcher] FATAL: cannot cd to $APP_DIR"; exit 1; }
export PYTHONPATH="$APP_DIR:$PYTHONPATH"

# --------------------------------------------------------------------------
# 3. Resolve a run command: prefer `python -m streamlit` (most robust)
# --------------------------------------------------------------------------
RUN_CMD=""

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

if [ -z "$RUN_CMD" ]; then
  SB="$(command -v streamlit 2>/dev/null)"
  if [ -n "$SB" ]; then
    RUN_CMD="$SB"
    echo "[launcher] Using streamlit binary: $SB"
  fi
fi

if [ -z "$RUN_CMD" ]; then
  echo "[launcher] FATAL: streamlit not found"
  osascript -e 'display dialog "Streamlit nie jest zainstalowany dla Twojego Pythona.\n\nOtwórz Terminal i uruchom:\n    pip3 install -r ~/Documents/Analiza_Biegowa/requirements.txt\n\nPotem kliknij ikonę ponownie." buttons {"OK"} default button "OK" with title "Analiza Biegowa"' 2>/dev/null
  exit 1
fi

# --------------------------------------------------------------------------
# 4. Launch Streamlit
# --------------------------------------------------------------------------
# shellcheck disable=SC2086
nohup $RUN_CMD run app.py \
  --server.port "$PORT" \
  --server.headless true \
  --browser.gatherUsageStats false \
  >> "$LOG" 2>&1 &

for _ in $(seq 1 60); do
  if [ "$(port_owner_dir "$PORT")" = "$APP_DIR" ]; then
    sleep 1
    open_and_exit "$PORT"
  fi
  sleep 0.5
done

echo "[launcher] Server did not start within timeout — see log above"
osascript -e 'display dialog "Serwer nie wystartował. Sprawdź log:\n    /tmp/analiza_biegowa_launch.log\n\nSzybki test w Terminalu:\n    cd ~/Documents/Analiza_Biegowa\n    python3 -m streamlit run app.py --server.port 8510" buttons {"OK"} default button "OK" with title "Analiza Biegowa"' 2>/dev/null
exit 1
