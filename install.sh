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

# Ensure pip is installed
echo ""
echo "Checking for pip..."
if ! $PYTHON_CMD -m pip --version &> /dev/null; then
    echo "pip not found. Installing pip..."

    # Detect OS and install pip
    if [ -f /etc/debian_version ]; then
        # Debian/Ubuntu
        echo "Detected Debian/Ubuntu system"
        sudo apt-get update > /dev/null 2>&1
        sudo apt-get install -y python3-pip python3-venv > /dev/null 2>&1
    elif [ -f /etc/redhat-release ]; then
        # RHEL/CentOS/Fedora
        echo "Detected RedHat/CentOS/Fedora system"
        sudo dnf install -y python3-pip python3-devel 2>/dev/null || \
        sudo yum install -y python3-pip python3-devel
    elif command -v pacman &> /dev/null; then
        # Arch Linux
        echo "Detected Arch Linux system"
        sudo pacman -S --noconfirm python-pip
    else
        echo "Warning: Could not auto-install pip."
        echo "Please install pip manually:"
        echo "  Ubuntu/Debian: sudo apt install python3-pip"
        echo "  CentOS/RHEL: sudo dnf install python3-pip"
        echo "  Or use: curl https://bootstrap.pypa.io/get-pip.py | python3"
        exit 1
    fi

    # Verify pip was installed
    if ! $PYTHON_CMD -m pip --version &> /dev/null; then
        echo "Error: Failed to install pip. Please install it manually."
        exit 1
    fi
    echo "✓ pip installed"
else
    echo "✓ pip is available"
fi

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
# Execute with proper argument handling
"$PYTHON_CMD" -m odoo_manager.cli "$@"
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

# Try to create symlinks in /usr/local/bin (system-wide, always in PATH)
echo ""
echo "Creating system-wide commands..."
SYMLINK_CREATED=false

if [ -w /usr/local/bin ]; then
    ln -sf "$USER_BIN/odoo-manager" /usr/local/bin/odoo-manager 2>/dev/null
    ln -sf "$USER_BIN/om" /usr/local/bin/om 2>/dev/null
    if [ -L /usr/local/bin/odoo-manager ]; then
        echo "✓ Created system-wide symlinks in /usr/local/bin"
        SYMLINK_CREATED=true
    fi
fi

if [ "$SYMLINK_CREATED" = false ]; then
    # Use sudo if available
    if command -v sudo &> /dev/null; then
        sudo ln -sf "$USER_BIN/odoo-manager" /usr/local/bin/odoo-manager 2>/dev/null
        sudo ln -sf "$USER_BIN/om" /usr/local/bin/om 2>/dev/null
        if [ -L /usr/local/bin/odoo-manager ]; then
            echo "✓ Created system-wide symlinks in /usr/local/bin (with sudo)"
            SYMLINK_CREATED=true
        fi
    fi
fi

if [ "$SYMLINK_CREATED" = false ]; then
    echo "⚠️  Could not create system-wide symlinks"
    echo "   Adding ~/.local/bin to .bashrc instead..."
    if ! grep -q "$USER_BIN" ~/.bashrc 2>/dev/null; then
        echo "" >> ~/.bashrc
        echo "# Odoo Manager" >> ~/.bashrc
        echo "export PATH=\"\$PATH:$USER_BIN\"" >> ~/.bashrc
        echo "✓ Added to PATH in ~/.bashrc"
        echo ""
        echo "   Run: source ~/.bashrc"
    fi
fi

# Also add to .bashrc for shell sessions
if [[ ":$PATH:" != *":$USER_BIN:"* ]]; then
    if ! grep -q "$USER_BIN" ~/.bashrc 2>/dev/null; then
        echo "" >> ~/.bashrc
        echo "# Odoo Manager" >> ~/.bashrc
        echo "export PATH=\"\$PATH:$USER_BIN\"" >> ~/.bashrc
        echo "✓ Added $USER_BIN to PATH in ~/.bashrc"
    fi
fi

echo ""
echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""

# Test the command immediately
echo "Testing odoo-manager..."
"$USER_BIN/odoo-manager" --help

echo ""
echo "Quick start:"
echo "  odoo-manager config init"
echo "  odoo-manager instance create myinstance"
echo ""
