#!/bin/bash
# coordinator.sh — greenfield activation gate (fail closed).
#
# Requires ALL prerequisite gates to be attested for the exact plan checksum
# AND both scoped stores to be initialized (empty-schema markers present)
# before atomically publishing the ``initialized`` state via the REAL
# operation-contract.sh primitives. Any missing/stale attestation, or a store
# that was never initialized (an unhealthy dependency), leaves the state
# unpublished and emits a redacted blocked receipt within the timeout window.
#
# Credential-free: emits only opaque plan checksum/state/environment flags.

set -u

# Source the shared contract, normalizing Windows CRLF line endings (the
# production lib may carry CRLF from the host checkout) without modifying it.
lib_bin="/usr/local/share/greenfield/operation-contract.sh"
lib_norm="/tmp/operation-contract.norm.sh"
tr -d '\r' < "$lib_bin" > "$lib_norm" || exit 1
. "$lib_norm"

plan_sha="${PLAN_SHA256:-}"
timeout="${TIMEOUT:-6}"

gates_dir="/shared/gates"
identity_dir="/shared/stores/identity"
domain_dir="/shared/stores/domain"
state_path="/shared/state.json"

stores_initialized() {
    [ -f "$identity_dir/.schema.json" ] || return 1
    [ -f "$domain_dir/.schema.json" ] || return 1
    return 0
}

deadline=$(( $(date +%s) + timeout ))

while :; do
    if contract_all_gates_ok "$gates_dir" "$plan_sha" 2>/dev/null \
        && stores_initialized 2>/dev/null; then
        contract_atomic_publish "$state_path" \
            '{"state":"initialized","environment":"vps-greenfield","traffic_enabled":false}'
        echo "ACTIVE plan_sha256=$plan_sha state=initialized"
        exit 0
    fi

    if [ "$(date +%s)" -ge "$deadline" ]; then
        contract_emit_blocked_receipt "preflight" "incomplete gates or uninitialized stores within timeout"
        echo "BLOCKED plan_sha256=$plan_sha reason=timeout_or_incomplete_gates"
        exit 1
    fi

    sleep 1
done
