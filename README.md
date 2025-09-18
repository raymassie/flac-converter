# FLAC Converter

A modern, user-friendly GUI application for converting audio files to FLAC format while preserving the original folder structure.

![FLAC Converter](https://img.shields.io/badge/Python-3.6+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Windows%20%7C%20Linux-lightgrey.svg)

## Features

- 🎵 **High-Quality Conversion**: Converts various audio formats to FLAC using ffmpeg
- 📁 **Folder Structure Preservation**: Maintains original directory hierarchy in output
- 🛑 **Stop/Resume**: Ability to stop conversion mid-process
- 📊 **Progress Tracking**: Real-time progress bar and file status
- 🎨 **Modern UI**: Clean, intuitive interface with file preview
- 🔄 **Batch Processing**: Convert multiple files or entire folders at once

## Supported Formats

**Input Formats:**
- M4A, MP3, WAV, AAC, OGG, AIFF, FLAC

**Output Format:**
- FLAC (Free Lossless Audio Codec)

## Requirements

- Python 3.6 or higher
- ffmpeg (for audio conversion)
- tkinter (usually included with Python)

## Installation

### 1. Install ffmpeg

**macOS (using Homebrew):**
```bash
brew install ffmpeg
```

**Windows:**
- Download ffmpeg from [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html)
- Add to your system PATH

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install ffmpeg
```

### 2. Clone the Repository

```bash
git clone https://github.com/yourusername/flac-converter.git
cd flac-converter
```

### 3. Run the Application

```bash
python3 flac_converter_app.py
```

## Usage

1. **Select Files**: Click "📁 Select Files" to choose individual audio files
2. **Select Folder**: Click "📂 Select Folder" to convert all audio files in a directory
3. **Review**: Check the file list to see what will be converted
4. **Convert**: Click "🔄 Start Conversion" and choose your output directory
5. **Monitor**: Watch the progress bar and file status updates
6. **Stop**: Click "🛑 Stop Conversion" to interrupt the process if needed

## Folder Structure Preservation

The application intelligently preserves your original folder structure:

**Example:**
```
Input:
Music/
├── Artist1/
│   ├── Album1/
│   │   └── song1.m4a
│   └── Album2/
│       └── song3.m4a
└── Artist2/
    └── Album2/
        └── Disc1/
            └── song2.m4a

Output (converted folder):
converted/
├── Artist1/
│   ├── Album1/
│   │   └── song1.flac
│   └── Album2/
│       └── song3.flac
└── Artist2/
    └── Album2/
        └── Disc1/
            └── song2.flac
```

## Features in Detail

### Smart Folder Detection
- Automatically calculates the common root directory
- Preserves relative folder structure from the common root
- Handles nested directories and complex folder hierarchies

### Conversion Control
- **Start/Stop**: Toggle between start and stop modes
- **Progress Tracking**: Real-time progress bar and percentage
- **File Status**: Individual file conversion status (Pending, Success, Failed)
- **Graceful Stop**: Stops between files, not mid-conversion

### User Interface
- **File Preview**: See file names, paths, and sizes before conversion
- **Responsive Design**: Resizable window with proper column sizing
- **Status Updates**: Clear status messages and progress indicators
- **Error Handling**: User-friendly error messages and validation

## Technical Details

- **Audio Engine**: Uses ffmpeg for high-quality audio conversion
- **Threading**: Background conversion with responsive UI
- **Path Handling**: Robust cross-platform path management
- **Error Recovery**: Graceful handling of conversion failures

## Troubleshooting

### ffmpeg Not Found
If you get an "ffmpeg not found" error:
1. Ensure ffmpeg is installed and in your system PATH
2. On macOS, try: `brew install ffmpeg`
3. Restart the application after installing ffmpeg

### Conversion Failures
- Check that input files are not corrupted
- Ensure you have write permissions to the output directory
- Verify the input file format is supported

### Performance Tips
- Convert files in smaller batches for better performance
- Use SSD storage for faster file I/O
- Close other applications to free up system resources

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with Python and tkinter
- Audio conversion powered by ffmpeg
- Icons and emojis for enhanced user experience

## Support

If you encounter any issues or have questions:
1. Check the troubleshooting section above
2. Search existing issues on GitHub
3. Create a new issue with detailed information about your problem

---

**Enjoy high-quality audio conversion with FLAC Converter!** 🎵