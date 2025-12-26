#!/bin/bash
# Test the workers status endpoint

echo "🧪 Testing Workers Status Endpoint"
echo "============================================================"

BASE_URL="http://localhost:8000"
TIMESTAMP=$(date +%s)

# First, we need to login to get a token
echo ""
echo "📝 Step 1: Login to get auth token"
USER_EMAIL="demo_user_1_${TIMESTAMP}@example.com"
USER_PASSWORD="SecurePass123!"

# Register a test user
REG_DATA='{
  "email": "'$USER_EMAIL'",
  "password": "'$USER_PASSWORD'",
  "first_name": "Test",
  "last_name": "User",
  "organization_name": "Test Org '$TIMESTAMP'"
}'

REG_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d "$REG_DATA")

echo "User registered: $USER_EMAIL"

# Login to get token
LOGIN_DATA='{
  "email": "'$USER_EMAIL'",
  "password": "'$USER_PASSWORD'"
}'

LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "$LOGIN_DATA")

TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)

if [ -z "$TOKEN" ]; then
    echo "❌ Failed to get auth token"
    echo "Response: $LOGIN_RESPONSE"
    exit 1
fi

echo "✅ Got auth token: ${TOKEN:0:50}..."

# Test workers status endpoint
echo ""
echo "📝 Step 2: Test workers status endpoint"
echo "URL: $BASE_URL/api/v1/workers/status"

WORKERS_RESPONSE=$(curl -s -X GET "$BASE_URL/api/v1/workers/status" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json")

echo ""
echo "📊 Workers Status Response:"
echo "$WORKERS_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$WORKERS_RESPONSE"

# Test workers health endpoint
echo ""
echo "📝 Step 3: Test workers health endpoint"
echo "URL: $BASE_URL/api/v1/workers/health"

HEALTH_RESPONSE=$(curl -s -X GET "$BASE_URL/api/v1/workers/health" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json")

echo ""
echo "🏥 Workers Health Response:"
echo "$HEALTH_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$HEALTH_RESPONSE"

# Check if we got successful responses
if echo "$WORKERS_RESPONSE" | grep -q "active_workers"; then
    echo ""
    echo "✅ Workers status endpoint is working!"
else
    echo ""
    echo "⚠️ Workers status endpoint returned unexpected response"
fi

if echo "$HEALTH_RESPONSE" | grep -q "healthy"; then
    echo "✅ Workers health endpoint is working!"
else
    echo "⚠️ Workers health endpoint returned unexpected response"
fi

echo ""
echo "============================================================"
echo "🎉 Workers endpoint testing complete!"
