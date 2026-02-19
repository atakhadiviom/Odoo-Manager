#!/bin/bash
# Comprehensive Test Suite for Odoo Manager
# Tests all functionality one by one

echo "=========================================="
echo "Odoo Manager Comprehensive Test Suite"
echo "=========================================="
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0
TEST_INSTANCE="test-odoo-instance"
TEST_DB="test_db"

# Get odoo-manager command path
if command -v odoo-manager &> /dev/null; then
    ODOO_CMD="odoo-manager"
elif [ -f "$HOME/.local/bin/odoo-manager" ]; then
    ODOO_CMD="$HOME/.local/bin/odoo-manager"
else
    echo -e "${RED}ERROR: odoo-manager not found${NC}"
    exit 1
fi

echo -e "${CYAN}Using command: $ODOO_CMD${NC}"
echo ""

# Test function
test_step() {
    local name="$1"
    local command="$2"
    local expected="${3:-0}"  # Expected exit code (default 0)

    echo -n "Testing: $name ... "

    if eval "$command" > /tmp/test_output.txt 2>&1; then
        if [ "$expected" = "0" ]; then
            echo -e "${GREEN}PASS${NC}"
            ((PASS_COUNT++))
            return 0
        fi
    fi

    # Check if error was expected
    actual_exit=$?
    if [ "$actual_exit" = "$expected" ]; then
        echo -e "${GREEN}PASS (expected failure)${NC}"
        ((PASS_COUNT++))
        return 0
    fi

    echo -e "${RED}FAIL${NC}"
    echo -e "${YELLOW}  Output: $(cat /tmp/test_output.txt | head -1)${NC}"
    ((FAIL_COUNT++))
    return 1
}

# Test function that checks output contains expected text
test_step_contains() {
    local name="$1"
    local command="$2"
    local expected_text="$3"

    echo -n "Testing: $name ... "

    if eval "$command" > /tmp/test_output.txt 2>&1; then
        if grep -q "$expected_text" /tmp/test_output.txt; then
            echo -e "${GREEN}PASS${NC}"
            ((PASS_COUNT++))
            return 0
        else
            echo -e "${RED}FAIL (expected text not found)${NC}"
            echo -e "${YELLOW}  Expected: $expected_text${NC}"
            ((FAIL_COUNT++))
            return 1
        fi
    else
        echo -e "${RED}FAIL (command failed)${NC}"
        echo -e "${YELLOW}  Output: $(cat /tmp/test_output.txt | head -1)${NC}"
        ((FAIL_COUNT++))
        return 1
    fi
}

# Cleanup function
cleanup() {
    echo ""
    echo -e "${BLUE}Cleaning up test resources...${NC}"

    # Remove test instance if exists
    $ODOO_CMD instance rm $TEST_INSTANCE --force > /dev/null 2>&1

    # Remove test database if exists
    $ODOO_CMD db drop $TEST_DB --instance $TEST_INSTANCE --force > /dev/null 2>&1

    echo -e "${GREEN}✓ Cleanup complete${NC}"
}

# Set trap for cleanup on exit
trap cleanup EXIT

# ============================================
# 1. BASIC COMMAND TESTS
# ============================================
echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}1. BASIC COMMAND TESTS${NC}"
echo -e "${BLUE}==========================================${NC}"

test_step "Help command" "$ODOO_CMD --help"
test_step "Version command" "$ODOO_CMD version"
test_step "Menu command (exit quickly)" "echo 'Q' | $ODOO_CMD menu"
echo ""

# ============================================
# 2. CONFIGURATION TESTS
# ============================================
echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}2. CONFIGURATION TESTS${NC}"
echo -e "${BLUE}==========================================${NC}"

test_step "Config init" "$ODOO_CMD config init"
test_step_contains "Config show" "$ODOO_CMD config show" "settings"
test_step_contains "Config path" "$ODOO_CMD config path" ".config"
echo ""

# ============================================
# 3. INSTANCE TESTS
# ============================================
echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}3. INSTANCE TESTS${NC}"
echo -e "${BLUE}==========================================${NC}"

test_step_contains "Instance list (empty)" "$ODOO_CMD instance list" "instances"

echo -e "${YELLOW}Creating test instance...${NC}"
if $ODOO_CMD instance create $TEST_INSTANCE --version 17.0 --port 8999 --workers 2 > /tmp/test_output.txt 2>&1; then
    echo -e "${GREEN}✓ Test instance created${NC}"
    ((PASS_COUNT++))
else
    echo -e "${RED}✗ Failed to create instance${NC}"
    cat /tmp/test_output.txt
    ((FAIL_COUNT++))
    # Skip remaining tests that depend on instance
    SKIP_COUNT=$((SKIP_COUNT + 20))
    echo ""
    echo -e "${RED}Skipping tests that require a working instance${NC}"
    cleanup
    exit $FAIL_COUNT
fi

test_step_contains "Instance list (with instance)" "$ODOO_CMD instance list" "$TEST_INSTANCE"
test_step_contains "Instance status" "$ODOO_CMD instance status $TEST_INSTANCE" "stopped"
test_step_contains "Instance info" "$ODOO_CMD instance info $TEST_INSTANCE" "version"
echo ""

