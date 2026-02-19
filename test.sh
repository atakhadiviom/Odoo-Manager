#!/bin/bash
# Test script for Odoo Manager
# Tests each major feature one by one

echo "=========================================="
echo "Odoo Manager Test Suite"
echo "=========================================="
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS_COUNT=0
FAIL_COUNT=0

# Test function
test_step() {
    local name="$1"
    local command="$2"

    echo -n "Testing: $name ... "

    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}PASS${NC}"
        ((PASS_COUNT++))
        return 0
    else
        echo -e "${RED}FAIL${NC}"
        ((FAIL_COUNT++))
        return 1
    fi
}

# Check if odoo-manager is installed
echo "1. Checking Installation..."
echo "----------------------------"

if command -v odoo-manager &> /dev/null; then
    echo -e "${GREEN}✓${NC} odoo-manager command found"
    ODOO_CMD="odoo-manager"
elif [ -f "$HOME/.local/bin/odoo-manager" ]; then
    echo -e "${YELLOW}!${NC} odoo-manager found in ~/.local/bin (not in PATH)"
    ODOO_CMD="$HOME/.local/bin/odoo-manager"
else
    echo -e "${RED}✗${NC} odoo-manager not found"
    exit 1
fi
echo ""

# Test help command
echo "2. Testing Basic Commands"
echo "----------------------------"
test_step "Help command" "$ODOO_CMD --help"
test_step "Version command" "$ODOO_CMD version"
echo ""

# Test config commands
echo "3. Testing Config Commands"
echo "----------------------------"
test_step "Config init" "$ODOO_CMD config init"
test_step "Config show" "$ODOO_CMD config show"
test_step "Config path" "$ODOO_CMD config path"
echo ""

# Test instance commands
echo "4. Testing Instance Commands"
echo "----------------------------"
test_step "Instance list" "$ODOO_CMD instance list"
echo ""

# Create a test instance
echo "5. Creating Test Instance"
echo "----------------------------"
echo "Creating instance 'test-instance'..."
if $ODOO_CMD instance create test-instance --version 17.0 --port 8099 2>&1 | grep -q "Created\|Success\|test-instance"; then
    echo -e "${GREEN}✓ Test instance created${NC}"
    ((PASS_COUNT++))
else
    echo -e "${RED}✗ Failed to create test instance${NC}"
    ((FAIL_COUNT++))
fi
echo ""

# Test instance status
echo "6. Testing Instance Operations"
echo "----------------------------"
test_step "Instance list (with test instance)" "$ODOO_CMD instance list"
test_step "Instance status" "$ODOO_CMD instance status test-instance"
test_step "Instance info" "$ODOO_CMD instance info test-instance"
echo ""

# Test database commands
echo "7. Testing Database Commands"
echo "----------------------------"
test_step "Database list" "$ODOO_CMD db list --instance test-instance"
echo ""

# Test git commands
echo "8. Testing Git Commands"
echo "----------------------------"
test_step "Git list repos" "$ODOO_CMD git list"
echo ""

# Test environment commands
echo "9. Testing Environment Commands"
echo "----------------------------"
test_step "Environment list" "$ODOO_CMD env list"
echo ""

# Test backup commands
echo "10. Testing Backup Commands"
echo "----------------------------"
test_step "Backup list" "$ODOO_CMD backup list"
echo ""

# Test user commands
echo "11. Testing User Commands"
echo "----------------------------"
test_step "User list" "$ODOO_CMD user list"
echo ""

# Test scheduler commands
echo "12. Testing Scheduler Commands"
echo "----------------------------"
test_step "Scheduler status" "$ODOO_CMD scheduler status"
echo ""

# Clean up test instance
echo "13. Cleaning Up"
echo "----------------------------"
echo "Removing test instance..."
if $ODOO_CMD instance rm test-instance --force 2>&1 | grep -q "Removed\|deleted\|Success"; then
    echo -e "${GREEN}✓ Test instance removed${NC}"
    ((PASS_COUNT++))
else
    echo -e "${YELLOW}!${NC} Could not remove test instance (may not exist or already removed)"
fi
echo ""

# Summary
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo -e "Passed: ${GREEN}$PASS_COUNT${NC}"
echo -e "Failed: ${RED}$FAIL_COUNT${NC}"
TOTAL=$((PASS_COUNT + FAIL_COUNT))
echo "Total: $TOTAL"
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed.${NC}"
    exit 1
fi
