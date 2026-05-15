#!/usr/bin/env bash
set -euo pipefail

# Enables:
#  1) Immutable releases
#  2) Require actions to be pinned to a full-length commit SHA
#  3) Always suggest updating pull request branches
#  4) Automatically delete head branches
#
# For every repo directory under ROOT_DIR (default: current directory).
#
# Requirements:
#   - gh CLI authenticated: gh auth status
#   - each directory is a git repo with an "origin" remote pointing to GitHub

ROOT_DIR="."
DRY_RUN="false"
ONLY_REPO=""

usage() {
  cat <<'EOF'
Usage: enable-gh-settings.sh [-r ROOT_DIR] [-n]
  -r, --root     Root directory to scan (default: current directory)
  -o, --only     Only process one repo under root (dir name or path)
  -n, --dry-run  Print actions without making changes
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -r|--root)
      ROOT_DIR="${2:-}"
      shift 2
      ;;
    -n|--dry-run)
      DRY_RUN="true"
      shift
      ;;
    -o|--only)
      ONLY_REPO="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      err "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$ROOT_DIR" ]]; then
  err "Root directory is required."
  usage
  exit 1
fi

ROOT_DIR="${ROOT_DIR%/}"
only_dir=""
if [[ -n "$ONLY_REPO" ]]; then
  if [[ "$ONLY_REPO" == /* ]]; then
    only_dir="$ONLY_REPO"
  elif [[ "$ONLY_REPO" == "." ]]; then
    only_dir="$ROOT_DIR"
  else
    only_dir="$ROOT_DIR/$ONLY_REPO"
  fi
  only_dir="${only_dir%/}"
  if [[ "$only_dir" != "$ROOT_DIR" && "$only_dir" != "$ROOT_DIR/"* ]]; then
    err "--only must point to a repo directory under root."
    exit 1
  fi
  if [[ ! -d "$only_dir" ]]; then
    err "Repo directory not found: $only_dir"
    exit 1
  fi
fi

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
  enabled="$(gh api "repos/$owner_repo/immutable-releases" --jq '.enabled'  || true)"
  if [[ "$enabled" == "true" ]]; then
    return 0
  elif [[ "$enabled" == "false" ]]; then
    return 1
  else
    return 2
  fi
}

check_sha_pinning_required() {
  local owner_repo="$1"
  local enabled
  enabled="$(gh api "repos/$owner_repo/actions/permissions" --jq '.sha_pinning_required' 2>/dev/null || true)"
  if [[ "$enabled" == "true" ]]; then
    return 0
  elif [[ "$enabled" == "false" ]]; then
    return 1
  else
    return 2
  fi
}

check_allow_update_branch() {
  local owner_repo="$1"
  local enabled
  enabled="$(gh api "repos/$owner_repo" --jq '.allow_update_branch' 2>/dev/null || true)"
  if [[ "$enabled" == "true" ]]; then
    return 0
  elif [[ "$enabled" == "false" ]]; then
    return 1
  else
    return 2
  fi
}

check_delete_branch_on_merge() {
  local owner_repo="$1"
  local enabled
  enabled="$(gh api "repos/$owner_repo" --jq '.delete_branch_on_merge' 2>/dev/null || true)"
  if [[ "$enabled" == "true" ]]; then
    return 0
  elif [[ "$enabled" == "false" ]]; then
    return 1
  else
    return 2
  fi
}

# --- preflight ---
command -v gh >/dev/null 2>&1 || { err "gh CLI not found. Install it (brew install gh)."; exit 1; }
gh auth status >/dev/null 2>&1 || { err "gh not authenticated. Run: gh auth login"; exit 1; }

processed=0
skipped=0
failed_ops=0
skipped_already=0
skipped_unknown=0
verify_failed_count=0

declare -a no_permission=()
declare -a not_accessible=()
declare -a verify_failed=()
declare -a other_errors=()
declare -a skipped_dirs=()

note "Root directory: $ROOT_DIR"
if [[ "$DRY_RUN" == "true" ]]; then
  note "Dry run: enabled (no changes will be made)"
fi
if [[ -n "$only_dir" ]]; then
  note "Only repo: $only_dir"
fi
note "Scanning for repo directories..."

shopt -s nullglob
for d in "$ROOT_DIR"/*/; do
  repo_dir="${d%/}"
  dir_name="$(basename "$repo_dir")"

  if [[ -n "$only_dir" && "$repo_dir" != "$only_dir" ]]; then
    continue
  fi

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
  immutable_status=2
  if check_immutable_releases "$owner_repo"; then
    immutable_status=0
  else
    immutable_status=$?
  fi
  if [[ "$immutable_status" -eq 0 ]]; then
    skipped_already=$((skipped_already + 1))
    note "  - immutable-releases: already enabled (skipping)"
  elif [[ "$immutable_status" -eq 2 ]]; then
    skipped_unknown=$((skipped_unknown + 1))
    not_accessible+=("$owner_repo (immutable-releases)")
    note "  - immutable-releases: SKIPPED (cannot read current status)"
  else
    if [[ "$DRY_RUN" == "true" ]]; then
      note "  - immutable-releases: DRY RUN (would enable)"
    else
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
    fi
  fi

  # --- 1b) Immutable releases: check ---
  if [[ "$immutable_status" -eq 2 ]]; then
    note "  - immutable-releases check: NOT ACCESSIBLE"
  elif [[ "$immutable_status" -ne 0 ]]; then
    if check_immutable_releases "$owner_repo"; then
      immutable_status=0
    else
      immutable_status=$?
    fi
    case "$immutable_status" in
      0) note "  - immutable-releases check: OK" ;;
      1) note "  - immutable-releases check: NOT ENABLED"
         if [[ "$DRY_RUN" == "false" ]]; then
           verify_failed_count=$((verify_failed_count + 1))
           verify_failed+=("$owner_repo (immutable-releases)")
         fi ;;
      2) note "  - immutable-releases check: NOT ACCESSIBLE"
         if [[ "$DRY_RUN" == "false" ]]; then
           verify_failed_count=$((verify_failed_count + 1))
           verify_failed+=("$owner_repo (immutable-releases)")
         fi ;;
    esac
  fi

  # --- 2) SHA pinning required: enable ---
  # The API requires "enabled" and (depending on context) "allowed_actions" too.
  # We fetch current values and PUT them back with sha_pinning_required=true.
  sha_pinning_status=2
  current_enabled="$(gh api "repos/$owner_repo/actions/permissions" --jq '.enabled' 2>/dev/null || true)"
  current_allowed="$(gh api "repos/$owner_repo/actions/permissions" --jq '.allowed_actions' 2>/dev/null || true)"

  if [[ -z "$current_enabled" || -z "$current_allowed" ]]; then
    failed_ops=$((failed_ops + 1))
    no_permission+=("$owner_repo (actions/permissions read)")
    note "  - sha_pinning_required: SKIPPED (cannot read current actions/permissions; likely no permission)"
  else
    sha_pinning_status=2
    if check_sha_pinning_required "$owner_repo"; then
      sha_pinning_status=0
    else
      sha_pinning_status=$?
    fi
    if [[ "$sha_pinning_status" -eq 0 ]]; then
      skipped_already=$((skipped_already + 1))
      note "  - sha_pinning_required: already enabled (skipping)"
    elif [[ "$sha_pinning_status" -eq 2 ]]; then
      skipped_unknown=$((skipped_unknown + 1))
      not_accessible+=("$owner_repo (sha_pinning_required)")
      note "  - sha_pinning_required: SKIPPED (cannot read current status)"
    else
      if [[ "$DRY_RUN" == "true" ]]; then
        note "  - sha_pinning_required: DRY RUN (would enable)"
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
    fi
  fi

  # --- 2b) SHA pinning required: check ---
  if [[ "$sha_pinning_status" -eq 2 ]]; then
    note "  - sha_pinning_required check: NOT ACCESSIBLE"
  elif [[ "$sha_pinning_status" -ne 0 ]]; then
    if check_sha_pinning_required "$owner_repo"; then
      sha_pinning_status=0
    else
      sha_pinning_status=$?
    fi
    case "$sha_pinning_status" in
      0) note "  - sha_pinning_required check: OK" ;;
      1) note "  - sha_pinning_required check: NOT ENABLED"
         if [[ "$DRY_RUN" == "false" ]]; then
           verify_failed_count=$((verify_failed_count + 1))
           verify_failed+=("$owner_repo (sha_pinning_required)")
         fi ;;
      2) note "  - sha_pinning_required check: NOT ACCESSIBLE"
         if [[ "$DRY_RUN" == "false" ]]; then
           verify_failed_count=$((verify_failed_count + 1))
           verify_failed+=("$owner_repo (sha_pinning_required)")
         fi ;;
    esac
  fi

  # --- 3) Always suggest updating pull request branches: enable ---
  allow_update_status=2
  if check_allow_update_branch "$owner_repo"; then
    allow_update_status=0
  else
    allow_update_status=$?
  fi
  if [[ "$allow_update_status" -eq 0 ]]; then
    skipped_already=$((skipped_already + 1))
    note "  - allow_update_branch: already enabled (skipping)"
  elif [[ "$allow_update_status" -eq 2 ]]; then
    skipped_unknown=$((skipped_unknown + 1))
    not_accessible+=("$owner_repo (allow_update_branch)")
    note "  - allow_update_branch: SKIPPED (cannot read current status)"
  else
    if [[ "$DRY_RUN" == "true" ]]; then
      note "  - allow_update_branch: DRY RUN (would enable)"
    else
      if ! out="$(gh api -X PATCH "repos/$owner_repo" -F allow_update_branch=true 2>&1)"; then
        failed_ops=$((failed_ops + 1))
        if grep -qiE 'HTTP 403|HTTP 404|Resource not accessible|Must have admin|requires.*admin|insufficient' <<<"$out"; then
          no_permission+=("$owner_repo (allow_update_branch)")
          note "  - allow_update_branch: FAILED (likely no permission)"
        else
          other_errors+=("$owner_repo (allow_update_branch): $out")
          note "  - allow_update_branch: FAILED (unexpected)"
        fi
      else
        note "  - allow_update_branch: enabled request sent"
      fi
    fi
  fi

  # --- 3b) Always suggest updating pull request branches: check ---
  if [[ "$allow_update_status" -eq 2 ]]; then
    note "  - allow_update_branch check: NOT ACCESSIBLE"
  elif [[ "$allow_update_status" -ne 0 ]]; then
    if check_allow_update_branch "$owner_repo"; then
      allow_update_status=0
    else
      allow_update_status=$?
    fi
    case "$allow_update_status" in
      0) note "  - allow_update_branch check: OK" ;;
      1) note "  - allow_update_branch check: NOT ENABLED"
         if [[ "$DRY_RUN" == "false" ]]; then
           verify_failed_count=$((verify_failed_count + 1))
           verify_failed+=("$owner_repo (allow_update_branch)")
         fi ;;
      2) note "  - allow_update_branch check: NOT ACCESSIBLE"
         if [[ "$DRY_RUN" == "false" ]]; then
           verify_failed_count=$((verify_failed_count + 1))
           verify_failed+=("$owner_repo (allow_update_branch)")
         fi ;;
    esac
  fi

  # --- 4) Automatically delete head branches: enable ---
  delete_branch_status=2
  if check_delete_branch_on_merge "$owner_repo"; then
    delete_branch_status=0
  else
    delete_branch_status=$?
  fi
  if [[ "$delete_branch_status" -eq 0 ]]; then
    skipped_already=$((skipped_already + 1))
    note "  - delete_branch_on_merge: already enabled (skipping)"
  elif [[ "$delete_branch_status" -eq 2 ]]; then
    skipped_unknown=$((skipped_unknown + 1))
    not_accessible+=("$owner_repo (delete_branch_on_merge)")
    note "  - delete_branch_on_merge: SKIPPED (cannot read current status)"
  else
    if [[ "$DRY_RUN" == "true" ]]; then
      note "  - delete_branch_on_merge: DRY RUN (would enable)"
    else
      if ! out="$(gh api -X PATCH "repos/$owner_repo" -F delete_branch_on_merge=true 2>&1)"; then
        failed_ops=$((failed_ops + 1))
        if grep -qiE 'HTTP 403|HTTP 404|Resource not accessible|Must have admin|requires.*admin|insufficient' <<<"$out"; then
          no_permission+=("$owner_repo (delete_branch_on_merge)")
          note "  - delete_branch_on_merge: FAILED (likely no permission)"
        else
          other_errors+=("$owner_repo (delete_branch_on_merge): $out")
          note "  - delete_branch_on_merge: FAILED (unexpected)"
        fi
      else
        note "  - delete_branch_on_merge: enabled request sent"
      fi
    fi
  fi

  # --- 4b) Automatically delete head branches: check ---
  if [[ "$delete_branch_status" -eq 2 ]]; then
    note "  - delete_branch_on_merge check: NOT ACCESSIBLE"
  elif [[ "$delete_branch_status" -ne 0 ]]; then
    if check_delete_branch_on_merge "$owner_repo"; then
      delete_branch_status=0
    else
      delete_branch_status=$?
    fi
    case "$delete_branch_status" in
      0) note "  - delete_branch_on_merge check: OK" ;;
      1) note "  - delete_branch_on_merge check: NOT ENABLED"
         if [[ "$DRY_RUN" == "false" ]]; then
           verify_failed_count=$((verify_failed_count + 1))
           verify_failed+=("$owner_repo (delete_branch_on_merge)")
         fi ;;
      2) note "  - delete_branch_on_merge check: NOT ACCESSIBLE"
         if [[ "$DRY_RUN" == "false" ]]; then
           verify_failed_count=$((verify_failed_count + 1))
           verify_failed+=("$owner_repo (delete_branch_on_merge)")
         fi ;;
    esac
  fi
done

note ""
note "===== Summary ====="
note "Processed repos:  $processed"
note "Skipped dirs:     $skipped"
note "Failed ops:       $failed_ops"
note "Verify failures:  $verify_failed_count"
note "Skipped enabled:  $skipped_already"
note "Skipped unknown:  $skipped_unknown"

if ((${#skipped_dirs[@]} > 0)); then
  note ""
  note "Skipped:"
  for s in "${skipped_dirs[@]}"; do note "  - $s"; done
fi

if ((${#verify_failed[@]} > 0)); then
  note ""
  note "Verify failures (enable attempted but setting not confirmed active):"
  printf "%s\n" "${verify_failed[@]}" | sort -u | while read -r line; do
    note "  - $line"
  done
fi

if ((${#no_permission[@]} > 0)); then
  note ""
  note "No permission / not accessible:"
  printf "%s\n" "${no_permission[@]}" | sort -u | while read -r line; do
    note "  - $line"
  done
fi

if ((${#not_accessible[@]} > 0)); then
  note ""
  note "Skipped (status unreadable / not accessible):"
  printf "%s\n" "${not_accessible[@]}" | sort -u | while read -r line; do
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
