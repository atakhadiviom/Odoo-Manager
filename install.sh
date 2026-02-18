#!/bin/bash
# One-line installer for Odoo Manager
# Usage: bash <(curl -s https://raw.githubusercontent.com/atakhadiviom/Odoo-refs/heads/main/install.sh)

set -e

echo "Installing Odoo Manager..."

# Detect Python command
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "Error: Python 3.11+ is required but not installed."
    echo "Install Python first and try again."
    exit 1
fi

# Check Python version
PYTHON_VERSION=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if [ "$(echo "$PYTHON_VERSION" | cut -d. -f2)" -lt 11 ]; then
    echo "Error: Python 3.11+ is required but found $PYTHON_CMD $PYTHON_VERSION"
    exit 1
fi

# Create temp directory
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"

# Run installation
echo ""
echo "Installing odoo-manager..."
$PYTHON_CMD -m pip install --upgrade pip setuptools wheel &> /dev/null

# Install from GitHub
if $PYTHON_CMD -m pip install git+https://github.com/atakhadiviom/Odoo-Manager.git@main 2>/dev/null || \
$PYTHON_CMD -m pip install --upgrade git+https://github.com/atakhadiviom/Odoo-Manager.git@main 2>/dev/null; then

    echo ""
    echo -e "\033[0;32m✓ Odoo Manager installed successfully!\033[0m"
    echo ""
    echo "Available commands:"
    echo "  odoo-manager  - Main CLI tool"
    echo "  om            - Short command"
    echo "  odoo-manager ui  - Terminal UI (panel interface)"
    echo ""
    echo "Quick start:"
    echo "  odoo-manager instance create myinstance"
    echo "  odoo-manager instance start myinstance"
    echo ""
    echo "For more information: https://github.com/atakhadiviom/Odoo-Manager"

else
    echo ""
    echo -e "\033[0;31m✗ Installation failed\033[0m"
    echo ""
    echo "Trying alternative installation method..."

    # Clone and install
    REPO_DIR="$TEMP_DIR/odoo-manager"
    git clone --depth 1 https://github.com/atakhadiviom/Odoo-Manager.git "$REPO_DIR" 2>/dev/null || {
        echo "Error: Failed to clone repository"
        rm -rf "$TEMP_DIR"
        exit 1
    }

    cd "$REPO_DIR"
    $PYTHON_CMD -m pip install -e . 2>/dev/null || {
        echo "Error: Failed to install package"
        rm -rf "$TEMP_DIR"
        exit 1
    }

    echo ""
    echo -e "\033[0;32m✓ Odoo Manager installed successfully!\033[0m"
    echo ""
    echo "Available commands:"
    echo "  odoo-manager"
    echo "  om"

    rm -rf "$TEMP_DIR"
fi
