#!/usr/bin/env bash
# Post-deploy smoke test: the five things a judge will do first.
#   ./scripts/smoke.sh https://your-app.liara.run
# Exits non-zero on the first broken contract.
set -Eeuo pipefail

BASE="${1:-${BASE_URL:-http://127.0.0.1:8000}}"
FAILED=0
say()  { printf '  %s %s\n' "$1" "$2"; }
ok()   { say "✓" "$1"; }
bad()  { say "✗" "$1"; FAILED=$((FAILED+1)); }
check() { if eval "$2" >/dev/null 2>&1; then ok "$1"; else bad "$1"; fi; }

echo "▶ Torbgard smoke test → $BASE"

HEALTH="$(curl -fsS --max-time 10 "$BASE/api/health" || echo '{}')"
echo "$HEALTH" | grep -q '"status":"ok"' && ok "health endpoint" || bad "health endpoint"
echo "$HEALTH" | grep -q '"db_ready":true' && ok "database ready" || bad "database ready"

META="$(curl -fsS --max-time 10 "$BASE/api/meta" || echo '{}')"
echo "$META" | grep -q '"demo"' && ok "meta exposes demo flags" || bad "meta exposes demo flags"
echo "$META" | grep -q '"simulated_contact":true' && ok "simulation is disclosed" || bad "simulation is disclosed"

SEARCH="$(curl -fsS --max-time 15 -X POST "$BASE/api/search" \
  -H 'content-type: application/json' \
  -d '{"query":"هدفون بلوتوثی","limit":3}' || echo '{}')"
echo "$SEARCH" | grep -q '"products"' && ok "search returns products" || bad "search returns products"

PID="$(printf '%s' "$SEARCH" | python3 -c 'import sys,json;print(json.load(sys.stdin)["products"][0]["product_id"])' 2>/dev/null || true)"
if [ -n "${PID:-}" ]; then
  ok "first product id: ${PID:0:18}…"
  STORES="$(curl -fsS --max-time 15 -X POST "$BASE/api/stores" \
    -H 'content-type: application/json' \
    -d "{\"product_id\":\"$PID\",\"lat\":35.6949,\"lon\":51.4071,\"limit\":5}" || echo '{}')"
  echo "$STORES" | grep -q '"price_valid"' && ok "stores carry transparency fields" || bad "stores carry transparency fields"
  echo "$STORES" | grep -q '"availability"' && ok "availability present" || bad "availability present"
else
  bad "could not read a product id"
fi

AGENT="$(curl -fsS --max-time 30 -X POST "$BASE/api/agent" \
  -H 'content-type: application/json' \
  -d '{"message":"هدفون زیر ۳ میلیون"}' || echo '{}')"
echo "$AGENT" | grep -q '"cards"' && ok "agent returns cards" || bad "agent returns cards"
echo "$AGENT" | grep -q '"tool_calls"' && ok "agent reports tool calls" || bad "agent reports tool calls"

if [ "$FAILED" -eq 0 ]; then
  echo "✅ all smoke checks passed"
else
  echo "❌ $FAILED check(s) failed"
  exit 1
fi
