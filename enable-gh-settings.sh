#!/usr/bin/env bash
set -euo pipefail

# Enables:
#  1) Immutable releases
#  2) Require actions to be pinned to a full-length commit SHA
#
# For every repo directory under ROOT_DIR (default: current directory).
#
# Requirements:
#   - gh CLI authenticated: gh auth status
#   - each directory is a git repo with an "origin" remote pointing to GitHub

ROOT_DIR="${1:-.}"

err()  { printf "ERROR: %s\n" "$*" >&2; }
note() { printf "%s\n" "$*"; }

get_owner_repo() {
  local repo_dir="$1"
  local origin path owner repo

  origin="$(git -C "$repo_dir" remote get-url origin 2>/dev/null || true)"
  [[ -n "$origin" ]] || return 1

  if [[ "$origin" =~ ^git@github\.com:(.+)$ ]]; then
    path="${BASH_REMATCH[1]}"
  elif [[ "$origin" =~ ^https?://github\.com/(.+)$ ]]; then
    path="${BASH_REMATCH[1]}"
  else
    return 2
  fi

  path="${path%.git}"
  path="${path%/}"

  owner="${path%%/*}"
  repo="${path#*/}"

  [[ -n "$owner" && -n "$repo" && "$owner" != "$repo" ]] || return 3
  printf "%s/%s" "$owner" "$repo"
}

check_immutable_releases() {
  local owner_repo="$1"
  local enabled
  enabled="$(gh api "repos/$owner_repo/immutable-releases" --jq '.enabled' 2>/dev/null || true)"
  [[ "$enabled" == "true" ]]
}

check_sha_pinning_required() {
  local owner_repo="$1"
  local enabled
  enabled="$(gh api "repos/$owner_repo/actions/permissions" --jq '.sha_pinning_required' 2>/dev/null || true)"
  [[ "$enabled" == "true" ]]
}

# --- preflight ---
command -v gh >/dev/null 2>&1 || { err "gh CLI not found. Install it (brew install gh)."; exit 1; }
gh auth status >/dev/null 2>&1 || { err "gh not authenticated. Run: gh auth login"; exit 1; }

processed=0
skipped=0
failed_ops=0

declare -a no_permission=()
declare -a other_errors=()
declare -a skipped_dirs=()

note "Root directory: $ROOT_DIR"
note "Scanning for repo directories..."

shopt -s nullglob
for d in "$ROOT_DIR"/*/; do
  repo_dir="${d%/}"
  dir_name="$(basename "$repo_dir")"

  if [[ ! -d "$repo_dir/.git" ]]; then
    skipped=$((skipped + 1))
    skipped_dirs+=("$dir_name (not a git repo)")
    continue
  fi

  owner_repo=""
  if ! owner_repo="$(get_owner_repo "$repo_dir")"; then
    skipped=$((skipped + 1))
    skipped_dirs+=("$dir_name (no/unsupported GitHub origin remote)")
    continue
  fi

  processed=$((processed + 1))
  note ""
  note "==> [$processed] $owner_repo"

  # --- 1) Immutable releases: enable ---
  if ! out="$(gh api -X PUT "repos/$owner_repo/immutable-releases" 2>&1)"; then
    failed_ops=$((failed_ops + 1))
    if grep -qiE 'HTTP 403|HTTP 404|Resource not accessible|Must have admin|requires.*admin|insufficient' <<<"$out"; then
      no_permission+=("$owner_repo (immutable-releases)")
      note "  - immutable-releases: FAILED (likely no permission)"
    else
      other_errors+=("$owner_repo (immutable-releases): $out")
      note "  - immutable-releases: FAILED (unexpected)"
    fi
  else
    note "  - immutable-releases: enabled request sent"
  fi

  # --- 1b) Immutable releases: check ---
  if check_immutable_releases "$owner_repo"; then
    note "  - immutable-releases check: OK"
  else
    note "  - immutable-releases check: NOT ENABLED / NOT ACCESSIBLE"
  fi

  # --- 2) SHA pinning required: enable ---
  # The API requires "enabled" and (depending on context) "allowed_actions" too.
  # We fetch current values and PUT them back with sha_pinning_required=true.
  current_enabled="$(gh api "repos/$owner_repo/actions/permissions" --jq '.enabled' 2>/dev/null || true)"
  current_allowed="$(gh api "repos/$owner_repo/actions/permissions" --jq '.allowed_actions' 2>/dev/null || true)"

  if [[ -z "$current_enabled" || -z "$current_allowed" ]]; then
    failed_ops=$((failed_ops + 1))
    no_permission+=("$owner_repo (actions/permissions read)")
    note "  - sha_pinning_required: SKIPPED (cannot read current actions/permissions; likely no permission)"
  else
    if ! out="$(gh api -X PUT "repos/$owner_repo/actions/permissions" \
        -F enabled="$current_enabled" \
        -F allowed_actions="$current_allowed" \
        -F sha_pinning_required=true \
        2>&1)"; then
      failed_ops=$((failed_ops + 1))
      if grep -qiE 'HTTP 403|HTTP 404|Resource not accessible|Must have admin|requires.*admin|insufficient' <<<"$out"; then
        no_permission+=("$owner_repo (sha_pinning_required)")
        note "  - sha_pinning_required: FAILED (likely no permission)"
      else
        other_errors+=("$owner_repo (sha_pinning_required): $out")
        note "  - sha_pinning_required: FAILED (unexpected)"
      fi
    else
      note "  - sha_pinning_required: enabled request sent"
    fi
  fi

  # --- 2b) SHA pinning required: check ---
  if check_sha_pinning_required "$owner_repo"; then
    note "  - sha_pinning_required check: OK"
  else
    note "  - sha_pinning_required check: NOT ENABLED / NOT ACCESSIBLE"
  fi
done

note ""
note "===== Summary ====="
note "Processed repos:  $processed"
note "Skipped dirs:     $skipped"
note "Failed ops:       $failed_ops"

if ((${#skipped_dirs[@]} > 0)); then
  note ""
  note "Skipped:"
  for s in "${skipped_dirs[@]}"; do note "  - $s"; done
fi

if ((${#no_permission[@]} > 0)); then
  note ""
  note "No permission / not accessible:"
  printf "%s\n" "${no_permission[@]}" | sort -u | while read -r line; do
    note "  - $line"
  done
fi

if ((${#other_errors[@]} > 0)); then
  note ""
  note "Other errors:"
  for e in "${other_errors[@]}"; do
    note "  - $e"
  done
fi

note ""
note "Done."
