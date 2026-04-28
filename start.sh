#!/bin/bash
set -euo pipefail

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [[ -f "$script_dir/.env" ]]; then
	set -a
	# shellcheck disable=SC1090
	source "$script_dir/.env"
	set +a
fi

exec python -m ultron_mini.launcher
