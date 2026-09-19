#!/bin/bash

cd "$(dirname "$0")"

if [ ! -x "venv/bin/python" ]; then
    echo "Virtual environment not found. Running setup..."
    ./setup.sh
fi

echo "Launching Audio Converter..."
venv/bin/python audio_converter_app.py

if [ $? -ne 0 ]; then
    echo ""
    echo "Press any key to close..."
    read -n 1
fi
