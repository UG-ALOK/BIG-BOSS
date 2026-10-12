
#!/usr/bin/env bash
set -Eeuo pipefail

# ============================================
# SECURITY.PY — PROFESSIONAL INSTALLER
# Termux / Debian / Ubuntu
# ============================================

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
RESET='\033[0m'

info()    { printf "${CYAN}[*]${RESET} %s\n" "$*"; }
success() { printf "${GREEN}[+]${RESET} %s\n" "$*"; }
warning() { printf "${YELLOW}[!]${RESET} %s\n" "$*"; }
die()     { printf "${RED}[ERROR]${RESET} %s\n" "$*" >&2; exit 1; }

trap 'die "Installation failed. Check the messages above."' ERR

printf "${GREEN}"
printf '%s\n' \
'╔══════════════════════════════════════════╗' \
'║       SECURITY.PY INSTALLER              ║' \
'║       TERMUX / LINUX EDITION             ║' \
'╚══════════════════════════════════════════╝'
printf "${RESET}\n"

# Detect operating system
IS_TERMUX=0

if [[ "${PREFIX:-}" == *com.termux* ]] ||
   [[ -d /data/data/com.termux ]]; then
    IS_TERMUX=1
    success "Termux detected"
elif command -v apt-get >/dev/null 2>&1; then
    success "Debian/Ubuntu Linux detected"
else
    die "Unsupported system. Use Termux or Debian/Ubuntu."
fi

# Fixed main filename
MAIN_FILE="security.py"

if [[ ! -f "$MAIN_FILE" ]]; then
    printf "Current directory: %s\n" "$PWD"
    read -r -p "Enter the full path to security.py: " MAIN_FILE
fi

[[ -f "$MAIN_FILE" ]] || die "security.py was not found."

MAIN_FILE="$(cd "$(dirname "$MAIN_FILE")" && pwd)/$(basename "$MAIN_FILE")"
PROJECT_DIR="$(dirname "$MAIN_FILE")"

cd "$PROJECT_DIR"

# Select administrative permissions
if (( IS_TERMUX )); then
    ROOT=()
elif [[ "$EUID" -eq 0 ]]; then
    ROOT=()
elif command -v sudo >/dev/null 2>&1; then
    ROOT=(sudo)
else
    die "Root access or sudo is required on Linux."
fi

# Update packages and install Python/Git
info "Updating system packages..."

if (( IS_TERMUX )); then
    pkg update -y
    pkg install -y python git
else
    "${ROOT[@]}" apt-get update
    "${ROOT[@]}" apt-get install -y \
        python3 python3-pip python3-venv git \
        ca-certificates build-essential
fi

# Find Python
if command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
elif command -v python >/dev/null 2>&1; then
    PYTHON=python
else
    die "Python installation failed."
fi

success "$("$PYTHON" --version)"
success "$(git --version)"

# Create a virtual environment
VENV_DIR="$PROJECT_DIR/.venv"

info "Setting up Python virtual environment..."

if "$PYTHON" -m venv "$VENV_DIR"; then
    RUN_PYTHON="$VENV_DIR/bin/python"

    info "Upgrading pip..."
    "$RUN_PYTHON" -m pip install --upgrade pip

    info "Installing Flask and Requests..."
    "$RUN_PYTHON" -m pip install Flask requests
else
    if (( IS_TERMUX )); then
        warning "Using Termux Python without a virtual environment."
        "$PYTHON" -m pip install --upgrade pip
        "$PYTHON" -m pip install Flask requests
        RUN_PYTHON="$PYTHON"
    else
        die "Could not create .venv. Check python3-venv."
    fi
fi

# Optional sudo support
if (( IS_TERMUX )); then
    info "sudo is not normally needed in Termux."
elif command -v sudo >/dev/null 2>&1; then
    success "sudo is available."
elif [[ "$EUID" -eq 0 ]]; then
    info "Installing sudo..."
    if apt-get install -y sudo; then
        success "sudo installed."
    else
        warning "Could not install sudo; continuing as root."
    fi
fi

# Verify libraries
info "Verifying dependencies..."
"$RUN_PYTHON" -c \
'import flask, requests; print("Flask: OK"); print("Requests: OK")'

chmod +x "$MAIN_FILE" 2>/dev/null || true

# Installation summary
printf "\n${GREEN}"
printf '%s\n' \
'╔══════════════════════════════════════════╗' \
'║          INSTALLATION COMPLETE            ║' \
'╚══════════════════════════════════════════╝'
printf "${RESET}\n"

success "Main file: security.py"
success "Installer: install.sh"
success "Git and Python are installed."
success "Flask and Requests are configured."

printf "\nRun the application with:\n\n"
printf 'cd "%s"\n' "$PROJECT_DIR"
printf '"%s" security.py\n' "$RUN_PYTHON"

printf "\n"
info "Only use the application on systems you are authorized to test."
