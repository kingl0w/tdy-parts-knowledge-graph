#!/usr/bin/env bash
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
CATALOG="$REPO/data/catalog.ttl"
OUT="$REPO/data/catalog-inferred.ttl"
SYMQ="$REPO/rules/symmetry/fitswith-symmetric.rq"
TMP="$(mktemp)"
SYM="$(mktemp --suffix=.ttl)"

for rule in "$REPO"/rules/*.rq; do
  sparql --data "$CATALOG" --query "$rule" --results=ttl \
    | grep -viE '^[[:space:]]*@?prefix[[:space:]]' \
    | grep -vE '^[[:space:]]*$' \
    | grep -vE '^[[:space:]]*#' >> "$TMP"
done

{ echo "@prefix tdy: <https://tdytrading.example/parts#> ."; echo ""; sort -u "$TMP"; } > "$SYM"
sparql --data "$SYM" --query "$SYMQ" --results=ttl \
  | grep -viE '^[[:space:]]*@?prefix[[:space:]]' | grep -vE '^[[:space:]]*$' >> "$TMP"

{ echo "@prefix tdy: <https://tdytrading.example/parts#> ."; echo ""; sort -u "$TMP"; } > "$OUT"
rm -f "$TMP" "$SYM"
echo "wrote $OUT"
