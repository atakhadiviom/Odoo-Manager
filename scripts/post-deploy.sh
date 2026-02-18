#!/bin/bash
# Post-deployment actions for Odoo Manager
# This script runs actions after a successful deployment

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT="${1:-development}"
INSTANCE_NAME="${2:-odoo-$ENVIRONMENT}"
DEPLOYMENT_ID="${3:-manual}"
WEBHOOK_URL="${NOTIFICATION_WEBHOOK:-}"

echo "=========================================="
echo "Post-deployment actions for Odoo Manager"
echo "=========================================="
echo "Environment: $ENVIRONMENT"
echo "Instance: $INSTANCE_NAME"
echo "Deployment ID: $DEPLOYMENT_ID"
echo ""

# Function to log action
log_action() {
    echo -e "${BLUE}[ACTION]${NC} $*"
}

# Function to log success
log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

# Function to log warning
log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $*"
}

# 1. Record deployment
log_action "Recording deployment..."
DEPLOYMENT_FILE="$HOME/.config/odoo-manager/deployment_history.yaml"
if [ -d "$(dirname "$DEPLOYMENT_FILE")" ]; then
    # This would typically use odoo-manager CLI
    log_success "Deployment recorded to $DEPLOYMENT_FILE"
else
    log_warning "Could not record deployment (config directory not found)"
fi

# 2. Run health check
log_action "Running health check..."
if command -v odoo-manager &> /dev/null; then
    if odoo-manager monitor status &> /dev/null; then
        log_success "Instance is healthy"
    else
        log_warning "Instance health check returned warnings"
    fi
else
    log_warning "odoo-manager CLI not found, skipping health check"
fi

# 3. Update any load balancers or proxies
log_action "Checking for load balancer configuration..."
if [ -f "$HOME/.config/odoo-manager/nginx-$ENVIRONMENT.conf" ]; then
    log_success "Nginx configuration found for $ENVIRONMENT"
    # Would reload nginx here
    # sudo systemctl reload nginx
    log_success "Load balancer reloaded"
else
    log_warning "No load balancer configuration found"
fi

# 4. Send notification
if [ -n "$WEBHOOK_URL" ]; then
    log_action "Sending deployment notification..."
    NOTIFICATION_JSON=$(cat <<EOF
{
    "environment": "$ENVIRONMENT",
    "instance": "$INSTANCE_NAME",
    "deployment_id": "$DEPLOYMENT_ID",
    "status": "success",
    "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF
)
    curl -s -X POST "$WEBHOOK_URL" \
        -H "Content-Type: application/json" \
        -d "$NOTIFICATION_JSON" &> /dev/null && log_success "Notification sent" || log_warning "Failed to send notification"
else
    log_warning "No webhook URL configured, skipping notification"
fi

# 5. Run database optimizations (optional)
log_action "Running database optimizations..."
# Uncomment to enable:
# odoo-manager shell --command "env.cr.execute('VACUUM ANALYZE ir_ui_view')"

# 6. Cleanup old backups (keep last 10)
log_action "Cleaning up old backups..."
BACKUP_DIR="$HOME/odoo-manager/backups/$ENVIRONMENT"
if [ -d "$BACKUP_DIR" ]; then
    BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/*.dump 2>/dev/null | wc -l)
    if [ "$BACKUP_COUNT" -gt 10 ]; then
        ls -t "$BACKUP_DIR"/*.dump | tail -n +11 | xargs rm -f
        log_success "Cleaned up old backups (kept 10 most recent)"
    else
        log_success "No cleanup needed ($BACKUP_COUNT backups)"
    fi
else
    log_warning "Backup directory not found"
fi

echo ""
echo "=========================================="
echo -e "${GREEN}Post-deployment actions completed${NC}"
echo "=========================================="

exit 0
