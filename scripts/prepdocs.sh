#!/usr/bin/env bash
# Run the ingestion pipeline
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$PROJECT_DIR/app/backend"

cd "$BACKEND_DIR"
python prepdocs.py --download "$@"
