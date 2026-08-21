#!/usr/bin/env bash
# Loads src/main/resources/seed/seed-data.json into the CognoDB instance pointed to by your
# COGNODB_* environment variables. Safe to re-run - every write is a MERGE keyed on a stable id.
#
# Usage:
#   export COGNODB_URI=bolt+s://<instance-id>.databases.cognodb.cloud
#   export COGNODB_USERNAME=cognodb
#   export COGNODB_PASSWORD=<your-password>
#   ./scripts/seed.sh              # merge seed data in (idempotent)
#   ./scripts/seed.sh --reset      # wipe the database first, then seed (e.g. switching domains)
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -z "${COGNODB_URI:-}" ] || [ -z "${COGNODB_PASSWORD:-}" ]; then
  echo "COGNODB_URI and COGNODB_PASSWORD must be set (see .env.example)." >&2
  exit 1
fi

mvn -q -DskipTests package
java -jar target/retailgraph.jar --seed "$@"
