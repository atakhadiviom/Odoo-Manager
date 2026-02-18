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

# Detect user bin directory
USER_BIN="$HOME/.local/bin"
if [ -d "$HOME/bin" ]; then
    USER_BIN="$HOME/bin"
fi

# Ensure user bin directory exists
mkdir -p "$USER_BIN" 2>/dev/null || true

# Run installation
echo ""
echo "Installing odoo-manager..."

# Upgrade pip first
$PYTHON_CMD -m pip install --upgrade pip setuptools wheel 2>/dev/null || true

# Install from GitHub (try with --user flag to ensure binaries are accessible)
INSTALL_SUCCESS=false

# Try regular install first
if $PYTHON_CMD -m pip install git+https://github.com/atakhadiviom/Odoo-Manager.git@main 2>/dev/null; then
    INSTALL_SUCCESS=true
# Try with --user flag
elif $PYTHON_CMD -m pip install --user git+https://github.com/atakhadiviom/Odoo-Manager.git@main 2>/dev/null; then
    INSTALL_SUCCESS=true
# Try upgrade with --user
elif $PYTHON_CMD -m pip install --user --upgrade git+https://github.com/atakhadiviom/Odoo-Manager.git@main 2>/dev/null; then
    INSTALL_SUCCESS=true
fi

if [ "$INSTALL_SUCCESS" = true ]; then
    echo ""
    echo -e "\033[0;32m✓ Odoo Manager installed successfully!\033[0m"
    echo ""

    # Check if command is available
    if ! command -v odoo-manager &> /dev/null; then
        # Find where pip installed the package
        SCRIPT_LOCATION=$($PYTHON_CMD -m pip show odoo-manager 2>/dev/null | grep "Location:" | cut -d' ' -f2)
        if [ -n "$SCRIPT_LOCATION" ]; then
            if [ -f "$SCRIPT_LOCATION/odoo_manager/cli.py" ]; then
                # Create wrapper script
                cat > "$USER_BIN/odoo-manager" << WRAPPER_EOF
#!/bin/bash
exec $PYTHON_CMD -m odoo_manager.cli "\$@"
WRAPPER_EOF
                chmod +x "$USER_BIN/odoo-manager"

                # Create symlink for short command
                ln -sf "$USER_BIN/odoo-manager" "$USER_BIN/om" 2>/dev/null || true
            fi
        fi

        # Check if PATH needs updating
        if [[ ":$PATH:" != *":$USER_BIN:"* ]]; then
            echo "⚠️  Add $USER_BIN to your PATH:"
            echo ""
            echo "  echo 'export PATH=\"\$PATH:$USER_BIN\"' >> ~/.bashrc"
            echo "  source ~/.bashrc"
            echo ""
            echo "Or run this command for the current session:"
            echo "  export PATH=\"\$PATH:$USER_BIN\""
            echo ""
        fi
    fi

    echo "Available commands:"
    echo "  odoo-manager  - Main CLI tool"
    echo "  om            - Short command"
    echo "  odoo-menu     - Interactive menu"
    echo ""
    echo "Quick start:"
    echo "  odoo-manager instance create myinstance"
    echo "  odoo-manager instance start myinstance"
    echo ""
    echo "For more information: https://github.com/atakhadiviom/Odoo-Manager"

else
    echo ""
    echo -e "\033[0;31m✗ pip installation failed, trying alternative method...\033[0m"

    # Clone and install
    TEMP_DIR=$(mktemp -d)
    REPO_DIR="$TEMP_DIR/odoo-manager"

    git clone --depth 1 https://github.com/atakhadiviom/Odoo-Manager.git "$REPO_DIR" 2>/dev/null || {
        echo "Error: Failed to clone repository"
        rm -rf "$TEMP_DIR"
        exit 1
    }

    cd "$REPO_DIR"

    # Try editable install
    if $PYTHON_CMD -m pip install -e . 2>/dev/null || $PYTHON_CMD -m pip install --user -e . 2>/dev/null; then
        echo ""
        echo -e "\033[0;32m✓ Odoo Manager installed successfully!\033[0m"
        echo ""

        # Create wrapper script if needed
        if ! command -v odoo-manager &> /dev/null; then
            cat > "$USER_BIN/odoo-manager" << WRAPPER_EOF
#!/bin/bash
cd "$REPO_DIR" 2>/dev/null || true
exec $PYTHON_CMD -m odoo_manager.cli "\$@"
WRAPPER_EOF
            chmod +x "$USER_BIN/odoo-manager"
            ln -sf "$USER_BIN/odoo-manager" "$USER_BIN/om" 2>/dev/null || true

            if [[ ":$PATH:" != *":$USER_BIN:"* ]]; then
                echo "⚠️  Add $USER_BIN to your PATH:"
                echo "  export PATH=\"\$PATH:$USER_BIN\""
            fi
        fi

        echo "Available commands: odoo-manager, om"
    else
        echo "Error: Failed to install package"
        rm -rf "$TEMP_DIR"
        exit 1
    fi

    rm -rf "$TEMP_DIR"
fi
