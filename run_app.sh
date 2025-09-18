#!/bin/bash

# FLAC Converter App Launcher
# Simple script to run the drag & drop FLAC converter

echo "🎵 Starting FLAC Converter App..."
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "⚠️  Virtual environment not found. Running setup..."
    ./setup.sh
fi

# Activate virtual environment and run app
echo "🚀 Launching FLAC Converter App..."
source venv/bin/activate
python3 flac_converter_app.py
