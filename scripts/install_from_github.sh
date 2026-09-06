#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${HH_AUTO_RESPONSE_REPO_URL:-https://github.com/gest0r1/hh-auto-response.git}"
REPO_REF="${HH_AUTO_RESPONSE_REF:-main}"
INSTALL_DIR="${1:-$HOME/hh-auto-response}"

if ! command -v git >/dev/null 2>&1; then
  echo "ERROR: git is required." >&2
  exit 127
fi

if [[ -e "$INSTALL_DIR" ]]; then
  echo "ERROR: install directory already exists: $INSTALL_DIR" >&2
  echo "Use the existing checkout or choose another target directory." >&2
  exit 2
fi

echo "Cloning $REPO_URL ($REPO_REF) into $INSTALL_DIR"
git clone --branch "$REPO_REF" --single-branch "$REPO_URL" "$INSTALL_DIR"

exec bash "$INSTALL_DIR/scripts/install.sh"
