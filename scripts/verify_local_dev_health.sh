#!/bin/bash
# 驗證本地 API 與前端 dev server 是否接通。

set -euo pipefail

API_PORT="${TOP10_API_PORT:-8001}"
FRONTEND_PORT="${TOP10_FRONTEND_PORT:-5173}"
API_BASE_URL="${VITE_API_BASE_URL:-http://127.0.0.1:${API_PORT}}"
FRONTEND_URL="http://127.0.0.1:${FRONTEND_PORT}"

check_url() {
  local label="$1"
  local url="$2"
  local expected="$3"
  local status

  status="$(curl -s -o /dev/null -w "%{http_code}" "$url" || true)"
  if [ "$status" = "000" ]; then
    echo "FAIL $label status=000 url=$url"
    echo "HINT 本機服務未連上；請先執行 bash scripts/start_ui.sh，或確認 TOP10_API_PORT / TOP10_FRONTEND_PORT 是否正確。"
    exit 1
  fi
  if [ "$status" != "$expected" ]; then
    echo "FAIL $label status=$status url=$url"
    exit 1
  fi
  echo "OK $label status=$status"
}

check_url "api.health" "$API_BASE_URL/api/health" "200"
check_url "api.weekly_candidates" "$API_BASE_URL/api/weekly-candidates?risk_style=balanced&target_type=stocks&holding_period=swing&entry_preference=mixed&risk_limit=excludeThemes&limit=10" "200"
check_url "api.stock_detail" "$API_BASE_URL/api/stocks/3030/detail?limit=1200" "200"
check_url "frontend" "$FRONTEND_URL/" "200"

echo "LOCAL_DEV_HEALTH_OK api=$API_BASE_URL frontend=$FRONTEND_URL"
