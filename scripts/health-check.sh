#!/bin/bash
# Health check script for Odoo instances
# Returns exit code 0 if healthy, 1 if unhealthy, 2 if critical

set -e

# Configuration
INSTANCE_NAME="${1:-odoo}"
PORT="${2:-8069}"
DB_HOST="${3:-localhost}"
DB_PORT="${4:-5432}"

# Check function
check() {
    local name="$1"
    local command="$2"

    if eval "$command" > /dev/null 2>&1; then
        echo "✓ $name"
        return 0
    else
        echo "✗ $name"
        return 1
    fi
}

# Track status
STATUS=0
WARNING=0

echo "Health check for: $INSTANCE_NAME"
echo "=================================="

# 1. Check if instance port is listening
if ! check "Port $PORT is listening" "nc -z localhost $PORT"; then
    STATUS=2
fi

# 2. Check HTTP endpoint
if command -v curl &> /dev/null; then
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$PORT/web/login || echo "000")
    if [ "$HTTP_CODE" = "000" ]; then
        echo "✗ HTTP endpoint not responding"
        STATUS=2
    elif [ "$HTTP_CODE" != "200" ] && [ "$HTTP_CODE" != "302" ]; then
        echo "⚠ HTTP endpoint returned $HTTP_CODE"
        WARNING=1
    else
        echo "✓ HTTP endpoint responding ($HTTP_CODE)"
    fi
fi

# 3. Check database connectivity
if command -v psql &> /dev/null; then
    if PGPASSWORD=odoo psql -h "$DB_HOST" -p "$DB_PORT" -U odoo -c "SELECT 1" &> /dev/null; then
        echo "✓ Database connection"
    else
        echo "✗ Database connection failed"
        STATUS=2
    fi
fi

# 4. Check Docker container (if applicable)
if command -v docker &> /dev/null; then
    CONTAINER_NAME="odoo-$INSTANCE_NAME"
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "✓ Docker container running"

        # Check container health status
        HEALTH_STATUS=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER_NAME" 2>/dev/null || echo "none")
        if [ "$HEALTH_STATUS" = "healthy" ]; then
            echo "  Container health: healthy"
        elif [ "$HEALTH_STATUS" = "unhealthy" ]; then
            echo "  Container health: unhealthy"
            STATUS=2
        fi
    else
        echo "⚠ Docker container not found (may be using source deployment)"
    fi
fi

# 5. Check disk space
DISK_USAGE=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
if [ "$DISK_USAGE" -gt 90 ]; then
    echo "✗ Disk usage critical: ${DISK_USAGE}%"
    STATUS=2
elif [ "$DISK_USAGE" -gt 80 ]; then
    echo "⚠ Disk usage high: ${DISK_USAGE}%"
    WARNING=1
else
    echo "✓ Disk usage: ${DISK_USAGE}%"
fi

# 6. Check memory
if command -v free &> /dev/null; then
    MEM_USAGE=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100.0}')
    if [ "$MEM_USAGE" -gt 90 ]; then
        echo "✗ Memory usage critical: ${MEM_USAGE}%"
        STATUS=2
    elif [ "$MEM_USAGE" -gt 80 ]; then
        echo "⚠ Memory usage high: ${MEM_USAGE}%"
        WARNING=1
    else
        echo "✓ Memory usage: ${MEM_USAGE}%"
    fi
fi

echo "=================================="

# Return appropriate exit code
if [ $STATUS -eq 2 ]; then
    echo "Status: CRITICAL"
    exit 2
elif [ $WARNING -eq 1 ]; then
    echo "Status: WARNING"
    exit 1
else
    echo "Status: HEALTHY"
    exit 0
fi
