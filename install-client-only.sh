#!/usr/bin/env bash
set -e

# SecureMessaging Client-Only Installation Script
# For connecting to an existing server

VERSION="1.0.0"
REPO_URL="https://github.com/julianmarinov/SecureMessaging.git"
INSTALL_DIR="${INSTALL_DIR:-$HOME/SecureMessaging-Client}"
PYTHON_MIN_VERSION="3.12"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print functions
print_info() { echo -e "${BLUE}ℹ${NC} $1"; }
print_success() { echo -e "${GREEN}✓${NC} $1"; }
print_error() { echo -e "${RED}✗${NC} $1"; }
print_warning() { echo -e "${YELLOW}⚠${NC} $1"; }

# Banner
echo -e "${BLUE}"
cat << "EOF"
╔═══════════════════════════════════════╗
║   SecureMessaging Client Installer    ║
║        Connect to Existing Server     ║
╚═══════════════════════════════════════╝
EOF
echo -e "${NC}"

# Check Python version
check_python() {
    print_info "Checking for Python ${PYTHON_MIN_VERSION}+"

    for py_cmd in python3.12 python3.13 python3.14 python3 python; do
        if command -v "$py_cmd" &> /dev/null; then
            PY_VERSION=$("$py_cmd" -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
            if [ "$(printf '%s\n' "$PYTHON_MIN_VERSION" "$PY_VERSION" | sort -V | head -n1)" = "$PYTHON_MIN_VERSION" ]; then
                PYTHON_CMD="$py_cmd"
                print_success "Found Python $PY_VERSION at $(command -v $py_cmd)"
                return 0
            fi
        fi
    done

    print_error "Python ${PYTHON_MIN_VERSION}+ is required but not found"
    print_info "Please install Python from https://www.python.org/downloads/"
    exit 1
}

# Clone or update repository
setup_repo() {
    if [ -d "$INSTALL_DIR" ]; then
        print_warning "Directory $INSTALL_DIR already exists"
        read -p "Continue with existing directory? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Installation cancelled"
            exit 0
        fi
    else
        print_info "Cloning repository to $INSTALL_DIR"
        if ! git clone "$REPO_URL" "$INSTALL_DIR"; then
            print_error "Failed to clone repository"
            exit 1
        fi
        print_success "Repository cloned"
    fi
}

# Create virtual environment
setup_venv() {
    print_info "Creating virtual environment"
    cd "$INSTALL_DIR"

    if [ -d ".venv" ]; then
        print_warning "Virtual environment already exists, skipping creation"
    else
        "$PYTHON_CMD" -m venv .venv
        print_success "Virtual environment created"
    fi

    # Activate venv
    source .venv/bin/activate

    # Upgrade pip
    print_info "Upgrading pip"
    pip install --upgrade pip wheel setuptools > /dev/null 2>&1

    # Install dependencies
    print_info "Installing dependencies (this may take a minute)"
    pip install -r requirements.txt > /dev/null 2>&1
    print_success "Dependencies installed"
}

# Create client launcher
create_launcher() {
    print_info "Creating launcher script"

    cat > securemsg << 'EOF'
#!/usr/bin/env bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"
source .venv/bin/activate
exec python client/main.py "$@"
EOF
    chmod +x securemsg

    print_success "Created launcher: ./securemsg"
}

# Get server configuration
configure_server() {
    echo
    print_info "Server Configuration"
    echo

    read -p "Enter server IP address (default: 100.96.169.49): " server_host
    server_host=${server_host:-100.96.169.49}

    read -p "Enter server port (default: 3005): " server_port
    server_port=${server_port:-3005}

    print_success "Client will connect to ws://$server_host:$server_port"
    print_info "You can change this later in client/main.py"
}

# Print final instructions
print_instructions() {
    echo
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}Client Installation Complete!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo
    echo "Installation directory: $INSTALL_DIR"
    echo
    echo "To start the client:"
    echo -e "  ${BLUE}cd $INSTALL_DIR && ./securemsg${NC}"
    echo
    echo -e "Server: ${BLUE}ws://$server_host:$server_port${NC}"
    echo
    echo "Login with your username and password"
    echo
    echo -e "${YELLOW}Note: Make sure you're connected to the server network${NC}"
    echo -e "${YELLOW}      (Tailscale recommended for secure remote access)${NC}"
    echo
}

# Main installation flow
main() {
    check_python
    setup_repo
    setup_venv
    create_launcher
    configure_server
    print_instructions
}

# Run main
main
