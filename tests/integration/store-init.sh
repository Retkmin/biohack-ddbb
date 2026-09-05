#!/bin/bash
# store-init.sh — empty-schema initialization for one scoped store.
#
# Reuses the REAL operation-contract.sh ``contract_empty_store_ok`` primitive:
# it initializes ONLY an empty store and writes a schema marker. A non-empty
# store fails closed (no import, no backfill). Credential-free.

set -u

# Source the shared contract, normalizing Windows CRLF line endings (the
# production lib may carry CRLF from the host checkout) without modifying it.
lib_bin="/usr/local/share/greenfield/operation-contract.sh"
lib_norm="/tmp/operation-contract.norm.sh"
tr -d '\r' < "$lib_bin" > "$lib_norm" || exit 1
. "$lib_norm"

store_name="${STORE_NAME:-identity}"
store_dir="${STORE_DIR:-/shared/stores/identity}"

# Ensure the scoped store directory exists, then initialize ONLY if it is
# empty; a non-empty store fails closed.
mkdir -p "$store_dir" 2>/dev/null || exit 1

if contract_empty_store_ok "$store_dir"; then
    printf '{"store":"%s","initialized":true}\n' "$store_name" \
        > "$store_dir/.schema.json" 2>/dev/null || exit 1
    echo "store=$store_name initialized"
    exit 0
else
    echo "store=$store_name BLOCKED not-empty"
    exit 1
fi
