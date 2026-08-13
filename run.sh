#!/usr/bin/env bash
#
# One command to run the whole thing.
#
#   ./run.sh          build the frontend and serve everything on one port
#   ./run.sh dev      hot-reloading dev servers (Vite on 5173)
#   ./run.sh setup    install dependencies and stop
#   ./run.sh test     run all three test suites
#   ./run.sh stop     stop anything this script started
#
# Nothing here needs an API key. Without them the system runs offline against
# its bundled dataset and says so in every answer.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

AI_PORT="${AI_PORT:-8000}"
# 5000 is taken by AirPlay Receiver on every modern macOS, so it is a poor
# default for a tool meant to run first time without configuration.
API_PORT="${PORT:-4000}"
WEB_PORT="${WEB_PORT:-5173}"
RUN_DIR="$ROOT/.run"
VENV="$ROOT/ai-service/.venv"

mkdir -p "$RUN_DIR"

# --- pretty output ----------------------------------------------------------
if [[ -t 1 ]]; then
  BOLD=$'\033[1m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; DIM=$'\033[2m'; OFF=$'\033[0m'
else
  BOLD=""; GREEN=""; YELLOW=""; RED=""; DIM=""; OFF=""
fi
step() { printf '%s==>%s %s\n' "$BOLD$GREEN" "$OFF" "$1"; }
info() { printf '    %s\n' "$1"; }
warn() { printf '%s !%s  %s\n' "$YELLOW" "$OFF" "$1"; }
die()  { printf '%serror:%s %s\n' "$RED" "$OFF" "$1" >&2; exit 1; }

# --- prerequisites ----------------------------------------------------------
check_prerequisites() {
  command -v node >/dev/null 2>&1 || die "Node.js 20+ is required (https://nodejs.org)"
  command -v python3 >/dev/null 2>&1 || die "Python 3.11+ is required (https://python.org)"

  local node_major
  node_major="$(node -p 'process.versions.node.split(".")[0]')"
  [[ "$node_major" -ge 20 ]] || die "Node.js 20+ is required (found $(node -v))"

  python3 - <<'PY' || die "Python 3.11+ is required"
import sys
sys.exit(0 if sys.version_info >= (3, 11) else 1)
PY
}

# --- dependencies -----------------------------------------------------------
setup() {
  check_prerequisites

  if [[ ! -x "$VENV/bin/python" ]]; then
    step "Creating the Python virtual environment"
    python3 -m venv "$VENV"
  fi

  step "Installing AI service dependencies"
  "$VENV/bin/pip" install --quiet --upgrade pip
  # requirements.txt adds Gemini, FAISS and transformers; the core set is enough
  # to run every feature offline, and installs in seconds rather than minutes.
  "$VENV/bin/pip" install --quiet -r ai-service/requirements-core.txt

  step "Installing backend dependencies"
  (cd backend && npm install --silent --no-audit --no-fund)

  step "Installing frontend dependencies"
  (cd frontend && npm install --silent --no-audit --no-fund)

  info "Dependencies ready."
}

needs_setup() {
  [[ ! -x "$VENV/bin/python" ]] && return 0
  [[ ! -d backend/node_modules ]] && return 0
  [[ ! -d frontend/node_modules ]] && return 0
  return 1
}

# --- process management -----------------------------------------------------
# Kill whatever is listening on a port. The pidfiles cover processes this
# script started, but a previous invocation left looping in another terminal
# still owns its children, and its supervisor has to go too or the port stays
# held. Ports are the thing that actually matters, so they are the backstop.
free_port() {
  local port="$1"
  local pids; pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
  [[ -z "$pids" ]] && return 0
  echo "$pids" | xargs -r kill 2>/dev/null || true
  sleep 0.4
  pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
  [[ -n "$pids" ]] && echo "$pids" | xargs -r kill -9 2>/dev/null || true
  return 0
}

stop_services() {
  local stopped=0

  # A previous run.sh supervisor, if one is still looping.
  if [[ -e "$RUN_DIR/runner.pid" ]]; then
    local runner; runner="$(cat "$RUN_DIR/runner.pid")"
    if [[ "$runner" != "$$" ]] && kill -0 "$runner" 2>/dev/null; then
      kill "$runner" 2>/dev/null || true
      stopped=1
    fi
    rm -f "$RUN_DIR/runner.pid"
  fi

  for pidfile in "$RUN_DIR"/*.pid; do
    [[ -e "$pidfile" ]] || continue
    local pid; pid="$(cat "$pidfile")"
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      # Give it a moment to close listeners before forcing.
      for _ in 1 2 3 4 5 6 7 8 9 10; do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.2
      done
      kill -9 "$pid" 2>/dev/null || true
      stopped=1
    fi
    rm -f "$pidfile"
  done
  # Backstop: anything still holding our ports, whoever started it.
  for port in "$AI_PORT" "$API_PORT" "$WEB_PORT"; do
    if port_in_use "$port"; then
      free_port "$port"
      stopped=1
    fi
  done

  [[ "$stopped" -eq 1 ]] && info "Stopped running services."
  return 0
}

port_in_use() {
  lsof -ti tcp:"$1" >/dev/null 2>&1
}

wait_for_health() {
  local url="$1" name="$2" attempts="${3:-60}"
  for ((i = 1; i <= attempts; i++)); do
    if curl -sf "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.5
  done
  warn "$name did not become healthy at $url"
  return 1
}

start_ai_service() {
  step "Starting the AI service on port $AI_PORT"
  (
    cd ai-service
    OFFLINE_MODE="${OFFLINE_MODE:-1}" \
      "$VENV/bin/python" -m uvicorn app.main:app \
      --host 0.0.0.0 --port "$AI_PORT" --log-level warning \
      > "$RUN_DIR/ai-service.log" 2>&1 &
    echo $! > "$RUN_DIR/ai-service.pid"
  )
  wait_for_health "http://127.0.0.1:$AI_PORT/health" "AI service"
}

start_backend() {
  step "Starting the API gateway on port $API_PORT"
  (
    cd backend
    PORT="$API_PORT" \
      AI_SERVICE_URL="http://127.0.0.1:$AI_PORT" \
      NODE_ENV="${NODE_ENV:-development}" \
      node src/server.js > "$RUN_DIR/backend.log" 2>&1 &
    echo $! > "$RUN_DIR/backend.pid"
  )
  wait_for_health "http://127.0.0.1:$API_PORT/health" "API gateway"
}

build_frontend() {
  step "Building the frontend"
  (cd frontend && npm run build --silent)
}

start_vite() {
  step "Starting the Vite dev server on port $WEB_PORT"
  (
    cd frontend
    VITE_API_PROXY="http://127.0.0.1:$API_PORT" \
      npx vite --port "$WEB_PORT" --strictPort \
      > "$RUN_DIR/frontend.log" 2>&1 &
    echo $! > "$RUN_DIR/frontend.pid"
  )
  wait_for_health "http://127.0.0.1:$WEB_PORT" "Vite"
}

banner() {
  local url="$1"
  echo
  printf '%s  AI Agri-Market Intelligence is running%s\n' "$BOLD$GREEN" "$OFF"
  echo
  printf '    Open  %s%s%s\n' "$BOLD" "$url" "$OFF"
  echo
  printf '    %sAPI     http://127.0.0.1:%s/api%s\n' "$DIM" "$API_PORT" "$OFF"
  printf '    %sAI docs http://127.0.0.1:%s/docs%s\n' "$DIM" "$AI_PORT" "$OFF"
  printf '    %sLogs    %s/%s\n' "$DIM" "$RUN_DIR" "$OFF"
  echo
  if [[ "${OFFLINE_MODE:-1}" == "1" ]]; then
    printf '    %sRunning offline against the bundled dataset. Every answer is%s\n' "$DIM" "$OFF"
    printf '    %sflagged as such. Add API keys to ai-service/.env for live data.%s\n' "$DIM" "$OFF"
    echo
  fi
  printf '    %sStop with ./run.sh stop, or Ctrl-C%s\n' "$DIM" "$OFF"
  echo
}

# Find a free port at or after $1, so a busy default does not stop the app from
# starting. The chosen port is printed, so the URL is never a guess.
next_free_port() {
  local port="$1"
  for _ in $(seq 1 20); do
    port_in_use "$port" || { echo "$port"; return 0; }
    port=$((port + 1))
  done
  die "Could not find a free port near $1"
}

check_ports() {
  local wanted_ai="$AI_PORT" wanted_api="$API_PORT"

  AI_PORT="$(next_free_port "$AI_PORT")"
  API_PORT="$(next_free_port "$API_PORT")"

  [[ "$AI_PORT" != "$wanted_ai" ]] && warn "Port $wanted_ai was busy; using $AI_PORT for the AI service."
  [[ "$API_PORT" != "$wanted_api" ]] && warn "Port $wanted_api was busy; using $API_PORT for the gateway."
  return 0
}

run_tests() {
  check_prerequisites
  needs_setup && setup

  step "AI service tests"
  (cd ai-service && "$VENV/bin/python" -m pytest tests/ -q)

  step "Backend tests"
  (cd backend && npm test --silent)

  step "Frontend tests"
  (cd frontend && npx vitest run)

  step "Frontend build"
  (cd frontend && npm run build --silent)

  echo
  printf '%s  All suites passed.%s\n\n' "$BOLD$GREEN" "$OFF"
}

# --- entry point ------------------------------------------------------------
MODE="${1:-start}"

case "$MODE" in
  setup)
    setup
    ;;

  test)
    run_tests
    ;;

  stop)
    stop_services
    ;;

  dev)
    stop_services
    needs_setup && setup
    check_ports
    trap 'echo; stop_services; exit 0' INT TERM
    start_ai_service
    start_backend
    WEB_PORT="$(next_free_port "$WEB_PORT")"
    start_vite
    banner "http://localhost:$WEB_PORT"
    info "Hot reload is on. Edit anything under frontend/src and the page updates."
    # Hold the terminal so Ctrl-C reaches the trap.
    while true; do sleep 1; done
    ;;

  start | "")
    stop_services
    needs_setup && setup
    check_ports
    trap 'echo; stop_services; exit 0' INT TERM
    echo $$ > "$RUN_DIR/runner.pid"
    build_frontend
    start_ai_service
    start_backend
    banner "http://localhost:$API_PORT"
    while true; do sleep 1; done
    ;;

  *)
    die "Unknown command '$MODE'. Use: start | dev | setup | test | stop"
    ;;
esac
