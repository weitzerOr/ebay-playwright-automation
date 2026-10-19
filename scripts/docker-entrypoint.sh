#!/bin/sh
set -e

mkdir -p /app/allure-results /app/allure-report /app/reports/screenshots /app/reports/traces

if [ "$#" -eq 0 ]; then
  set -- pytest
fi

run_with_display() {
  if [ "${HEADLESS}" = "true" ] || [ "${HEADLESS}" = "1" ]; then
    exec "$@"
  fi
  exec xvfb-run --auto-servernum --server-args="-screen 0 1440x900x24" "$@"
}

case "$1" in
  pytest|python|python3)
    run_with_display "$@"
    ;;
  *)
    exec "$@"
    ;;
esac
