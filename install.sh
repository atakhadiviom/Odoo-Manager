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
    echo "Install Python first and try again."
    exit 1
fi

# Check Python version
PYTHON_VERSION=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
echo "Found Python: $PYTHON_CMD $PYTHON_VERSION"

if [ "$(echo "$PYTHON_VERSION" | cut -d. -f2)" -lt 11 ]; then
    echo "Error: Python 3.11+ is required but found $PYTHON_VERSION"
    exit 1
fi

# Check if pip is available
echo ""
echo "Checking pip..."
if ! $PYTHON_CMD -m pip --version &>/dev/null; then
    echo "pip is not installed. Installing pip..."
    curl -sS https://bootstrap.pypa.io/get-pip.py | $PYTHON_CMD
fi

# Create install directory
echo ""
echo "Setting up directories..."
INSTALL_DIR="$HOME/odoo-manager"
mkdir -p "$INSTALL_DIR"

# Download the code
echo "Downloading from GitHub..."
git clone --depth 1 https://github.com/atakhadiviom/Odoo-Manager.git "$INSTALL_DIR" 2>/dev/null || {
    echo "Trying full clone..."
    git clone https://github.com/atakhadiviom/Odoo-Manager.git "$INSTALL_DIR" || {
        echo "Error: Failed to clone repository"
        exit 1
    }
}
echo "✓ Downloaded to $INSTALL_DIR"

# Install dependencies
echo ""
echo "Installing Python dependencies..."
cd "$INSTALL_DIR"

# Upgrade pip first
echo "Upgrading pip..."
$PYTHON_CMD -m pip install --upgrade pip --user

# Install requirements from pyproject.toml or use explicit list
echo "Installing required packages..."

# Try using requirements.txt approach from pyproject.toml dependencies
cat > "$INSTALL_DIR/requirements.txt" << 'REQEOF'
click>=8.1.0
rich>=13.0.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
pyyaml>=6.0
jinja2>=3.1.0
psycopg2-binary>=2.9.0
docker>=6.0.0
requests>=2.28.0
humanfriendly>=10.0.0
textual>=0.44.0
GitPython>=3.1.0
APScheduler>=3.10.0
psutil>=5.9.0
paramiko>=3.0.0
httpx>=0.24.0
cryptography>=41.0.0
REQEOF

echo "Running: pip install --user -r requirements.txt"
$PYTHON_CMD -m pip install --user -r "$INSTALL_DIR/requirements.txt"

if [ $? -eq 0 ]; then
    echo "✓ Dependencies installed"
else
    echo ""
    echo "⚠️  Some dependencies failed. Trying alternative install..."
    echo ""
    # Try with --break-system-packages flag (for newer pip versions)
    $PYTHON_CMD -m pip install -r "$INSTALL_DIR/requirements.txt" --break-system-packages 2>/dev/null && {
        echo "✓ Dependencies installed with --break-system-packages"
    } || {
        echo "⚠️  Warning: Dependency installation had issues"
    }
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
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
fi

if [ -z "$PYTHON_CMD" ]; then
    echo "Error: Python not found"
    exit 1
fi

# Run from install directory
cd "$INSTALL_DIR" 2>/dev/null || {
    echo "Error: odoo-manager not installed properly"
    echo "Run: bash <(curl -s https://raw.githubusercontent.com/atakhadiviom/Odoo-Manager/main/install.sh)"
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
