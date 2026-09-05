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

# Allowlisted executable operations. Docs/README/MDX never appear here. The
# ``preflight``/``verify-empty`` actions are the fail-closed greenfield VPS
# deployment gates; the remaining actions are the separate, source-driven
# migration tooling that a greenfield release never invokes.
CONTRACT_ALLOWED_ACTIONS="load backfill reconcile backup restore cutover rollback preflight verify-empty initialize activate"

# ── Allowlisting ───────────────────────────────────────────────────────────

contract_is_allowed_action() {
    case " $CONTRACT_ALLOWED_ACTIONS " in
        *" $1 "*) return 0 ;;
        *) return 1 ;;
    esac
}

contract_is_executable_action_path() {
    # Reject documentation-like paths regardless of a misleading name or case.
    lower=$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')
    case "$lower" in
        *.md|*.mdx|*.txt|*.markdown|*.rst|*readme*|*doc*) return 1 ;;
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
        load|backfill|reconcile|cutover|rollback|preflight|verify-empty|initialize|activate) printf 'store-operation' ;;
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

    # Lifecycle operations (preflight/verify-empty/initialize/activate) are
    # additionally gated on the release digest/manifest binding before any
    # store-operation run, so a missing or malformed digest (or an incomplete
    # release manifest) fails closed before Compose is invoked.
    case "$action" in
        preflight|verify-empty|initialize|activate)
            if ! contract_apply_gates_ok; then
                contract_emit_blocked_receipt "$action" "release digests not validated"
                return 1
            fi
            ;;
    esac

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

# ── Greenfield deployment gates: plan, attestations, empty stores ──────────
#
# These primitives implement the fail-closed greenfield deployment protocol
# (preflight -> empty stores -> initialize -> activate). They are
# credential-free: they hash, atomically publish state, and validate
# prerequisite attestations without ever accepting or emitting a URL, user,
# password, token, or secret. Activation never proceeds on a partial
# prerequisite set — every gate must be attested for the exact plan checksum
# and both scoped stores must be empty.

contract_plan_file_checksum() {
    # Immutable SHA-256 identity of the deployment plan file.
    file=$1
    sha256sum "$file" | cut -d' ' -f1
}

contract_atomic_publish() {
    # Atomically publish content to target: write a sibling temp file, then
    # rename over the target. A reader never observes a partially written
    # state file (preflight/active publication).
    target=$1
    content=$2
    dir=$(dirname "$target")
    tmp="$dir/.state.tmp.$$"
    printf '%s\n' "$content" > "$tmp" 2>/dev/null || return 1
    mv "$tmp" "$target" 2>/dev/null || return 1
    return 0
}

contract_attestation_ok() {
    # Require a prerequisite attestation file that is present and positive
    # (contains `"attested":true`). A missing or negative attestation fails
    # closed before any activation.
    attestation_file=$1
    [ -f "$attestation_file" ] || {
        echo "missing attestation" >&2
        return 1
    }
    grep -Eq '"attested"[[:space:]]*:[[:space:]]*true' "$attestation_file" 2>/dev/null || {
        echo "attestation not granted" >&2
        return 1
    }
    return 0
}

contract_empty_store_ok() {
    # Require a scoped store directory to be empty (no application data files).
    # A missing or non-empty store fails closed before initialization; a
    # greenfield release never imports or backfills legacy data.
    store_dir=$1
    [ -d "$store_dir" ] || {
        echo "missing store" >&2
        return 1
    }
    [ -z "$(find "$store_dir" -mindepth 1 -print -quit 2>/dev/null)" ] || {
        echo "store not empty" >&2
        return 1
    }
    return 0
}

