#!/bin/bash

# Quick Setup Script for Network Lab Project
# Run this script to initialize the development environment

set -e  # Exit on error

echo "========================================================"
echo "Network Lab Project - Quick Setup"
echo "========================================================"
echo ""

# Detect OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macOS"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="Linux"
else
    OS="Other"
fi

echo "[*] Detected OS: $OS"
echo ""

# Check Python installation
echo "[*] Checking Python installation..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo "    ✓ Python found: $PYTHON_VERSION"
else
    echo "    ✗ Python 3 not found. Please install Python 3.10 or later."
    exit 1
fi

# Create virtual environment
echo ""
echo "[*] Creating Python virtual environment..."
if [ -d "venv" ]; then
    echo "    ! Virtual environment already exists. Skipping."
else
    python3 -m venv venv
    echo "    ✓ Virtual environment created"
fi

# Activate virtual environment
echo ""
echo "[*] Activating virtual environment..."
source venv/bin/activate
echo "    ✓ Virtual environment activated"

# Upgrade pip
echo ""
echo "[*] Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1
echo "    ✓ Pip upgraded"

# Install requirements
echo ""
echo "[*] Installing Python dependencies..."
echo "    (This may take a few minutes...)"
pip install -r requirements.txt > /dev/null 2>&1
echo "    ✓ Dependencies installed"

# Check for Ansible
echo ""
echo "[*] Checking Ansible installation..."
if command -v ansible &> /dev/null; then
    ANSIBLE_VERSION=$(ansible --version | head -n 1)
    echo "    ✓ Ansible found: $ANSIBLE_VERSION"
else
    echo "    ! Ansible not found in system PATH"
    echo "    Installing via pip..."
    pip install ansible > /dev/null 2>&1
    echo "    ✓ Ansible installed via pip"
fi

# Check for nmap
echo ""
echo "[*] Checking nmap installation..."
if command -v nmap &> /dev/null; then
    NMAP_VERSION=$(nmap --version | head -n 1)
    echo "    ✓ nmap found: $NMAP_VERSION"
else
    echo "    ✗ nmap not found"
    if [[ "$OS" == "macOS" ]]; then
        echo "    Install with: brew install nmap"
    elif [[ "$OS" == "Linux" ]]; then
        echo "    Install with: sudo apt-get install nmap (Ubuntu/Debian)"
        echo "                  sudo yum install nmap (CentOS/RHEL)"
    fi
fi

# Create test results directory
echo ""
echo "[*] Creating project directories..."
mkdir -p task1_device_discovery/test_results
mkdir -p shared/config_templates
echo "    ✓ Directories created"

# Test imports
echo ""
echo "[*] Testing Python imports..."
python3 << EOF
try:
    import requests
    import ipaddress
    import yaml
    import jinja2
    print("    ✓ Core imports successful")
except ImportError as e:
    print(f"    ✗ Import error: {e}")
    exit(1)
EOF

# Create activation helper script
cat > activate.sh << 'EOFSCRIPT'
#!/bin/bash
# Helper script to activate the virtual environment
source venv/bin/activate
echo "✓ Virtual environment activated"
echo "To deactivate, run: deactivate"
EOFSCRIPT
chmod +x activate.sh

echo ""
echo "========================================================"
echo "Setup Complete!"
echo "========================================================"
echo ""
echo "Next steps:"
echo "  1. Activate environment: source activate.sh"
echo "  2. Navigate to task directory: cd task1_device_discovery"
echo "  3. Generate FortiGate config: python3 fortigate_config.py"
echo "  4. Review documentation: cat README.md"
echo ""
echo "To run discovery and testing:"
echo "  python3 device_discovery.py"
echo "  ansible-playbook -i ansible_inventory.yml ansible_playbook.yml"
echo ""
echo "VSCode Integration:"
echo "  Open this folder in VSCode"
echo "  Select Python interpreter: venv/bin/python"
echo "  Extensions recommended: Python, Ansible, YAML"
echo ""
