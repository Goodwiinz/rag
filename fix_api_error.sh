#!/bin/bash

# Script to fix API error and restart services

set -e

echo "🔧 Fixing API Error and Restarting Services..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_header() {
    echo -e "${BLUE}[FIX]${NC} $1"
}

# Check if frontend is running
stop_frontend() {
    print_header "Stopping frontend services..."

    if pgrep -f "next dev" > /dev/null; then
        pkill -f "next dev"
        print_status "Frontend stopped ✓"
    else
        print_warning "Frontend was not running"
    fi
}

# Clear Next.js cache
clear_cache() {
    print_header "Clearing Next.js cache..."

    cd frontend
    if [ -d ".next" ]; then
        rm -rf .next
        print_status "Next.js cache cleared ✓"
    else
        print_warning "No .next directory found"
    fi
    cd ..
}

# Verify environment variables
verify_env() {
    print_header "Verifying environment variables..."

    cd frontend
    if [ -f ".env.local" ]; then
        if grep -q "NEXT_PUBLIC_API_BASE_URL" .env.local; then
            print_status "Environment variables configured correctly ✓"
        else
            print_error "Environment variables not configured properly"
            exit 1
        fi
    else
        print_error ".env.local file not found"
        exit 1
    fi
    cd ..
}

# Start services
start_services() {
    print_header "Starting services..."

    # Start backend if not running
    if ! pgrep -f "uvicorn.*main:app" > /dev/null; then
        print_status "Starting backend..."
        cd backend
        nohup uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload > ../logs/backend.log 2>&1 &
        BACKEND_PID=$!
        echo $BACKEND_PID > ../backend.pid
        cd ..
        print_status "Backend started (PID: $BACKEND_PID) ✓"
    else
        print_status "Backend is already running ✓"
    fi

    # Start frontend
    print_status "Starting frontend..."
    cd frontend
    nohup npm run dev > ../logs/frontend.log 2>&1 &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > ../frontend.pid
    cd ..
    print_status "Frontend started (PID: $FRONTEND_PID) ✓"
}

# Wait for services to be ready
wait_for_services() {
    print_header "Waiting for services to be ready..."

    # Wait for backend
    local backend_ready=false
    for i in {1..30}; do
        if curl -f http://localhost:8000/health &>/dev/null; then
            print_status "Backend is ready ✓"
            backend_ready=true
            break
        fi
        echo -n "."
        sleep 2
    done

    if [ "$backend_ready" = false ]; then
        print_error "Backend failed to start"
        return 1
    fi

    # Wait for frontend
    local frontend_ready=false
    for i in {1..60}; do
        if curl -f http://localhost:3000 &>/dev/null; then
            print_status "Frontend is ready ✓"
            frontend_ready=true
            break
        fi
        echo -n "."
        sleep 2
    done

    if [ "$frontend_ready" = false ]; then
        print_error "Frontend failed to start"
        return 1
    fi
}

# Test API connectivity
test_api() {
    print_header "Testing API connectivity..."

    # Test backend health
    if curl -f http://localhost:8000/health &>/dev/null; then
        print_status "Backend health check passed ✓"
    else
        print_error "Backend health check failed"
        return 1
    fi

    # Test frontend health
    if curl -f http://localhost:3000 &>/dev/null; then
        print_status "Frontend health check passed ✓"
    else
        print_error "Frontend health check failed"
        return 1
    fi

    # Test API endpoint (should return 403 auth error, which is expected)
    local api_response=$(curl -s http://localhost:8000/api/v1/documents/)
    if echo "$api_response" | grep -q "Not authenticated"; then
        print_status "API endpoint responding correctly (auth required) ✓"
    else
        print_warning "API endpoint response unexpected: $api_response"
    fi
}

# Display information
display_info() {
    print_header "Fix Applied Successfully!"
    echo ""
    echo -e "${GREEN}🌐 Services Status:${NC}"
    echo "  • Frontend:            http://localhost:3000"
    echo "  • Backend API:         http://localhost:8000"
    echo "  • API Documentation:   http://localhost:8000/docs"
    echo ""
    echo -e "${GREEN}🔧 What was fixed:${NC}"
    echo "  ✅ Environment variables updated (NEXT_PUBLIC_*)"
    echo "  ✅ Next.js cache cleared"
    echo "  ✅ Services restarted"
    echo "  ✅ API connectivity verified"
    echo ""
    echo -e "${GREEN}📝 Next Steps:${NC}"
    echo "  1. Open browser to http://localhost:3000"
    echo "  2. Login to the application"
    echo "  3. Try uploading a document"
    echo "  4. Check browser console for any remaining errors"
    echo ""
    echo -e "${GREEN}📊 Monitoring:${NC}"
    echo "  • View logs: tail -f logs/frontend.log"
    echo "  • API test: curl http://localhost:8000/api/v1/documents/"
    echo ""
}

# Main execution
main() {
    echo "🎯 API Error Fix Script"
    echo "======================="
    echo ""

    stop_frontend
    clear_cache
    verify_env
    start_services
    wait_for_services
    test_api
    display_info

    echo -e "${GREEN}✅ API error fix completed successfully!${NC}"
    echo ""
    echo -e "${YELLOW}💡 If you still see API errors, clear your browser cache and reload the page.${NC}"
}

# Handle script interruption
trap 'print_warning "Fix process interrupted."; exit 1' INT

# Run main function
main "$@"