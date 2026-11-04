#!/bin/bash
# Double-click this file (or run ./start.command) to start HireHub + Speak-to-Apply on your Mac.
cd "$(dirname "$0")" || exit 1
KEYS="../hirehub-keys/keys.env"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is not installed. Run:  xcode-select --install   then try again."; read -r; exit 1
fi
if [ ! -f "$KEYS" ]; then echo "Keys file not found at $KEYS"; read -r; exit 1; fi

if [ ! -d .venv ]; then
  echo "First run: setting up (about 1 minute)…"
  python3 -m venv .venv || { echo "Could not create a virtual environment."; read -r; exit 1; }
fi
source .venv/bin/activate
pip install -q --disable-pip-version-check -r requirements-local.txt || { echo "Package install failed."; read -r; exit 1; }

set -a; source "$KEYS"; set +a
export PREFILL_SECRET="$(python3 -c 'import secrets;print(secrets.token_urlsafe(24))')"
export RECRUITER_PASSWORD="${RECRUITER_PASSWORD:-hirehub-demo}"
export HIREHUB_URL="http://localhost:8001"
export DATA_DIR_HH="$PWD/hirehub/data" DATA_DIR_SP="$PWD/speak/data"

# free the ports if a previous run is still going
for p in 8001 8002; do lsof -ti tcp:$p 2>/dev/null | xargs kill 2>/dev/null; done

(cd hirehub && DATA_DIR="$DATA_DIR_HH" uvicorn app:app --port 8001 --log-level warning) &
HH=$!
(cd speak && DATA_DIR="$DATA_DIR_SP" uvicorn app:app --port 8002 --log-level warning) &
SPK=$!
trap 'kill $HH $SPK 2>/dev/null; exit' INT TERM EXIT

for i in $(seq 1 30); do curl -s localhost:8002/healthz >/dev/null && curl -s localhost:8001/healthz >/dev/null && break; sleep 1; done
echo ""
echo "  Speak-to-Apply:  http://localhost:8002"
echo "  HireHub:         http://localhost:8001"
echo "  Recruiter view:  http://localhost:8001/recruiter   (user: recruiter, password: $RECRUITER_PASSWORD)"
echo "  Metrics:         http://localhost:8002/stats"
echo ""
echo "  Keep this window open. Press Ctrl+C to stop."
open "http://localhost:8002"
wait
