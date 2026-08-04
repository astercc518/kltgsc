#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

mapfile -t candidate_files < <(
  git ls-files --cached --others --exclude-standard |
    while IFS= read -r path; do
      case "$path" in
        docs/architecture/*|docs/operations/*|docker-compose*.yml|.env.example|backend/.env.example)
          printf '%s\n' "$path"
          ;;
      esac
    done
)
mapfile -t documentation_files < <(
  printf '%s\n' "${candidate_files[@]}" |
    grep -E '^docs/(architecture|operations)/' || true
)

failed=0

scan_rule() {
  local rule_name="$1"
  local expression="$2"
  local matches
  matches="$(grep -IlE "$expression" "${candidate_files[@]}" 2>/dev/null || true)"
  if [[ -n "$matches" ]]; then
    echo "tracked secret scan failed: $rule_name" >&2
    while IFS= read -r path; do
      echo "  file: $path" >&2
    done <<<"$matches"
    failed=1
  fi
}

scan_documentation_rule() {
  local rule_name="$1"
  local expression="$2"
  local matches
  matches="$(grep -IlE "$expression" "${documentation_files[@]}" 2>/dev/null || true)"
  if [[ -n "$matches" ]]; then
    echo "tracked secret scan failed: $rule_name" >&2
    while IFS= read -r path; do
      echo "  file: $path" >&2
    done <<<"$matches"
    failed=1
  fi
}

scan_rule "private-key-material" '-----BEGIN ([A-Z ]+ )?PRIVATE KEY-----'
scan_documentation_rule "credential-in-connection-uri" '(postgresql|postgres|redis|rediss)://[^<[:space:]]+:[^<[:space:]@]+@'
scan_documentation_rule "literal-ipv4-in-operations-doc" '([0-9]{1,3}\.){3}[0-9]{1,3}'

if [[ "$failed" -ne 0 ]]; then
  exit 1
fi

echo "tracked secret scan passed"
