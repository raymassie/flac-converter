#!/usr/bin/env python3
"""
M4A to FLAC Converter Script

This script converts .m4a audio files to .flac format using the pydub library.
It can process single files or entire directories.

Requirements:
- Python 3.6+
- pydub library (install with: pip install pydub)
- ffmpeg (install with: brew install ffmpeg on macOS)

Usage:
    python m4a_to_flac_converter.py <input_file_or_directory>
    
Examples:
    python m4a_to_flac_converter.py song.m4a
    python m4a_to_flac_converter.py /path/to/music/folder
"""

import os
import sys
import argparse
from pathlib import Path
from pydub import AudioSegment
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def convert_m4a_to_flac(input_path, output_path=None, quality=192):
    """
    Convert a single .m4a file to .flac format.
    
    Args:
        input_path (str): Path to the input .m4a file
        output_path (str): Path for the output .flac file (optional)
        quality (int): Audio quality in kbps (default: 192)
    
    Returns:
        bool: True if conversion successful, False otherwise
    """
    try:
        # Load the audio file
        logger.info(f"Loading audio file: {input_path}")
        audio = AudioSegment.from_file(input_path, format="m4a")
        
        # Generate output path if not provided
        if output_path is None:
            output_path = str(Path(input_path).with_suffix('.flac'))
        
        # Export as FLAC
        logger.info(f"Converting to FLAC: {output_path}")
        audio.export(output_path, format="flac", parameters=["-q:a", str(quality)])
        
        logger.info(f"Successfully converted: {input_path} -> {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error converting {input_path}: {str(e)}")
        return False

def process_directory(input_dir, output_dir=None, recursive=False):
    """
    Process all .m4a files in a directory.
    
    Args:
        input_dir (str): Input directory path
        output_dir (str): Output directory path (optional)
        recursive (bool): Whether to process subdirectories recursively
    
    Returns:
        tuple: (total_files, successful_conversions, failed_conversions)
    """
    input_path = Path(input_dir)
    
    if not input_path.exists() or not input_path.is_dir():
        logger.error(f"Invalid directory: {input_dir}")
        return 0, 0, 0
    
    # Set output directory
    if output_dir is None:
        output_dir = input_dir
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Find all .m4a files
    if recursive:
        m4a_files = list(input_path.rglob("*.m4a"))
    else:
        m4a_files = list(input_path.glob("*.m4a"))
    
    if not m4a_files:
        logger.info(f"No .m4a files found in {input_dir}")
        return 0, 0, 0
    
    logger.info(f"Found {len(m4a_files)} .m4a files to convert")
    
    successful = 0
    failed = 0
    
    for m4a_file in m4a_files:
        # Calculate relative path for output
        if recursive:
            rel_path = m4a_file.relative_to(input_path)
        else:
            rel_path = m4a_file.name
        
        # Create output file path
        output_file = output_path / rel_path.with_suffix('.flac')
        
        # Create output subdirectory if needed
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert the file
        if convert_m4a_to_flac(str(m4a_file), str(output_file)):
            successful += 1
        else:
            failed += 1
    
    return len(m4a_files), successful, failed

def main():
    parser = argparse.ArgumentParser(
        description="Convert .m4a audio files to .flac format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "input",
        help="Input .m4a file or directory containing .m4a files"
    )
    
    parser.add_argument(
        "-o", "--output",
        help="Output directory (for directory processing) or output file path"
    )
    
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Process subdirectories recursively when input is a directory"
    )
    
    parser.add_argument(
        "-q", "--quality",
        type=int,
        default=192,
        help="Audio quality in kbps (default: 192)"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    input_path = Path(args.input)
    
    if not input_path.exists():
        logger.error(f"Input path does not exist: {args.input}")
        sys.exit(1)
    
    if input_path.is_file():
        # Single file conversion
        if input_path.suffix.lower() != '.m4a':
            logger.error(f"Input file is not a .m4a file: {args.input}")
            sys.exit(1)
        
        success = convert_m4a_to_flac(
            str(input_path), 
            args.output, 
            args.quality
        )
        
        if success:
            logger.info("File conversion completed successfully!")
            sys.exit(0)
        else:
            logger.error("File conversion failed!")
            sys.exit(1)
    
    elif input_path.is_dir():
        # Directory processing
        total, successful, failed = process_directory(
            str(input_path),
            args.output,
            args.recursive
        )
        
        logger.info(f"\nConversion Summary:")
        logger.info(f"Total files: {total}")
        logger.info(f"Successful: {successful}")
        logger.info(f"Failed: {failed}")
        
        if failed == 0:
            logger.info("All conversions completed successfully!")
            sys.exit(0)
        else:
            logger.warning(f"{failed} conversions failed!")
            sys.exit(1)
    
    else:
        logger.error(f"Invalid input path: {args.input}")
        sys.exit(1)

if __name__ == "__main__":
    main()
