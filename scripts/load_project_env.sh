#!/usr/bin/env bash
# Source optional .env from project root without clobbering variables explicitly
# provided by the caller, for example: HH_CHAT_REPLY_SEND=0 scripts/run_...
# Must be sourced after cd to the repository root.

if [[ -f .env ]]; then
  declare -A __hh_project_env_overrides=()
  while IFS='=' read -r __hh_project_env_name _; do
    case "$__hh_project_env_name" in
      HH_*|PYTHONPATH|VITE_*)
        __hh_project_env_overrides["$__hh_project_env_name"]="${!__hh_project_env_name-}"
        ;;
    esac
  done < <(env)

  set -a
  # shellcheck disable=SC1091
  source .env
  set +a

  for __hh_project_env_name in "${!__hh_project_env_overrides[@]}"; do
    export "$__hh_project_env_name=${__hh_project_env_overrides[$__hh_project_env_name]}"
  done
  unset __hh_project_env_name __hh_project_env_overrides
fi
