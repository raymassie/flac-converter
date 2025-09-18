#!/bin/bash

# M4A to FLAC Converter Setup Script
# This script sets up the virtual environment and installs all dependencies

set -e  # Exit on any error

echo "🚀 Setting up M4A to FLAC Converter..."
echo "======================================"

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if Python 3.12 is available (Homebrew version)
if command -v /opt/homebrew/bin/python3.12 &> /dev/null; then
    PYTHON_CMD="/opt/homebrew/bin/python3.12"
    echo "✅ Found Homebrew Python 3.12: $PYTHON_CMD"
elif command -v python3.12 &> /dev/null; then
    PYTHON_CMD="python3.12"
    echo "✅ Found Python 3.12: $PYTHON_CMD"
else
    echo "❌ Python 3.12 not found!"
    echo "Installing Python 3.12 via Homebrew..."
    brew install python@3.12
    PYTHON_CMD="/opt/homebrew/bin/python3.12"
fi

# Check if ffmpeg is available
if ! command -v ffmpeg &> /dev/null; then
    echo "❌ ffmpeg not found!"
    echo "Installing ffmpeg via Homebrew..."
    brew install ffmpeg
else
    echo "✅ ffmpeg is already installed"
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    "$PYTHON_CMD" -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment and install dependencies
echo "📦 Installing Python dependencies..."
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install pydub
pip install pydub

echo "✅ Dependencies installed successfully"

# Make scripts executable
chmod +x convert_m4a_to_flac.sh
chmod +x run_converter.py

echo ""
echo "🎉 Setup complete! You can now use the converter:"
echo ""
echo "  # Convert a single file:"
echo "  ./run_converter.py song.m4a"
echo ""
echo "  # Convert all files in a directory:"
echo "  ./run_converter.py /path/to/music/folder"
echo ""
echo "  # Use the shell script wrapper:"
echo "  ./convert_m4a_to_flac.sh song.m4a"
echo ""
echo "  # Run tests:"
echo "  source venv/bin/activate && python test_conversion.py"
