#!/bin/bash
# Comprehensive verification script for all fixes

echo "🔍 RAG System - Comprehensive Fix Verification"
echo "============================================================"
echo ""

BASE_URL="http://localhost:8000"
PASSED=0
FAILED=0

# Function to print test result
print_result() {
    if [ $1 -eq 0 ]; then
        echo "✅ PASS: $2"
        ((PASSED++))
    else
        echo "❌ FAIL: $2"
        ((FAILED++))
    fi
}

# Test 1: Check backend is running
echo "📝 Test 1: Backend Health Check"
HEALTH_RESPONSE=$(curl -s http://localhost:8000/health)
if echo "$HEALTH_RESPONSE" | grep -q "healthy"; then
    print_result 0 "Backend is running and healthy"
else
    print_result 1 "Backend is not healthy"
fi
echo ""

# Test 2: Registration with duplicate organization
echo "📝 Test 2: Registration with Duplicate Organization Name"
TIMESTAMP=$(date +%s)
ORG_NAME="Test Organization"

# Register user 1
USER1_EMAIL="test1_${TIMESTAMP}@example.com"
REG1_DATA=$(cat <<EOF
{"email":"$USER1_EMAIL","password":"SecurePass123!","first_name":"User","last_name":"One","organization_name":"$ORG_NAME"}
EOF
)
REG1_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d "$REG1_DATA")

HTTP_CODE1=$(echo "$REG1_RESPONSE" | tail -n1)
if [ "$HTTP_CODE1" = "200" ] || [ "$HTTP_CODE1" = "201" ]; then
    print_result 0 "First user registered successfully"
else
    print_result 1 "First user registration failed (HTTP $HTTP_CODE1)"
fi

# Register user 2 with SAME org name
USER2_EMAIL="test2_${TIMESTAMP}@example.com"
REG2_DATA=$(cat <<EOF
{"email":"$USER2_EMAIL","password":"SecurePass123!","first_name":"User","last_name":"Two","organization_name":"$ORG_NAME"}
EOF
)
REG2_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d "$REG2_DATA")

HTTP_CODE2=$(echo "$REG2_RESPONSE" | tail -n1)
if [ "$HTTP_CODE2" = "200" ] || [ "$HTTP_CODE2" = "201" ]; then
    print_result 0 "Second user registered with same org name"
else
    print_result 1 "Second user registration failed (HTTP $HTTP_CODE2)"
fi
echo ""

# Test 3: Login and get token
echo "📝 Test 3: Authentication"
LOGIN_DATA=$(cat <<EOF
{"email":"$USER1_EMAIL","password":"SecurePass123!"}
EOF
)
LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "$LOGIN_DATA")

TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null)

if [ -n "$TOKEN" ]; then
    print_result 0 "Login successful, token obtained"
else
    print_result 1 "Login failed or token not obtained"
fi
echo ""

# Test 4: Workers Status Endpoint
echo "📝 Test 4: Workers Status Endpoint"
if [ -n "$TOKEN" ]; then
    WORKERS_RESPONSE=$(curl -s -X GET "$BASE_URL/api/v1/workers/status" \
      -H "Authorization: Bearer $TOKEN")

    if echo "$WORKERS_RESPONSE" | grep -q "active_workers"; then
        print_result 0 "Workers status endpoint working"

        # Check if workers are online
        ACTIVE_WORKERS=$(echo "$WORKERS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('active_workers', 0))" 2>/dev/null)
        if [ "$ACTIVE_WORKERS" -gt 0 ]; then
            print_result 0 "Workers are online (count: $ACTIVE_WORKERS)"
        else
            print_result 1 "No workers online"
        fi
    else
        print_result 1 "Workers status endpoint failed"
    fi
else
    print_result 1 "Skipped (no auth token)"
fi
echo ""

# Test 5: Workers Health Endpoint
echo "📝 Test 5: Workers Health Endpoint"
if [ -n "$TOKEN" ]; then
    HEALTH_RESPONSE=$(curl -s -X GET "$BASE_URL/api/v1/workers/health" \
      -H "Authorization: Bearer $TOKEN")

    if echo "$HEALTH_RESPONSE" | grep -q "healthy"; then
        IS_HEALTHY=$(echo "$HEALTH_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('healthy', False))" 2>/dev/null)
        if [ "$IS_HEALTHY" = "True" ]; then
            print_result 0 "Workers are healthy"
        else
            print_result 1 "Workers are unhealthy"
        fi
    else
        print_result 1 "Workers health endpoint failed"
    fi
else
    print_result 1 "Skipped (no auth token)"
fi
echo ""

# Test 6: API Documentation
echo "📝 Test 6: API Documentation"
DOCS_RESPONSE=$(curl -s http://localhost:8000/docs)
if echo "$DOCS_RESPONSE" | grep -q "Swagger"; then
    print_result 0 "API documentation accessible"
else
    print_result 1 "API documentation not accessible"
fi
echo ""

# Summary
echo "============================================================"
echo "📊 Test Summary"
echo "============================================================"
echo "Total Tests: $((PASSED + FAILED))"
echo "✅ Passed: $PASSED"
echo "❌ Failed: $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "🎉 All tests PASSED! System is fully operational."
    echo ""
    echo "✅ Registration fix verified"
    echo "✅ Workers monitoring verified"
    echo "✅ Authentication verified"
    echo "✅ System health verified"
    exit 0
else
    echo "⚠️ Some tests FAILED. Please review the output above."
    exit 1
fi
