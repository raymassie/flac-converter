#!/bin/bash

# Audio Converter launcher

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -x "venv/bin/python" ]; then
    echo "Virtual environment not found. Running setup..."
    ./setup.sh || exit 1
fi

echo "Starting Audio Converter..."
exec venv/bin/python audio_converter_app.py
