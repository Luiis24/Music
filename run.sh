#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -d .vendor/flask ]]; then
  curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
  python3 /tmp/get-pip.py --target ./.vendor
  PYTHONPATH="./.vendor" python3 -m pip install --target ./.vendor -r requirements.txt
fi

export PYTHONPATH="$PWD/.vendor${PYTHONPATH:+:$PYTHONPATH}"
exec python3 app.py