# ============================================
# 4. DATABASE TESTS
# ============================================
echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}4. DATABASE TESTS${NC}"
echo -e "${BLUE}==========================================${NC}"

# Note: Database operations require PostgreSQL
test_step_contains "Database list" "$ODOO_CMD db list --instance $TEST_INSTANCE" "database"

echo -e "${YELLOW}Note: Skip create/drop database tests (require running PostgreSQL)${NC}"
((SKIP_COUNT=$((SKIP_COUNT + 3))))
echo ""

# ============================================
# 5. MODULE TESTS
# ============================================
echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}5. MODULE TESTS${NC}"
echo -e "${BLUE}==========================================${NC}"

echo -e "${YELLOW}Note: Module tests require running Odoo instance${NC}"
((SKIP_COUNT=$((SKIP_COUNT + 4))))
echo ""

# ============================================
# 6. BACKUP TESTS
# ============================================
echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}6. BACKUP TESTS${NC}"
echo -e "${BLUE}==========================================${NC}"

test_step_contains "Backup list" "$ODOO_CMD backup list" "backups"
echo ""

# ============================================
# 7. GIT TESTS
# ============================================
echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}7. GIT TESTS${NC}"
echo -e "${BLUE}==========================================${NC}"

test_step_contains "Git list repos" "$ODOO_CMD git list" "repositories"
echo ""

# ============================================
# 8. ENVIRONMENT TESTS
# ============================================
echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}8. ENVIRONMENT TESTS${NC}"
echo -e "${BLUE}==========================================${NC}"

test_step_contains "Environment list" "$ODOO_CMD env list" "environments"
echo ""

# ============================================
# 9. DEPLOY TESTS
# ============================================
echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}9. DEPLOY TESTS${NC}"
echo -e "${BLUE}==========================================${NC}"

test_step_contains "Deploy list/history" "$ODOO_CMD deploy list" "deployment" "1"
echo ""

# ============================================
# 10. MONITOR TESTS
# ============================================
echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}10. MONITOR TESTS${NC}"
echo -e "${BLUE}==========================================${NC}"

test_step_contains "Monitor status" "$ODOO_CMD monitor status" "instances"
echo ""

# ============================================
# 11. SCHEDULER TESTS
# ============================================
echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}11. SCHEDULER TESTS${NC}"
echo -e "${BLUE}==========================================${NC}"

test_step_contains "Scheduler status" "$ODOO_CMD scheduler status" "scheduler"
test_step_contains "Scheduler list tasks" "$ODOO_CMD scheduler list" "tasks"
echo ""

# ============================================
# 12. USER TESTS
# ============================================
echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}12. USER TESTS${NC}"
echo -e "${BLUE}==========================================${NC}"

test_step_contains "User list" "$ODOO_CMD user list" "users"
echo ""

# ============================================
# 13. SSL TESTS
# ============================================
echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}13. SSL TESTS${NC}"
echo -e "${BLUE}==========================================${NC}"

test_step_contains "SSL status" "$ODOO_CMD ssl status" "certificate" "1"
echo ""

# ============================================
# 14. LOGS TESTS
# ============================================
echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}14. LOGS TESTS${NC}"
echo -e "${BLUE}==========================================${NC}"

echo -e "${YELLOW}Note: Log tests require running instance${NC}"
((SKIP_COUNT=$((SKIP_COUNT + 2))))
echo ""

# ============================================
# 15. TUI TESTS
# ============================================
echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}15. TUI TESTS${NC}"
echo -e "${BLUE}==========================================${NC}"

echo -e "${YELLOW}Note: TUI test skipped (requires interactive terminal)${NC}"
((SKIP_COUNT=$((SKIP_COUNT + 1))))
echo ""

# ============================================
# 16. CLEANUP TESTS
# ============================================
echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}16. CLEANUP TESTS${NC}"
echo -e "${BLUE}==========================================${NC}"

test_step_contains "Remove test instance" "$ODOO_CMD instance rm $TEST_INSTANCE --force" "removed" "deleted"
echo ""

# ============================================
# TEST SUMMARY
# ============================================
echo ""
echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}TEST SUMMARY${NC}"
echo -e "${BLUE}==========================================${NC}"
echo -e "Passed:  ${GREEN}$PASS_COUNT${NC}"
echo -e "Failed:  ${RED}$FAIL_COUNT${NC}"
echo -e "Skipped: ${YELLOW}$SKIP_COUNT${NC}"
TOTAL=$((PASS_COUNT + FAIL_COUNT + SKIP_COUNT))
echo -e "Total:   $TOTAL"
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
    echo -e "${GREEN}==========================================${NC}"
    echo -e "${GREEN}ALL TESTS PASSED!${NC}"
    echo -e "${GREEN}==========================================${NC}"
    exit 0
else
    echo -e "${RED}==========================================${NC}"
    echo -e "${RED}SOME TESTS FAILED${NC}"
    echo -e "${RED}==========================================${NC}"
    exit 1
fi
