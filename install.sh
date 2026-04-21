#!/usr/bin/env bash
set -e

# SecureMessaging Installation Script
# Supports macOS and Linux

VERSION="1.0.0"
REPO_URL="https://github.com/julianmarinov/SecureMessaging.git"
INSTALL_DIR="${INSTALL_DIR:-$HOME/SecureMessaging}"
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
║   SecureMessaging Installer v1.0.0    ║
║   End-to-End Encrypted Messaging      ║
╚═══════════════════════════════════════╝
EOF
echo -e "${NC}"

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    print_error "Please do not run this script as root"
    exit 1
fi

# Detect OS
detect_os() {
    case "$(uname -s)" in
        Linux*)     OS=Linux;;
        Darwin*)    OS=Mac;;
        *)          OS="UNKNOWN"
    esac
    print_info "Detected OS: $OS"
}

# Install Homebrew on macOS
install_homebrew() {
    if command -v brew &> /dev/null; then
        print_success "Homebrew already installed"
        return 0
    fi

    print_info "Homebrew not found - installing Homebrew"
    print_warning "This will require sudo access"

    if /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"; then
        # Add Homebrew to PATH for Apple Silicon Macs
        if [ -f "/opt/homebrew/bin/brew" ]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
        fi
        print_success "Homebrew installed"
        return 0
    else
        print_error "Failed to install Homebrew"
        return 1
    fi
}

# Install Python via package manager
install_python() {
    if [ "$OS" = "Mac" ]; then
        print_info "Installing Python 3.12 via Homebrew"

        if ! install_homebrew; then
            print_error "Cannot install Python without Homebrew"
            print_info "Please install Python manually from https://www.python.org/downloads/"
            exit 1
        fi

        # Make sure brew is in PATH
        if [ -f "/opt/homebrew/bin/brew" ]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
        fi

        if brew install python@3.12; then
            print_success "Python 3.12 installed"
            # Add Homebrew Python to PATH
            export PATH="/opt/homebrew/opt/python@3.12/bin:$PATH"
            return 0
        else
            print_error "Failed to install Python"
            exit 1
        fi
    elif [ "$OS" = "Linux" ]; then
        print_error "Python ${PYTHON_MIN_VERSION}+ is required but not found"
        print_info "Please install Python 3.12+ using your package manager:"
        print_info "  Ubuntu/Debian: sudo apt install python3.12"
        print_info "  Fedora: sudo dnf install python3.12"
        print_info "  Arch: sudo pacman -S python"
        exit 1
    else
        print_error "Automatic Python installation not supported on this OS"
        print_info "Please install Python from https://www.python.org/downloads/"
        exit 1
    fi
}

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

    print_warning "Python ${PYTHON_MIN_VERSION}+ not found"

    # Offer to install automatically
    if [ "$OS" = "Mac" ]; then
        print_info "Would you like to install Python 3.12 automatically via Homebrew?"
        read -p "Install Python? (Y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            install_python
            # Retry Python detection
            for py_cmd in python3.12 python3.13 python3.14 python3 python; do
                if command -v "$py_cmd" &> /dev/null; then
                    PY_VERSION=$("$py_cmd" -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
                    if [ "$(printf '%s\n' "$PYTHON_MIN_VERSION" "$PY_VERSION" | sort -V | head -n1)" = "$PYTHON_MIN_VERSION" ]; then
                        PYTHON_CMD="$py_cmd"
                        print_success "Found Python $PY_VERSION"
                        return 0
                    fi
                fi
            done
            print_error "Python installation succeeded but Python not found in PATH"
            print_info "Try closing and reopening your terminal, then run this script again"
            exit 1
        fi
    fi

    print_error "Cannot continue without Python ${PYTHON_MIN_VERSION}+"
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
            print_info "You can manually clone: git clone $REPO_URL $INSTALL_DIR"
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

# Setup configuration
setup_config() {
    print_info "Setting up configuration"

    if [ ! -f "config/server_config.json" ]; then
        cp config/server_config.example.json config/server_config.json
        print_success "Created server_config.json from example"
    else
        print_warning "config/server_config.json already exists, skipping"
    fi
}

# Initialize database
init_database() {
    print_info "Initializing database"
    source .venv/bin/activate

    if [ -f "data/server/server.db" ]; then
        print_warning "Database already exists"
        read -p "Reinitialize database? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -f data/server/server.db
            python scripts/init_db.py
            print_success "Database reinitialized"
        else
            print_info "Keeping existing database"
        fi
    else
        python scripts/init_db.py
        print_success "Database initialized"
    fi
}

# Create first user
create_user() {
    source .venv/bin/activate

    print_info "Would you like to create a user now?"
    read -p "Create user? (Y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        read -p "Enter username: " username
        if [ -n "$username" ]; then
            python scripts/create_user.py "$username"
            print_success "User created"
        fi
    fi
}

# Create launcher scripts
create_launchers() {
    print_info "Creating launcher scripts"

    # Server launcher
    cat > securemsg-server << 'EOF'
#!/usr/bin/env bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"
source .venv/bin/activate
exec python server/server.py "$@"
EOF
    chmod +x securemsg-server

    # Client launcher
    cat > securemsg << 'EOF'
#!/usr/bin/env bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"
source .venv/bin/activate
exec python client/main.py "$@"
EOF
    chmod +x securemsg

    print_success "Created launchers: ./securemsg-server and ./securemsg"
}

# Optionally add to PATH
setup_path() {
    if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
        print_info "Would you like to add SecureMessaging to your PATH?"
        print_info "This will allow you to run 'securemsg' and 'securemsg-server' from anywhere"
        read -p "Add to PATH? (y/N): " -n 1 -r
        echo

        if [[ $REPLY =~ ^[Yy]$ ]]; then
            SHELL_RC=""
            case "$SHELL" in
                */bash) SHELL_RC="$HOME/.bashrc" ;;
                */zsh)  SHELL_RC="$HOME/.zshrc" ;;
                *)      print_warning "Unknown shell: $SHELL" ;;
            esac

            if [ -n "$SHELL_RC" ]; then
                echo "" >> "$SHELL_RC"
                echo "# SecureMessaging" >> "$SHELL_RC"
                echo "export PATH=\"\$PATH:$INSTALL_DIR\"" >> "$SHELL_RC"
                print_success "Added to $SHELL_RC"
                print_info "Run 'source $SHELL_RC' or restart your terminal"
            fi
        fi
    fi
}

# Print final instructions
print_instructions() {
    echo
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}Installation Complete!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo
    echo "Installation directory: $INSTALL_DIR"
    echo
    echo "To start the server:"
    echo -e "  ${BLUE}cd $INSTALL_DIR && ./securemsg-server${NC}"
    echo
    echo "To start the client:"
    echo -e "  ${BLUE}cd $INSTALL_DIR && ./securemsg${NC}"
    echo
    echo "To create additional users:"
    echo -e "  ${BLUE}cd $INSTALL_DIR && source .venv/bin/activate${NC}"
    echo -e "  ${BLUE}python scripts/create_user.py <username>${NC}"
    echo
    echo "Configuration file: config/server_config.json"
    echo
    echo "Documentation: $INSTALL_DIR/README.md"
    echo "Visit: https://github.com/julianmarinov/SecureMessaging"
    echo
}

# Main installation flow
main() {
    detect_os
    check_python
    setup_repo
    setup_venv
    setup_config
    init_database
    create_user
    create_launchers
    setup_path
    print_instructions
}

# Run main
main
