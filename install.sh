#!/bin/bash
# One-line installer for Odoo Manager
# Usage: bash <(curl -s https://raw.githubusercontent.com/atakhadiviom/Odoo-Manager/main/install.sh)

echo "=========================================="
echo "Odoo Manager Installation"
echo "=========================================="
echo ""

# Detect Python command
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "Error: Python 3.11+ is required but not installed."
    exit 1
fi

# Check Python version
PYTHON_VERSION=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
echo "Found Python: $PYTHON_CMD $PYTHON_VERSION"

# Create install directory
echo ""
echo "Setting up directories..."
INSTALL_DIR="$HOME/odoo-manager"
mkdir -p "$INSTALL_DIR"

# Download the code
echo "Downloading from GitHub..."
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "Updating existing installation..."
    cd "$INSTALL_DIR" && git pull
else
    rm -rf "$INSTALL_DIR" 2>/dev/null || true
    git clone https://github.com/atakhadiviom/Odoo-Manager.git "$INSTALL_DIR" || {
        echo "Error: Failed to clone repository"
        exit 1
    }
fi
echo "✓ Downloaded to $INSTALL_DIR"

# Install dependencies
echo ""
echo "Installing Python dependencies..."
cd "$INSTALL_DIR"

# Single pip install command with all dependencies
echo "This may take a few minutes..."
python3 -m pip install --break-system-packages \
    click rich pydantic pydantic-settings pyyaml jinja2 \
    psycopg2-binary requests humanfriendly textual \
    GitPython APScheduler psutil paramiko httpx cryptography docker

if [ $? -eq 0 ]; then
    echo "✓ Dependencies installed"
else
    echo "⚠️  Some dependencies failed to install"
    echo "The application may still work if core packages were installed"
fi

# Create executable command
echo ""
echo "Creating odoo-manager command..."

USER_BIN="$HOME/.local/bin"
mkdir -p "$USER_BIN"

# Create the main executable
cat > "$USER_BIN/odoo-manager" << 'EOF'
#!/bin/bash
# Odoo Manager - executable wrapper

INSTALL_DIR="$HOME/odoo-manager"

# Find Python
PYTHON_CMD="python3"
if ! command -v python3 &> /dev/null; then
    PYTHON_CMD="python"
fi

if [ -z "$PYTHON_CMD" ]; then
    echo "Error: Python not found"
    exit 1
fi

# Run from install directory
cd "$INSTALL_DIR" 2>/dev/null || {
    echo "Error: odoo-manager not installed properly"
    exit 1
}

# Set PYTHONPATH and run
export PYTHONPATH="$INSTALL_DIR:$PYTHONPATH"
exec $PYTHON_CMD -m odoo_manager.cli "$@"
EOF

chmod +x "$USER_BIN/odoo-manager"

# Create short command
cat > "$USER_BIN/om" << 'EOF'
#!/bin/bash
exec "$HOME/.local/bin/odoo-manager" "$@"
EOF
chmod +x "$USER_BIN/om"

echo "✓ Created command: $USER_BIN/odoo-manager"
echo "✓ Created command: $USER_BIN/om"

# Check PATH
echo ""
if [[ ":$PATH:" != *":$USER_BIN:"* ]]; then
    echo "=========================================="
    echo "⚠️  IMPORTANT: Add to PATH"
    echo "=========================================="
    echo ""
    echo "Run this command:"
    echo "  echo 'export PATH=\"\$PATH:$USER_BIN\"' >> ~/.bashrc"
    echo "  source ~/.bashrc"
    echo ""
    echo "Or for current session:"
    echo "  export PATH=\"\$PATH:$USER_BIN\""
    echo ""
    echo "=========================================="
else
    echo "✓ $USER_BIN is in PATH"
fi

echo ""
echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "Try running:"
echo "  odoo-manager --help"
echo ""
echo "Quick start:"
echo "  odoo-manager config init"
echo "  odoo-manager instance create myinstance"
echo ""
