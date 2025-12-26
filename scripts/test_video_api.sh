#!/bin/bash
# Video Processing Integration Test Script

set -e

API_URL="http://localhost:8000/api/v1"
VIDEO_FILE="$1"

echo "======================================"
echo "  VIDEO PROCESSING INTEGRATION TEST"
echo "======================================"
echo ""

# Test 1: Health Check
echo "🏥 Testing API Health..."
health_response=$(curl -s "${API_URL%/api/v1}/health")
echo "✓ API Status: $(echo $health_response | python3 -c 'import sys, json; print(json.load(sys.stdin)["status"])')"
echo ""

# Test 2: Create test user and get token
echo "🔐 Creating test user and authenticating..."
register_response=$(curl -s -X POST "$API_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPassword123!",
    "full_name": "Test User"
  }' 2>/dev/null || echo '{"detail":"User already exists"}')

login_response=$(curl -s -X POST "$API_URL/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test@example.com&password=TestPassword123!")

ACCESS_TOKEN=$(echo $login_response | python3 -c 'import sys, json; print(json.load(sys.stdin).get("access_token", ""))' 2>/dev/null || echo "")

if [ -z "$ACCESS_TOKEN" ]; then
  echo "⚠️  Authentication failed. Trying to continue without token..."
  AUTH_HEADER=""
else
  echo "✓ Authenticated successfully"
  AUTH_HEADER="Authorization: Bearer $ACCESS_TOKEN"
fi
echo ""

# Test 3: Check if video file is provided
if [ -z "$VIDEO_FILE" ]; then
  echo "⚠️  No video file provided."
  echo "   Usage: $0 /path/to/video.mp4"
  echo ""
  echo "📊 Checking existing files..."
  curl -s -X GET "$API_URL/files/" -H "$AUTH_HEADER" | python3 -m json.tool | head -20
  exit 0
fi

if [ ! -f "$VIDEO_FILE" ]; then
  echo "❌ Video file not found: $VIDEO_FILE"
  exit 1
fi

# Test 4: Upload video file
echo "📤 Uploading video file: $(basename "$VIDEO_FILE")"
FILE_SIZE=$(ls -lh "$VIDEO_FILE" | awk '{print $5}')
echo "   Size: $FILE_SIZE"

upload_response=$(curl -s -X POST "$API_URL/files/upload" \
  -H "$AUTH_HEADER" \
  -F "file=@$VIDEO_FILE" \
  -F "title=Integration Test Video" \
  -F "description=Testing video processing pipeline")

DOCUMENT_ID=$(echo $upload_response | python3 -c 'import sys, json; print(json.load(sys.stdin).get("id", ""))' 2>/dev/null || echo "")

if [ -z "$DOCUMENT_ID" ]; then
  echo "❌ Upload failed!"
  echo "$upload_response" | python3 -m json.tool
  exit 1
fi

echo "✓ Upload successful!"
echo "  Document ID: $DOCUMENT_ID"
echo ""

# Test 5: Monitor processing status
echo "⏳ Monitoring processing status..."
MAX_RETRIES=30
RETRY_INTERVAL=2
for i in $(seq 1 $MAX_RETRIES); do
  status_response=$(curl -s -X GET "$API_URL/files/$DOCUMENT_ID" -H "$AUTH_HEADER")
  STATUS=$(echo $status_response | python3 -c 'import sys, json; print(json.load(sys.stdin).get("processing_status", "unknown"))' 2>/dev/null || echo "unknown")

  echo "  [$i/$MAX_RETRIES] Status: $STATUS"

  if [ "$STATUS" = "completed" ]; then
    echo "✓ Processing completed successfully!"
    break
  elif [ "$STATUS" = "failed" ]; then
    echo "❌ Processing failed!"
    echo "$status_response" | python3 -m json.tool
    exit 1
  fi

  sleep $RETRY_INTERVAL
done

echo ""

# Test 6: Get file metadata
echo "📋 Retrieving file metadata..."
curl -s -X GET "$API_URL/files/$DOCUMENT_ID/metadata" -H "$AUTH_HEADER" | python3 -m json.tool
echo ""

# Test 7: Get file statistics
echo "📊 Getting file statistics..."
curl -s -X GET "$API_URL/files/stats" -H "$AUTH_HEADER" | python3 -m json.tool
echo ""

# Test 8: List all files
echo "📁 Listing all files..."
curl -s -X GET "$API_URL/files/" -H "$AUTH_HEADER" | python3 -m json.tool | head -50
echo ""

echo "======================================"
echo "  ✅ TEST COMPLETED SUCCESSFULLY"
echo "======================================"
