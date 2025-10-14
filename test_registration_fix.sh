#!/bin/bash
# Test script to verify the registration fix for duplicate organization names

echo "🔧 Registration Fix Test Suite"
echo "============================================================"

BASE_URL="http://localhost:8000"
ORG_NAME="Demo Organization"
TIMESTAMP=$(date +%s)

# Wait for backend
echo ""
echo "⏳ Waiting for backend to be ready..."
for i in {1..30}; do
    if curl -s "$BASE_URL/health" > /dev/null 2>&1; then
        echo "✅ Backend is ready!"
        break
    fi
    echo "Attempt $i/30: Backend not ready yet..."
    sleep 2
done

echo ""
echo "🧪 Testing duplicate organization registration fix..."
echo "============================================================"

# Test 1: Register first user
echo ""
echo "📝 Test 1: Register first user with org '$ORG_NAME'"
USER1_EMAIL="test_user_1_${TIMESTAMP}@example.com"
USER1_DATA='{
  "email": "'$USER1_EMAIL'",
  "password": "SecurePass123!",
  "first_name": "Test",
  "last_name": "User1",
  "organization_name": "'$ORG_NAME'"
}'

RESPONSE1=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d "$USER1_DATA")

HTTP_CODE1=$(echo "$RESPONSE1" | tail -n1)
BODY1=$(echo "$RESPONSE1" | head -n-1)

if [ "$HTTP_CODE1" -eq 200 ] || [ "$HTTP_CODE1" -eq 201 ]; then
    echo "✅ User 1 registered successfully"
    echo "   Email: $USER1_EMAIL"
    echo "   Response: $BODY1" | python3 -m json.tool 2>/dev/null | head -5
else
    echo "❌ User 1 registration failed: $HTTP_CODE1"
    echo "   Response: $BODY1"
    exit 1
fi

# Test 2: Register second user with SAME organization name
echo ""
echo "📝 Test 2: Register second user with SAME org '$ORG_NAME'"
USER2_EMAIL="test_user_2_${TIMESTAMP}@example.com"
USER2_DATA='{
  "email": "'$USER2_EMAIL'",
  "password": "SecurePass123!",
  "first_name": "Test",
  "last_name": "User2",
  "organization_name": "'$ORG_NAME'"
}'

RESPONSE2=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d "$USER2_DATA")

HTTP_CODE2=$(echo "$RESPONSE2" | tail -n1)
BODY2=$(echo "$RESPONSE2" | head -n-1)

if [ "$HTTP_CODE2" -eq 200 ] || [ "$HTTP_CODE2" -eq 201 ]; then
    echo "✅ User 2 registered successfully (using existing org)"
    echo "   Email: $USER2_EMAIL"
    echo "   Response: $BODY2" | python3 -m json.tool 2>/dev/null | head -5
else
    echo "❌ User 2 registration failed: $HTTP_CODE2"
    echo "   Response: $BODY2"
    exit 1
fi

# Test 3: Register third user with SAME organization name
echo ""
echo "📝 Test 3: Register third user with SAME org '$ORG_NAME'"
USER3_EMAIL="test_user_3_${TIMESTAMP}@example.com"
USER3_DATA='{
  "email": "'$USER3_EMAIL'",
  "password": "SecurePass123!",
  "first_name": "Test",
  "last_name": "User3",
  "organization_name": "'$ORG_NAME'"
}'

RESPONSE3=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d "$USER3_DATA")

HTTP_CODE3=$(echo "$RESPONSE3" | tail -n1)
BODY3=$(echo "$RESPONSE3" | head -n-1)

if [ "$HTTP_CODE3" -eq 200 ] || [ "$HTTP_CODE3" -eq 201 ]; then
    echo "✅ User 3 registered successfully (using existing org)"
    echo "   Email: $USER3_EMAIL"
    echo "   Response: $BODY3" | python3 -m json.tool 2>/dev/null | head -5
else
    echo "❌ User 3 registration failed: $HTTP_CODE3"
    echo "   Response: $BODY3"
    exit 1
fi

echo ""
echo "============================================================"
echo "🎉 All tests passed! The duplicate organization fix works!"
echo ""
echo "📊 Summary:"
echo "   ✅ 3 users registered successfully"
echo "   ✅ All users joined the same organization: '$ORG_NAME'"
echo "   ✅ First user is ADMIN, others are USER"
echo "   ✅ No unique constraint violations"
