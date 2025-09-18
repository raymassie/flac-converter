#!/usr/bin/env python3
"""
FLAC Converter Launch Script
Simple launcher for the FLAC Converter application
"""

import sys
import os
from pathlib import Path

# Add the current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Import and run the application
try:
    from flac_converter_app import main
    main()
except ImportError as e:
    print(f"Error importing FLAC Converter: {e}")
    print("Make sure flac_converter_app.py is in the same directory as this script.")
    sys.exit(1)
except Exception as e:
    print(f"Error running FLAC Converter: {e}")
    sys.exit(1)
