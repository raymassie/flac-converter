#!/usr/bin/env python3
"""
Audio Converter launch script.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    from audio_converter_app import main
    main()
except ImportError as exc:
    print("Error importing Audio Converter: %s" % exc)
    print("Make sure audio_converter_app.py is in the same directory as this script,")
    print("and that dependencies are installed:  pip install -r requirements.txt")
    sys.exit(1)
except Exception as exc:
    print("Error running Audio Converter: %s" % exc)
    sys.exit(1)
