#!/usr/bin/env bash
# VM bring-up checklist for the production-style (Docker Compose) deployment.
#
# Run from the repo root on the Nebius VM:  bash scripts/vm-bringup.sh
#
# Verifies prerequisites, builds the agent/eval image, and starts Airflow +
# MLflow. Safe to re-run. Pass --check to only run the checks (no build/up).
set -uo pipefail

cd "$(dirname "$0")/.."   # repo root

CHECK_ONLY=false
[ "${1:-}" = "--check" ] && CHECK_ONLY=true

ok()   { printf '  \033[32m[ok]\033[0m   %s\n' "$1"; }
warn() { printf '  \033[33m[warn]\033[0m %s\n' "$1"; }
fail() { printf '  \033[31m[fail]\033[0m %s\n' "$1"; FAILED=1; }
FAILED=0

echo "== Prerequisites =="
command -v docker >/dev/null 2>&1 && ok "docker: $(docker --version)" || fail "docker not found"
docker compose version >/dev/null 2>&1 && ok "docker compose plugin present" || fail "docker compose plugin missing"
command -v uv >/dev/null 2>&1 && ok "uv: $(uv --version)" || warn "uv not found (only needed for the standalone path)"
docker info >/dev/null 2>&1 && ok "docker daemon reachable" || fail "cannot talk to docker daemon (is your user in the docker group?)"

echo "== Configuration =="
if [ -f .env ]; then
  ok ".env present"
  # shellcheck disable=SC1091
  set -a; . ./.env; set +a
else
  fail ".env missing -- run: cp .env.example .env && edit NEBIUS_API_KEY"
fi

if [ -n "${NEBIUS_API_KEY:-}" ] && [ "${NEBIUS_API_KEY}" != "XXX" ]; then
  ok "NEBIUS_API_KEY set"
else
  fail "NEBIUS_API_KEY not set (agent step will fail)"
fi

export HOST_PROJECT_DIR="${HOST_PROJECT_DIR:-$(pwd)}"
ok "HOST_PROJECT_DIR=$HOST_PROJECT_DIR (used for DockerOperator bind mounts)"

if [ -n "${S3_BUCKET:-}" ]; then
  ok "S3_BUCKET=$S3_BUCKET (artifacts will be uploaded)"
else
  warn "S3_BUCKET empty -- artifacts stay local (upload step is a no-op)"
fi

if [ "$FAILED" -ne 0 ]; then
  echo; echo "Fix the [fail] items above, then re-run."; exit 1
fi

if [ "$CHECK_ONLY" = true ]; then
  echo; echo "Checks passed. Re-run without --check to build and start."; exit 0
fi

echo "== Build agent/eval image =="
docker build -t "${AGENT_IMAGE:-mlops-assignment:latest}" . || { fail "image build failed"; exit 1; }
ok "built ${AGENT_IMAGE:-mlops-assignment:latest}"

echo "== Start Airflow + MLflow =="
docker compose up -d || { fail "docker compose up failed"; exit 1; }

echo
echo "Done. Next steps:"
echo "  - Airflow UI : http://localhost:8080"
echo "      user 'admin', password:"
echo "      docker compose logs airflow | grep -i 'password'"
echo "  - MLflow UI  : http://localhost:5000  (experiment 'coding-agent-eval')"
echo "  - Trigger the 'evaluate_agent_docker' DAG (Trigger DAG w/ config),"
echo "    e.g. {\"subset\":\"verified\",\"split\":\"test\",\"workers\":5,\"task_slice\":\"0:3\"}"
echo "  - Artifacts land in ./runs/<run-id>/ ; capture screenshots/ per REPORT.md."
