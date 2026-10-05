#!/usr/bin/env bash
# Update the app to the latest main and restart it. Run on the server, from
# the checkout (GitHub Actions calls it over SSH after the tests pass).
#
# The whole script is wrapped in main() so bash reads it completely before
# "git reset" can replace this file mid-run.
set -euo pipefail

main() {
  cd "$(dirname "$(readlink -f "$0")")/.."

  # One deploy at a time; a second push waits for the first to finish.
  exec 9>/tmp/voice-to-text-deploy.lock
  flock 9

  echo "==> Fetching latest main"
  git fetch --quiet origin main
  git reset --hard origin/main
  echo "    now at $(git log -1 --format='%h %s')"

  echo "==> Building and restarting containers"
  # COMPOSE_PROFILES in .env (e.g. COMPOSE_PROFILES=ai) is picked up automatically.
  docker compose up -d --build --remove-orphans

  echo "==> Waiting for the app to answer"
  for _ in $(seq 1 60); do
    if docker compose exec -T voice-to-text python -c \
      "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)" 2>/dev/null; then
      echo "    healthy"
      docker image prune -f >/dev/null
      echo "==> Deployed $(git log -1 --format='%h')"
      return 0
    fi
    sleep 2
  done

  echo "!! The app did not become healthy. Recent logs:" >&2
  docker compose logs --tail 50 voice-to-text >&2
  return 1
}

main "$@"
