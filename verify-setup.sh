#!/bin/bash

# Setup Verification Script
# Checks all prerequisites and configurations

set -e

RESET='\033[0m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'

echo -e "${BLUE}═══════════════════════════════════════════════════════════${RESET}"
echo -e "${BLUE}  FlyRank Billing Engine - Setup Verification${RESET}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${RESET}\n"

CHECKS_PASSED=0
CHECKS_FAILED=0
CHECKS_WARNING=0

check_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ PASS${RESET}: $2"
        ((CHECKS_PASSED++))
    elif [ $1 -eq 2 ]; then
        echo -e "${YELLOW}⚠️  WARN${RESET}: $2"
        ((CHECKS_WARNING++))
    else
        echo -e "${RED}❌ FAIL${RESET}: $2"
        ((CHECKS_FAILED++))
    fi
}

echo -e "${BLUE}1. System Requirements${RESET}"
echo "─────────────────────────────────────────────"

# Check Docker
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version | awk '{print $3}' | cut -d',' -f1)
    check_result 0 "Docker installed (v$DOCKER_VERSION)"
else
    check_result 1 "Docker not installed (required)"
fi

# Check Docker Compose
if command -v docker-compose &> /dev/null; then
    DC_VERSION=$(docker-compose --version | awk '{print $4}' | cut -d',' -f1)
    check_result 0 "Docker Compose installed (v$DC_VERSION)"
elif command -v docker &> /dev/null && docker compose version &> /dev/null; then
    check_result 0 "Docker Compose v2 available"
else
    check_result 1 "Docker Compose not installed (required)"
fi

# Check Git
if command -v git &> /dev/null; then
    check_result 0 "Git installed"
else
    check_result 2 "Git not installed (recommended)"
fi

# Check curl
if command -v curl &> /dev/null; then
    check_result 0 "curl installed"
else
    check_result 1 "curl not installed (required)"
fi

echo -e "\n${BLUE}2. Project Structure${RESET}"
echo "─────────────────────────────────────────────"

# Check required directories
for dir in backend frontend alembic docs; do
    if [ -d "$dir" ]; then
        check_result 0 "Directory exists: $dir/"
    else
        check_result 1 "Missing directory: $dir/"
    fi
done

# Check required files
for file in README.md capstone.yaml docker-compose.yml LICENSE .env.example .gitignore; do
    if [ -f "$file" ]; then
        check_result 0 "File exists: $file"
    else
        check_result 1 "Missing file: $file"
    fi
done

echo -e "\n${BLUE}3. Configuration Files${RESET}"
echo "─────────────────────────────────────────────"

# Check .env file
if [ -f ".env" ]; then
    check_result 0 "Configuration file (.env) exists"
    
    # Check Stripe keys
    if grep -q "STRIPE_API_KEY=sk_test_" .env; then
        check_result 0 "Stripe API key configured"
    else
        check_result 2 "Stripe API key not set (needed for payment tests)"
    fi
    
    if grep -q "STRIPE_WEBHOOK_SECRET=whsec_" .env; then
        check_result 0 "Stripe webhook secret configured"
    else
        check_result 2 "Stripe webhook secret not set (needed for webhook tests)"
    fi
    
    # Check database URL
    if grep -q "DATABASE_URL=" .env; then
        check_result 0 "Database URL configured"
    else
        check_result 1 "Database URL not configured"
    fi
else
    check_result 2 "Configuration file (.env) not found"
    echo "   → Run: cp .env.example .env"
fi

echo -e "\n${BLUE}4. Backend Setup${RESET}"
echo "─────────────────────────────────────────────"

# Check backend Python
if [ -f "backend/requirements.txt" ]; then
    check_result 0 "Backend requirements.txt exists"
else
    check_result 1 "Missing: backend/requirements.txt"
fi

# Check backend main app
if [ -f "backend/app/main.py" ]; then
    check_result 0 "Backend main.py exists"
else
    check_result 1 "Missing: backend/app/main.py"
fi

# Check models
if [ -f "backend/app/models.py" ]; then
    check_result 0 "Database models exist"
else
    check_result 1 "Missing: backend/app/models.py"
fi

# Check tests
if [ -f "backend/tests/test_idempotency.py" ]; then
    check_result 0 "Test suite exists"
else
    check_result 2 "Test suite not found (optional but recommended)"
fi

echo -e "\n${BLUE}5. Frontend Setup${RESET}"
echo "─────────────────────────────────────────────"

# Check frontend files
if [ -f "frontend/package.json" ]; then
    check_result 0 "Frontend package.json exists"
else
    check_result 1 "Missing: frontend/package.json"
fi

