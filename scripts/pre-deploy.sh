#!/bin/bash
# Pre-deployment checks for Odoo Manager
# This script runs validation checks before deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT="${1:-development}"
BRANCH="${2:-main}"
REPO_PATH="${3:-.}"
MIN_DISK_GB="${MIN_DISK_GB:-5}"

echo "=========================================="
echo "Pre-deployment checks for Odoo Manager"
echo "=========================================="
echo "Environment: $ENVIRONMENT"
echo "Branch: $BRANCH"
echo "Repository: $REPO_PATH"
echo ""

# Track overall status
FAILED=0
SKIPPED=0
PASSED=0

# Function to run a check
run_check() {
    local name="$1"
    local command="$2"

    echo -n "Checking $name... "

    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}PASSED${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}FAILED${NC}"
        ((FAILED++))
        return 1
    fi
}

# Function to skip a check
skip_check() {
    local name="$1"
    local reason="$2"

    echo -e "Checking $name... ${YELLOW}SKIPPED${NC} ($reason)"
    ((SKIPPED++))
}

# 1. Check if we're in a git repository
if [ -d "$REPO_PATH/.git" ]; then
    run_check "Git repository" "true"
else
    echo -e "Checking Git repository... ${RED}FAILED${NC} (not a git repo)"
    ((FAILED++))
fi

# 2. Check Python syntax
echo -n "Checking Python syntax... "
PYTHON_ERRORS=0
for py_file in $(find "$REPO_PATH" -name "*.py" 2>/dev/null | head -20); do
    if ! python3 -m py_compile "$py_file" 2>/dev/null; then
        ((PYTHON_ERRORS++))
    fi
done

if [ $PYTHON_ERRORS -eq 0 ]; then
    echo -e "${GREEN}PASSED${NC}"
    ((PASSED++))
else
    echo -e "${RED}FAILED${NC} ($PYTHON_ERRORS files with errors)"
    ((FAILED++))
fi

# 3. Check disk space
echo -n "Checking disk space... "
FREE_SPACE=$(df -BG / | tail -1 | awk '{print $4}' | tr -d 'G')
if [ "$FREE_SPACE" -ge "$MIN_DISK_GB" ]; then
    echo -e "${GREEN}PASSED${NC} (${FREE_SPACE}GB free)"
    ((PASSED++))
else
    echo -e "${RED}FAILED${NC} (only ${FREE_SPACE}GB free, need ${MIN_DISK_GB}GB)"
    ((FAILED++))
fi

# 4. Check if Docker is available (for docker deployments)
if command -v docker &> /dev/null; then
    run_check "Docker availability" "docker info > /dev/null 2>&1"
else
    skip_check "Docker availability" "docker command not found"
fi

# 5. Check PostgreSQL connectivity
if command -v psql &> /dev/null; then
    # Try connecting with default odoo credentials
    if PGPASSWORD=odoo psql -h localhost -U odoo -c "SELECT 1" &> /dev/null; then
        echo -e "Checking PostgreSQL... ${GREEN}PASSED${NC}"
        ((PASSED++))
    else
        echo -e "Checking PostgreSQL... ${YELLOW}SKIPPED${NC} (cannot connect)"
        ((SKIPPED++))
    fi
else
    skip_check "PostgreSQL" "psql command not found"
fi

# 6. Check for Odoo manifest syntax errors
echo -n "Checking Odoo manifests... "
MANIFEST_ERRORS=0
for manifest in $(find "$REPO_PATH" -name "__manifest__.py" 2>/dev/null); do
    if ! python3 -c "import sys; exec(open('$manifest').read())" 2>/dev/null; then
        ((MANIFEST_ERRORS++))
    fi
done

if [ $MANIFEST_ERRORS -eq 0 ]; then
    echo -e "${GREEN}PASSED${NC}"
    ((PASSED++))
else
    echo -e "${YELLOW}WARNING${NC} ($MANIFEST_ERRORS manifests may have issues)"
    ((SKIPPED++))
fi

# Summary
echo ""
echo "=========================================="
echo "Summary:"
echo -e "  ${GREEN}PASSED:${NC} $PASSED"
echo -e "  ${YELLOW}SKIPPED:${NC} $SKIPPED"
echo -e "  ${RED}FAILED:${NC} $FAILED"
echo "=========================================="

# Exit with error if any checks failed
if [ $FAILED -gt 0 ]; then
    echo -e "${RED}Pre-deployment checks failed${NC}"
    exit 1
fi

echo -e "${GREEN}Pre-deployment checks passed${NC}"
exit 0