contract_all_gates_ok() {
    # Require every prerequisite gate attestation for the exact plan checksum.
    # Any missing, negative, or stale attestation returns 1.
    gates_dir=$1
    plan_sha=$2
    for gate in plan protected_config digests dns_tls capacity retention; do
        attestation_file="$gates_dir/$gate.attestation.json"
        [ -f "$attestation_file" ] || {
            echo "missing attestation: $gate" >&2
            return 1
        }
        grep -Eq '"attested"[[:space:]]*:[[:space:]]*true' "$attestation_file" 2>/dev/null || {
            echo "attestation not granted: $gate" >&2
            return 1
        }
        grep -Eq "\"plan_sha256\"[[:space:]]*:[[:space:]]*\"$plan_sha\"" "$attestation_file" 2>/dev/null || {
            echo "stale attestation: $gate" >&2
            return 1
        }
    done
    return 0
}

contract_emit_blocked_receipt() {
    # Emit a redacted blocked receipt for a greenfield deployment gate.
    action=$1
    reason=$2
    printf '{"action":"%s","dry_run":false,"plan_checksum":"","counts":null,"blocked":true,"failure_code":"blocked","failure_reason":"%s"}\n' \
        "$action" "$reason"
    return 1
}

contract_image_digest_ok() {
    # Require a well-formed SHA-256 image digest (exactly 64 lowercase hex
    # characters). The production Compose resolves application artifacts by
    # immutable ``@sha256:<digest>`` references; a missing, empty, uppercase, or
    # non-hex digest fails closed before activation.
    digest=$1
    case "$digest" in
        *[!0-9a-f]*)
            echo "malformed image digest" >&2
            return 1
            ;;
    esac
    if [ "${#digest}" -ne 64 ]; then
        echo "malformed image digest" >&2
        return 1
    fi
    return 0
}

contract_release_digests_ok() {
    # Require both approved release digests (backend/frontend) to be present and
    # well-formed. This is the fail-closed digest gate the digest-pinned Compose
    # image references depend on; activation never proceeds on a partial or
    # malformed set.
    backend_digest=$1
    frontend_digest=$2
    contract_image_digest_ok "$backend_digest" || return 1
    contract_image_digest_ok "$frontend_digest" || return 1
    return 0
}

contract_release_manifest_ok() {
    # Require a complete immutable release manifest: ``SHA256SUMS`` must cover
    # every artifact the release claims (plan.json, compose.yml,
    # control-manifest.schema.json, README.md) AND every entry must verify
    # against the actual file content (``sha256sum -c``). This binds each
    # artifact's digest to its canonical content, so a well-formed-but-wrong
    # digest or a manifest that omits a claimed artifact fails closed.
    release_dir=$1
    [ -n "$release_dir" ] && [ -d "$release_dir" ] || {
        echo "missing release dir" >&2
        return 1
    }
    [ -f "$release_dir/SHA256SUMS" ] || {
        echo "missing SHA256SUMS" >&2
        return 1
    }
    for artifact in plan.json compose.yml control-manifest.schema.json README.md; do
        [ -f "$release_dir/$artifact" ] || {
            echo "missing artifact: $artifact" >&2
            return 1
        }
        grep -q "  $artifact\$" "$release_dir/SHA256SUMS" || {
            echo "missing checksum entry: $artifact" >&2
            return 1
        }
    done
    ( cd "$release_dir" && sha256sum -c SHA256SUMS >/dev/null 2>&1 ) || {
        echo "checksum mismatch" >&2
        return 1
    }
    return 0
}

contract_apply_gates_ok() {
    # Fail-closed gate for apply-mode lifecycle operations (preflight,
    # verify-empty, initialize, activate): the approved backend/frontend release
    # digests must be present and well-formed, and — when ``DDBB_RELEASE_DIR`` is
    # set — the release manifest must be complete and checksum-verified. This is
    # the digest/manifest binding invoked by the dispatch before any
    # store-operation run; it reads only non-secret digest/release values.
    backend_digest=${BACKEND_IMAGE_DIGEST:-}
    frontend_digest=${FRONTEND_IMAGE_DIGEST:-}
    contract_release_digests_ok "$backend_digest" "$frontend_digest" || {
        echo "release digests not validated" >&2
        return 1
    }
    release_dir=${DDBB_RELEASE_DIR:-}
    if [ -n "$release_dir" ]; then
        contract_release_manifest_ok "$release_dir" || return 1
    fi
    return 0
}
