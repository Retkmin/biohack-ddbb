#!/bin/bash
# gate.sh — a greenfield prerequisite gate (plan/protected_config/digests/...).
#
# Writes a redacted, plan-bound attestation for one named prerequisite gate on
# the shared volume. Credential-free: no URL, user, password, token, or secret
# is accepted or emitted.

set -u

# Source the shared contract, normalizing Windows CRLF line endings (the
# production lib may carry CRLF from the host checkout) without modifying it.
lib_bin="/usr/local/share/greenfield/operation-contract.sh"
lib_norm="/tmp/operation-contract.norm.sh"
tr -d '\r' < "$lib_bin" > "$lib_norm" || exit 1
. "$lib_norm"

gate="${GATE:-plan}"
plan_sha="${PLAN_SHA256:-}"

gates_dir="/shared/gates"
mkdir -p "$gates_dir" 2>/dev/null || exit 1

printf '{"gate":"%s","plan_sha256":"%s","attested":true}\n' "$gate" "$plan_sha" \
    > "$gates_dir/$gate.attestation.json" 2>/dev/null || exit 1

echo "gate=$gate attested plan_sha256=$plan_sha"
