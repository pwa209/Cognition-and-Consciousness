#!/usr/bin/env bash
set -Eeuo pipefail

factorcon_die() {
  printf '%s\n' "ERROR: $*" >&2
  exit 2
}

factorcon_repo_root() {
  cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." >/dev/null 2>&1
  pwd -P
}

factorcon_config_value() {
  local config_path="$1"
  local section="$2"
  local key="$3"
  python3 - "$config_path" "$section" "$key" <<'PY'
import json, pathlib, sys
path = pathlib.Path(sys.argv[1])
base = json.loads(path.read_text(encoding="utf-8"))
root = path.resolve().parent.parent
if sys.argv[2] == "server":
    linked = pathlib.Path(base["server"])
    value = json.loads((linked if linked.is_absolute() else root / linked).read_text(encoding="utf-8"))
else:
    value = base
print(value[sys.argv[3]])
PY
}

factorcon_verify_identity() {
  local expected_host="$1"
  local expected_user="$2"
  local observed_host observed_user
  observed_host="$(hostname)"
  observed_user="$(id -un)"
  [[ "$observed_host" == "$expected_host" ]] || factorcon_die "host mismatch: expected $expected_host, got $observed_host"
  [[ "$observed_user" == "$expected_user" ]] || factorcon_die "user mismatch: expected $expected_user, got $observed_user"
}

factorcon_require_root() {
  local root="$1"
  local prefix="$2"
  case "$root" in
    "$prefix"/*) ;;
    *) factorcon_die "unsafe root $root; expected a child of $prefix" ;;
  esac
  [[ "$root" != "$prefix" ]] || factorcon_die "project root may not equal broad prefix $prefix"
}

