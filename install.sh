#!/bin/bash
#
# field-agent installer
# Usage: curl -fsSL https://raw.githubusercontent.com/wesleyzhao/field-agent/main/install.sh | bash
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Installation directory
INSTALL_DIR="$HOME/field-agent"

echo -e "${CYAN}
╔═══════════════════════════════════════╗
║     field-agent installer             ║
║     Browser-based tmux manager        ║
╚═══════════════════════════════════════╝
${NC}"

# Detect OS
detect_os() {
    case "$(uname -s)" in
        Darwin*)    echo "macos" ;;
        Linux*)     echo "linux" ;;
        *)          echo "unknown" ;;
    esac
}

OS=$(detect_os)

if [ "$OS" = "unknown" ]; then
    echo -e "${RED}Error: Unsupported operating system${NC}"
    exit 1
fi

echo -e "${CYAN}Detected OS:${NC} $OS"

# Check for Python 3.10+
check_python() {
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
        MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 10 ]; then
            echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION found"
            return 0
        fi
    fi
    return 1
}

# Install Python if needed
install_python() {
    echo -e "${YELLOW}Installing Python 3...${NC}"

    if [ "$OS" = "macos" ]; then
        if ! command -v brew &> /dev/null; then
            echo -e "${YELLOW}Installing Homebrew...${NC}"
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        fi
        brew install python@3.11
    elif [ "$OS" = "linux" ]; then
        if command -v apt-get &> /dev/null; then
            sudo apt-get update
            sudo apt-get install -y python3 python3-pip python3-venv
        elif command -v yum &> /dev/null; then
            sudo yum install -y python3 python3-pip
        elif command -v dnf &> /dev/null; then
            sudo dnf install -y python3 python3-pip
        else
            echo -e "${RED}Error: Could not find package manager to install Python${NC}"
            exit 1
        fi
    fi
}

# Check for tmux
check_tmux() {
    if command -v tmux &> /dev/null; then
        echo -e "${GREEN}✓${NC} tmux found"
        return 0
    fi
    return 1
}

# Install tmux if needed
install_tmux() {
    echo -e "${YELLOW}Installing tmux...${NC}"

    if [ "$OS" = "macos" ]; then
        if ! command -v brew &> /dev/null; then
            echo -e "${YELLOW}Installing Homebrew...${NC}"
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        fi
        brew install tmux
    elif [ "$OS" = "linux" ]; then
        if command -v apt-get &> /dev/null; then
            sudo apt-get update
            sudo apt-get install -y tmux
        elif command -v yum &> /dev/null; then
            sudo yum install -y tmux
        elif command -v dnf &> /dev/null; then
            sudo dnf install -y tmux
        else
            echo -e "${RED}Error: Could not find package manager to install tmux${NC}"
            exit 1
        fi
    fi
}

# Check for git
check_git() {
    if command -v git &> /dev/null; then
        echo -e "${GREEN}✓${NC} git found"
        return 0
    fi
    return 1
}

# Install git if needed
install_git() {
    echo -e "${YELLOW}Installing git...${NC}"

    if [ "$OS" = "macos" ]; then
        xcode-select --install 2>/dev/null || true
    elif [ "$OS" = "linux" ]; then
        if command -v apt-get &> /dev/null; then
            sudo apt-get update
            sudo apt-get install -y git
        elif command -v yum &> /dev/null; then
            sudo yum install -y git
        elif command -v dnf &> /dev/null; then
            sudo dnf install -y git
        fi
    fi
}

echo ""
echo -e "${CYAN}Checking dependencies...${NC}"

# Check and install dependencies
if ! check_git; then
    install_git
fi

if ! check_python; then
    install_python
fi

if ! check_tmux; then
    install_tmux
fi

# Clone or update repository
echo ""
echo -e "${CYAN}Installing field-agent...${NC}"

if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}Existing installation found. Updating...${NC}"
    cd "$INSTALL_DIR"
    git fetch origin
    git checkout main 2>/dev/null || git checkout -b main origin/main
    git pull origin main
else
    git clone https://github.com/wesleyzhao/field-agent.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    git checkout main
fi

# Install Python package
echo ""
echo -e "${CYAN}Installing Python dependencies...${NC}"
python3 -m pip install -e "$INSTALL_DIR" --quiet

# Add to PATH if needed
SHELL_RC=""
if [ -f "$HOME/.zshrc" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then
    SHELL_RC="$HOME/.bashrc"
fi

# Check if ~/.local/bin is in PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    if [ -n "$SHELL_RC" ]; then
        echo "" >> "$SHELL_RC"
        echo '# Added by field-agent installer' >> "$SHELL_RC"
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_RC"
        echo -e "${YELLOW}Note: Added ~/.local/bin to PATH in $SHELL_RC${NC}"
        echo -e "${YELLOW}Run 'source $SHELL_RC' or restart your terminal${NC}"
    fi
fi

# Success!
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     Installation complete!            ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════╝${NC}"
echo ""
echo -e "Next steps:"
echo ""
echo -e "  1. Run the setup wizard:"
echo -e "     ${CYAN}field-agent setup${NC}"
echo ""
echo -e "  2. Start the server:"
echo -e "     ${CYAN}field-agent serve${NC}"
echo ""
echo -e "  3. For remote access from your phone:"
echo -e "     ${CYAN}field-agent serve --tunnel${NC}"
echo ""
echo -e "Documentation: https://github.com/wesleyzhao/field-agent"
echo ""

# Offer to run setup now
echo -e "${YELLOW}Would you like to run setup now? [Y/n]${NC}"
read -r response
if [[ "$response" =~ ^([yY][eE][sS]|[yY]|"")$ ]]; then
    # Source the updated PATH
    export PATH="$HOME/.local/bin:$PATH"
    field-agent setup || python3 -m field_agent.cli.main setup
fi
