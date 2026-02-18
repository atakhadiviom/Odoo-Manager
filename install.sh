#!/bin/bash
# One-line installer for Odoo Manager
# Usage: bash <(curl -s https://raw.githubusercontent.com/atakhadiviom/Odoo-Manager/main/install.sh)

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

echo "Using $PYTHON_CMD $PYTHON_VERSION"

# Detect user bin directory
USER_BIN="$HOME/.local/bin"
mkdir -p "$USER_BIN" 2>/dev/null || true

# Run installation
echo ""
echo "Installing odoo-manager..."

# Method 1: Clone and install in editable mode (most reliable)
TEMP_DIR=$(mktemp -d)
REPO_DIR="$TEMP_DIR/odoo-manager"

echo "Downloading from GitHub..."
git clone --depth 1 https://github.com/atakhadiviom/Odoo-Manager.git "$REPO_DIR" || {
    echo "Error: Failed to clone repository"
    rm -rf "$TEMP_DIR"
    exit 1
}

cd "$REPO_DIR"
echo "Installing package..."

# Try installing with pip
if $PYTHON_CMD -m pip install -e . 2>&1; then
    echo ""
    echo -e "\033[0;32m✓ Package installed via pip\033[0m"
else
    echo "pip install failed, creating standalone wrapper..."
fi

# Create standalone wrapper script (works regardless of pip install)
echo "Creating command wrapper..."

# Create wrapper that runs directly from source
cat > "$USER_BIN/odoo-manager" << 'WRAPPER_EOF'
#!/bin/bash
# Auto-generated wrapper for odoo-manager

# Find Python 3.11+
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    if [ "$(echo "$PYTHON_VERSION" | cut -d. -f2)" -ge 11 ]; then
        PYTHON_CMD="python3"
    fi
fi

if [ -z "$PYTHON_CMD" ]; then
    echo "Error: Python 3.11+ required"
    exit 1
fi

# Try to run from installed package first
if $PYTHON_CMD -m odoo_manager.cli "$@" 2>/dev/null; then
    exit 0
fi

# Fallback: run from source
ODOO_MANAGER_DIR="$HOME/.odoo-manager"
if [ -d "$ODOO_MANAGER_DIR" ]; then
    cd "$ODOO_MANAGER_DIR"
    PYTHONPATH="$ODOO_MANAGER_DIR:$PYTHONPATH" $PYTHON_CMD -m odoo_manager.cli "$@"
else
    echo "Error: odoo-manager not found. Please reinstall."
    exit 1
fi
WRAPPER_EOF

chmod +x "$USER_BIN/odoo-manager"

# Create short command symlink
ln -sf "$USER_BIN/odoo-manager" "$USER_BIN/om" 2>/dev/null || true

# Copy source to ~/.odoo-manager for fallback
echo "Installing source files..."
FINAL_DIR="$HOME/.odoo-manager"
rm -rf "$FINAL_DIR" 2>/dev/null || true
cp -r "$REPO_DIR" "$FINAL_DIR"

# Install dependencies to user site
echo "Installing dependencies..."
cd "$FINAL_DIR"
$PYTHON_CMD -m pip install --user -r pyproject.toml 2>&1 || \
$PYTHON_CMD -m pip install --user click rich pydantic pydantic-settings pyyaml jinja2 psycopg2-binary docker requests humanfriendly textual GitPython APScheduler psutil paramiko httpx cryptography 2>&1 || \
echo "Warning: Some dependencies may not have installed correctly"

rm -rf "$TEMP_DIR"

echo ""
echo -e "\033[0;32m✓ Odoo Manager installed successfully!\033[0m"
echo ""

# Check PATH
if [[ ":$PATH:" != *":$USER_BIN:"* ]]; then
    echo "⚠️  IMPORTANT: Add $USER_BIN to your PATH:"
    echo ""
    echo "  echo 'export PATH=\"\$PATH:$USER_BIN\"' >> ~/.bashrc"
    echo "  source ~/.bashrc"
    echo ""
    echo "Or run this for the current session:"
    echo "  export PATH=\"\$PATH:$USER_BIN\""
    echo ""
fi

echo "Available commands:"
echo "  odoo-manager  - Main CLI tool"
echo "  om            - Short command"
echo ""
echo "Quick start:"
echo "  odoo-manager config init"
echo "  odoo-manager instance create myinstance"
echo ""
echo "For more information: https://github.com/atakhadiviom/Odoo-Manager"
