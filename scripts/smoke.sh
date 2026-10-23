#!/usr/bin/env bash
# Post-deploy smoke test: health → search → stores → contact → agent.
# Usage: ./scripts/smoke.sh https://app.liara.run
set -euo pipefail
BASE="${1:-http://127.0.0.1:8000}"
fail=0

check() { # name, condition-bit
  if [ "$2" = "1" ]; then echo "  ✓ $1"; else echo "  ✗ $1"; fail=$((fail+1)); fi
}

echo "▶ smoke test: $BASE"

health=$(curl -fsS "$BASE/api/health" || true)
echo "$health" | grep -q '"db_ready":true' && check "health + db" 1 || check "health + db" 0

ready=$(curl -fsS "$BASE/api/ready" || true)
echo "$ready" | grep -q '"shops"' && check "ready + counts" 1 || check "ready + counts" 0

curl -fsS "$BASE/" -o /tmp/torbgard-index.html || true
grep -q '<html' /tmp/torbgard-index.html 2>/dev/null && check "PWA html" 1 || check "PWA html" 0

product=$(curl -fsS -X POST "$BASE/api/search" -H 'content-type: application/json' \
  -d '{"query":"هدفون","limit":1}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["products"][0]["product_id"])' 2>/dev/null || true)
[ -n "${product:-}" ] && check "search returns product" 1 || check "search returns product" 0

stores=$(curl -fsS -X POST "$BASE/api/stores" -H 'content-type: application/json' \
  -d "{\"product_id\":\"$product\",\"lat\":35.6949,\"lon\":51.4071,\"limit\":3}" || true)
echo "$stores" | grep -q '"price_valid"' && check "stores payload" 1 || check "stores payload" 0

shop=$(echo "$stores" | python3 -c 'import sys,json;print(json.load(sys.stdin)["stores"][0]["shop_id"])' 2>/dev/null || true)
[ -n "${shop:-}" ] && check "store found" 1 || check "store found" 0

thread=$(curl -fsS -X POST "$BASE/api/contact" -H 'content-type: application/json' \
  -d "{\"shop_id\":\"$shop\",\"product_id\":\"$product\",\"intent\":\"price_stock\"}" || true)
echo "$thread" | grep -q 'thread_id' && check "contact accepted" 1 || check "contact accepted" 0

agent=$(curl -fsS -X POST "$BASE/api/agent" -H 'content-type: application/json' \
  -d '{"message":"هدفون زیر ۳ میلیون"}' || true)
echo "$agent" | grep -q '"cards"' && check "agent cards" 1 || check "agent cards" 0

echo
if [ "$fail" -eq 0 ]; then echo "✅ smoke passed"; else echo "❌ $fail check(s) failed"; exit 1; fi
