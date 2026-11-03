#!/usr/bin/env bash
set -euo pipefail
script_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
python_cmd=${PYTHON:-python}
forward=()
while (($#)); do
  if [[ $1 == --python ]]; then
    if (($# < 2)); then echo '--python requires an executable' >&2; exit 2; fi
    python_cmd=$2
    shift 2
  else
    forward+=("$1")
    shift
  fi
done
exec "$python_cmd" "$script_dir/../generate.py" \
  --model Qwen/Qwen3-Coder-30B-A3B-Instruct --profile qwen3-coder "${forward[@]}"