if [ -f "frontend/src/App.tsx" ]; then
    check_result 0 "React App component exists"
else
    check_result 1 "Missing: frontend/src/App.tsx"
fi

if [ -f "frontend/vite.config.ts" ]; then
    check_result 0 "Vite configuration exists"
else
    check_result 1 "Missing: frontend/vite.config.ts"
fi

echo -e "\n${BLUE}6. Database Setup${RESET}"
echo "─────────────────────────────────────────────"

# Check migrations
if [ -d "alembic/versions" ]; then
    MIGRATION_COUNT=$(find alembic/versions -name "*.py" -type f | wc -l)
    check_result 0 "Alembic migrations ($MIGRATION_COUNT files)"
else
    check_result 1 "Missing: alembic/versions/"
fi

if [ -f "alembic/env.py" ]; then
    check_result 0 "Alembic environment configured"
else
    check_result 1 "Missing: alembic/env.py"
fi

echo -e "\n${BLUE}7. Docker Configuration${RESET}"
echo "─────────────────────────────────────────────"

# Check docker-compose syntax
if docker-compose config > /dev/null 2>&1; then
    check_result 0 "docker-compose.yml is valid"
else
    check_result 1 "docker-compose.yml has errors"
fi

# Check Dockerfile
if [ -f "Dockerfile.backend" ]; then
    check_result 0 "Backend Dockerfile exists"
else
    check_result 1 "Missing: Dockerfile.backend"
fi

if [ -f "frontend/Dockerfile" ]; then
    check_result 0 "Frontend Dockerfile exists"
else
    check_result 1 "Missing: frontend/Dockerfile"
fi

echo -e "\n${BLUE}8. Documentation${RESET}"
echo "─────────────────────────────────────────────"

# Check documentation files
for doc in "README.md" "docs/API.md" "docs/DEPLOYMENT.md" "EVIDENCE.md"; do
    if [ -f "$doc" ]; then
        check_result 0 "Documentation: $doc"
    else
        check_result 2 "Missing doc: $doc (optional but helpful)"
    fi
done

echo -e "\n${BLUE}9. Port Availability${RESET}"
echo "─────────────────────────────────────────────"

# Check if ports are available (or will be after docker-compose)
for port in 3000 8000 5432 80; do
    if ! nc -z 127.0.0.1 $port 2>/dev/null; then
        check_result 0 "Port $port is available"
    else
        check_result 2 "Port $port is already in use"
    fi
done

echo -e "\n${BLUE}10. File Permissions${RESET}"
echo "─────────────────────────────────────────────"

# Check if files are readable
if [ -r "README.md" ] && [ -r "docker-compose.yml" ]; then
    check_result 0 "Files have proper permissions"
else
    check_result 1 "Some files are not readable"
fi

# Check if .gitignore exists and is configured
if [ -f ".gitignore" ] && grep -q ".env" .gitignore; then
    check_result 0 ".env is in .gitignore (secrets protected)"
else
    check_result 2 ".env might not be properly ignored"
fi

echo -e "\n${BLUE}═══════════════════════════════════════════════════════════${RESET}"
echo -e "${BLUE}VERIFICATION SUMMARY${RESET}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${RESET}\n"

echo -e "${GREEN}✅ Passed${RESET}: $CHECKS_PASSED"
echo -e "${YELLOW}⚠️  Warnings${RESET}: $CHECKS_WARNING"
echo -e "${RED}❌ Failed${RESET}: $CHECKS_FAILED"

echo ""

if [ $CHECKS_FAILED -eq 0 ]; then
    if [ $CHECKS_WARNING -eq 0 ]; then
        echo -e "${GREEN}✅ All checks passed! System is ready.${RESET}\n"
        echo -e "${BLUE}Next steps:${RESET}"
        echo "  1. docker-compose up -d"
        echo "  2. docker-compose exec backend pytest tests/ -v  (run tests)"
        echo "  3. Open http://localhost:3000 in browser"
        echo ""
        exit 0
    else
        echo -e "${YELLOW}⚠️  All critical checks passed, but review warnings above.${RESET}\n"
        echo -e "${BLUE}Next steps:${RESET}"
        echo "  1. docker-compose up -d"
        echo "  2. Open http://localhost:3000 in browser"
        echo ""
        exit 0
    fi
else
    echo -e "${RED}❌ System is not ready. Fix the failures above.${RESET}\n"
    echo -e "${BLUE}Common fixes:${RESET}"
    echo "  • Install Docker: https://docs.docker.com/get-docker/"
    echo "  • Copy config: cp .env.example .env"
    echo "  • Add Stripe keys to .env"
    echo ""
    exit 1
fi
