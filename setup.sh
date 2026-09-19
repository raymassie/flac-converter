#!/bin/bash

# Audio Converter setup
# Creates the virtual environment and installs dependencies.

set -e

echo "Setting up Audio Converter..."
echo "============================="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- Python -----------------------------------------------------------------
if command -v /opt/homebrew/bin/python3 &> /dev/null; then
    PYTHON_CMD="/opt/homebrew/bin/python3"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
else
    echo "Python 3 not found. Install it with: brew install python"
    exit 1
fi
echo "Using Python: $PYTHON_CMD ($($PYTHON_CMD -V 2>&1))"

# --- tkinter ----------------------------------------------------------------
if ! "$PYTHON_CMD" -c "import tkinter" &> /dev/null; then
    echo "This Python has no tkinter support."
    echo "On macOS with Homebrew, install it with: brew install python-tk"
    exit 1
fi
echo "tkinter: OK"

# --- ffmpeg -----------------------------------------------------------------
if ! command -v ffmpeg &> /dev/null; then
    echo "ffmpeg not found."
    if command -v brew &> /dev/null; then
        echo "Installing ffmpeg via Homebrew..."
        brew install ffmpeg
    else
        echo "Install ffmpeg and re-run this script."
        exit 1
    fi
fi
echo "ffmpeg: $(command -v ffmpeg)"

# --- virtual environment ----------------------------------------------------
# A leftover venv is often stale: built against a Python that has since been
# upgraded or removed. A stale venv can still have a working interpreter and
# pip while pointing at a different Python than the one checked above, so the
# version and tkinter are both verified before it is reused.
BASE_VERSION="$("$PYTHON_CMD" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"

venv_is_usable() {
    [ -x "venv/bin/python" ] || return 1
    venv/bin/python -c "import sys" &> /dev/null || return 1
    venv/bin/python -m pip --version &> /dev/null || return 1
    local venv_version
    venv_version="$(venv/bin/python -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null)"
    [ "$venv_version" = "$BASE_VERSION" ] || return 1
    venv/bin/python -c "import tkinter" &> /dev/null || return 1
    return 0
}

if [ -d "venv" ]; then
    if venv_is_usable; then
        echo "Reusing existing virtual environment (Python $BASE_VERSION)"
    else
        echo "Existing virtual environment is stale or incomplete. Rebuilding it..."
        rm -rf venv
    fi
fi

if [ ! -d "venv" ]; then
    echo "Creating virtual environment (Python $BASE_VERSION)..."
    "$PYTHON_CMD" -m venv --system-site-packages venv
fi

VENV_PY="venv/bin/python"

if ! "$VENV_PY" -m pip --version &> /dev/null; then
    echo "pip is missing from the virtual environment. Bootstrapping it..."
    "$VENV_PY" -m ensurepip --upgrade
fi

# A freshly built venv that still cannot import tkinter means the base Python's
# Tk support is not reachable. Report enough detail to act on.
if ! "$VENV_PY" -c "import tkinter" &> /dev/null; then
    echo ""
    echo "The virtual environment cannot import tkinter, even after rebuilding."
    echo ""
    echo "  base python : $PYTHON_CMD ($("$PYTHON_CMD" -c 'import sys; print(sys.version.split()[0])'))"
    echo "  base prefix : $("$PYTHON_CMD" -c 'import sys; print(sys.base_prefix)')"
    echo "  venv python : $("$VENV_PY" -c 'import sys; print(sys.version.split()[0])')"
    echo "  venv prefix : $("$VENV_PY" -c 'import sys; print(sys.base_prefix)')"
    echo ""
    echo "  error:"
    "$VENV_PY" -c "import tkinter" 2>&1 | sed 's/^/    /'
    echo ""
    echo "Install the Tk package matching the base Python above, for example:"
    echo "  brew install python-tk@$BASE_VERSION"
    exit 1
fi

echo "tkinter in venv: OK"

"$VENV_PY" -m pip install --upgrade pip --quiet
"$VENV_PY" -m pip install -r requirements.txt

# --- executables ------------------------------------------------------------
chmod +x run.py run_app.sh "Launch Audio Converter.command" 2>/dev/null || true

echo ""
echo "Setup complete. Start the app with any of:"
echo "  ./run_app.sh"
echo "  python3 audio_converter_app.py"
echo "  double-click 'Launch Audio Converter.command'"
