#!/bin/sh
# operation-contract.sh — shared validation, plan, and receipt contract for the
# credential-free ``ops/*`` wrappers in biohack-ddbb.
#
# This library is sourced (never executed) by the thin ``ops/<action>``
# wrappers. It enforces three invariants before any Compose invocation:
#
#   1. allowlisting  — only the known executable operations run; documentation
#      -like paths (Markdown, README.sh, .mdx) are rejected;
#   2. credential-free — secret-like arguments (passwords, tokens, DSNs, keys)
#      are refused before anything is executed;
#   3. no shell-evaluated input — arguments are quoted positional parameters,
#      never ``eval``'d, never interpolated into a command string.
#
# It performs no database SQL and accepts no database credentials. Credentials
# reach the backend adapter only through the protected VPS environment source
# consumed by Docker Compose, never through a wrapper argument.

# Allowlisted executable operations. Docs/README/MDX never appear here.
CONTRACT_ALLOWED_ACTIONS="load backfill reconcile backup restore cutover rollback"

# ── Allowlisting ───────────────────────────────────────────────────────────

contract_is_allowed_action() {
    case " $CONTRACT_ALLOWED_ACTIONS " in
        *" $1 "*) return 0 ;;
        *) return 1 ;;
    esac
}

contract_is_executable_action_path() {
    # Reject documentation-like paths regardless of a misleading name.
    case "$1" in
        *.md|*.mdx|*.txt|*.markdown|*.rst|*README*|*readme*|*DOC*|*doc*) return 1 ;;
        *) return 0 ;;
    esac
}

contract_validate_action() {
    contract_is_allowed_action "$1" || {
        echo "invalid action: $1" >&2
        return 2
    }
    contract_is_executable_action_path "$1" || {
        echo "documentation-like action rejected: $1" >&2
        return 2
    }
    return 0
}

# ── Credential-free argument scanning ──────────────────────────────────────

contract_has_secret() {
    # Return 0 if any argument looks like a credential value; 1 otherwise.
    for arg in "$@"; do
        case "$arg" in
            *password*|*PASSWORD*|*passwd*|*PASSWD*|*pgpass*|*PGPASS*|*pgpassword*|*PGPASSWORD*)
                return 0 ;;
            *token*|*TOKEN*|*secret*|*SECRET*|*api_key*|*API_KEY*|*apikey*|*APIKEY*)
                return 0 ;;
            *credential*|*CREDENTIAL*)
                return 0 ;;
            *postgresql://*|*postgres://*|*mysql://*|*redis://*|*amqp://*)
                return 0 ;;
            *DATABASE_URL*|*database_url*)
                return 0 ;;
        esac
    done
    return 1
}

contract_reject_secrets() {
    if contract_has_secret "$@"; then
        echo "secret-like argument rejected" >&2
        return 2
    fi
    return 0
}

# ── Deterministic plan identity ────────────────────────────────────────────

contract_plan_checksum() {
    # Stable SHA-256 over the sanitized operation parameters. The arguments are
    # allowlisted/validated upstream, so no secret or shell metacharacter can
    # reach this function.
    printf '%s\n' "$@" | sha256sum | cut -d' ' -f1
}

# ── Receipt emission (stdout + optional file) ──────────────────────────────

contract_emit_receipt() {
    payload=$1
    receipt_dir=${2:-}
    printf '%s\n' "$payload"
    if [ -n "$receipt_dir" ]; then
        mkdir -p "$receipt_dir" 2>/dev/null || return 1
        printf '%s\n' "$payload" > "$receipt_dir/receipt.json" 2>/dev/null || return 1
    fi
    return 0
}

# ── Service/profile resolution ─────────────────────────────────────────────

contract_service_for() {
    case "$1" in
        load|backfill|reconcile|cutover|rollback) printf 'store-operation' ;;
        backup) printf 'backup-%s' "$2" ;;
        restore) printf 'restore-%s' "$2" ;;
    esac
}

contract_profile_for() {
    case "$1" in
        backup|restore) printf 'backup' ;;
        *) printf 'operations' ;;
    esac
}

# ── Main dispatch (shared by every wrapper) ────────────────────────────────

contract_main() {
    action=$1
    shift

    contract_validate_action "$action" || return 2

    mode="dry-run"
    store=""
    receipt_dir=""
    compose_bin=${DOCKER_COMPOSE_BIN:-docker}
    compose_file=${DDBB_COMPOSE_FILE:-deploy/production/compose.yml}
    env_file=${DDBB_ENV_FILE:-/etc/sam/production.env}

    while [ "$#" -gt 0 ]; do
        case "$1" in
            --dry-run) mode="dry-run"; shift ;;
            --apply) mode="apply"; shift ;;
            --store)
                shift
                if [ "$#" -lt 1 ]; then
                    echo "missing --store value" >&2
                    return 2
                fi
                store=$1
                case "$store" in
                    identity|domain) ;;
                    *) echo "invalid store: $store" >&2; return 2 ;;
                esac
                shift ;;
            --receipt-dir)
                shift
                if [ "$#" -lt 1 ]; then
                    echo "missing --receipt-dir value" >&2
                    return 2
                fi
                receipt_dir=$1
                shift ;;
            *)
                if contract_has_secret "$1"; then
                    echo "secret-like argument rejected" >&2
                    return 2
                fi
                echo "unknown argument: $1" >&2
                return 2 ;;
        esac
    done

    if [ -z "$store" ]; then
        echo "missing --store identity|domain" >&2
        return 2
    fi

    # Defensive scan of the collected non-secret values (store name is already
    # restricted to identity|domain; receipt-dir is a path).
    if contract_has_secret "$store" "$receipt_dir"; then
        echo "secret-like value rejected" >&2
        return 2
    fi

    plan_checksum=$(contract_plan_checksum "$action" "$store" "$mode")

    # Dry-run is the default and performs no write: emit a deterministic plan
    # summary and return clean. The backend is never invoked in dry-run.
    if [ "$mode" = "dry-run" ]; then
        receipt=$(printf \
            '{"action":"%s","store":"%s","dry_run":true,"plan_checksum":"%s","counts":null,"blocked":false}' \
            "$action" "$store" "$plan_checksum")
        contract_emit_receipt "$receipt" "$receipt_dir"
        return 0
    fi

    # Apply: delegate to the backend adapter through Compose. Credentials are
    # consumed by Compose from the protected environment source only; the
    # wrapper passes a non-secret action + store.
    service=$(contract_service_for "$action" "$store")
    profile=$(contract_profile_for "$action")
    result=$("$compose_bin" compose \
        --env-file "$env_file" \
        -f "$compose_file" \
        --profile "$profile" \
        run --rm "$service" "$action" --store "$store")
    status=$?

    if [ "$status" -ne 0 ]; then
        contract_emit_receipt "$result" "$receipt_dir"
        return 1
    fi

    if printf '%s' "$result" | grep -q '"blocked"[[:space:]]*:[[:space:]]*true'; then
        contract_emit_receipt "$result" "$receipt_dir"
        return 1
    fi

    contract_emit_receipt "$result" "$receipt_dir"
    return 0
}
