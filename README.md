# Audio Converter

A GUI application for batch-converting audio files between FLAC, WAV, AIFF, AAC and MP3
using ffmpeg, preserving the original folder structure.

Formerly "FLAC Converter". Renamed when multi-format output was added.

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Windows%20%7C%20Linux-lightgrey.svg)

## Features

- **Five output formats**: FLAC, WAV, AIFF, AAC (.m4a), MP3
- **Drag and drop**: drop files or folders straight onto the window
- **Multiple folders**: on macOS the folder chooser takes several at once (shift-click
  or cmd-click); elsewhere it asks whether you want to add another after each one
- **Background folder scanning**: large folders are scanned off the UI thread, with live
  progress and Esc to cancel
- **Folder structure preservation**: output mirrors the input hierarchy
- **Save in place**: optionally write converted files next to their originals
- **Skip files already in the target format**, marked as Skipped in the list
- **Move originals to Trash** after conversion is verified (optional, off by default)
- **Cover art and tags preserved** where the output container supports them
- **Cancel mid-run**: the Start button becomes In Progress and stops the job when clicked
- **De-duplication**: adding the same folder twice will not queue anything twice
- **Readable failures**: destination folders are checked for writability before a run,
  and every failure reports its reason

## Output format settings

| Format | Extension | Encoder | Settings |
|---|---|---|---|
| FLAC | `.flac` | flac | `-compression_level 8` (lossless, smallest) |
| WAV | `.wav` | pcm_s16le | 16-bit PCM |
| AIFF | `.aiff` | pcm_s16be | 16-bit PCM |
| AAC | `.m4a` | aac | 256 kbps |
| MP3 | `.mp3` | libmp3lame | 320 kbps |

Only formats your ffmpeg build can actually encode appear in the dropdown.

## What you need first

Two things have to be on your computer before Audio Converter will run. Both are
one-line installs.

- **ffmpeg** — this is the program that actually converts the audio. On macOS:
  `brew install ffmpeg`
- **Python 3.9 or newer, with tkinter** — this draws the app's window. Most Macs
  already have Python, but the window part is often missing. On macOS:
  `brew install python-tk`

If you don't have Homebrew (the `brew` command), install it first from
[brew.sh](https://brew.sh).

Everything else the app needs is installed for you in the next step.

## Setting it up (once)

1. Download this folder to your computer and remember where you put it.
2. Open Terminal, type `cd ` (with a space), then drag the folder onto the
   Terminal window and press Return. This moves Terminal into the folder.
3. Type `./setup.sh` and press Return.

`setup.sh` checks that Python and ffmpeg are present, creates a self-contained
`venv` folder for the app's own dependencies, and installs them there. It does not
touch anything else on your system. If you see "permission denied", run
`chmod +x setup.sh` first and try again.

You only ever do this once.

## Running it

**The easy way.** Double-click **Audio Converter** in this folder. That's the app
icon. No Terminal window, nothing to type.

To keep it handy, right-click it and choose **Make Alias**, then drag the alias to
your Dock or your Applications folder. Use an alias, not a copy. The app is a thin
launcher that runs the Python file sitting next to it, so a copy moved somewhere
else can't find it and will tell you so rather than starting.

**From Terminal**, if you prefer, from inside the folder:

```bash
./run_app.sh
```

**Running the Python directly**, useful if something is going wrong and you want
to see the error messages:

```bash
venv/bin/python audio_converter_app.py
```

Use `venv/bin/python` rather than plain `python3` here. The `venv` folder is where
setup put the app's dependencies, so plain `python3` will usually complain that
`tkinterdnd2` is missing.

If the app ever fails to start on the very first launch, it writes what went wrong
to `/tmp/audio_converter_setup.log`.

## Usage

1. **Add files**: drag files or folders onto the window, or use **Select** for a file
   or folder chooser. On macOS the folder chooser is the native panel and accepts
   multiple folders at once via shift-click or cmd-click; on other platforms Tk allows
   only one per dialog, so you are asked whether to add another after each. Folders are
   scanned recursively in the background; press **Esc** to cancel a scan that is taking
   too long.
2. **Choose an output location**: click **Destination**, or tick
   **Save to same folder as originals**.
3. **Pick a format** from the dropdown.
4. **Start**. The button reads **In Progress** during the run; click it to stop after
   the current file. It reads **Complete** when the job finishes.

Select a row and press Delete or Backspace to remove it from the list. **Double-click**
a row to see its full status, source and destination paths, and any error.

## Deleting originals

**Delete original files** moves each source file to the Trash, but only after the
conversion has been verified: ffmpeg exited cleanly, the output file exists, and it is
not zero bytes. Files that were **skipped** or that **failed** are never deleted.

On macOS this uses Finder via `osascript` if `send2trash` is not installed. On other
platforms `send2trash` is required; without it the originals are kept and the status
column says so.

## Folder structure preservation

The common root of everything you add is calculated, and each file's path relative to
that root is recreated under the destination.

```
Input:
Music/
├── Artist1/
│   ├── Album1/song1.m4a
│   └── Album2/song3.m4a
└── Artist2/Album2/Disc1/song2.m4a

Output:
converted/
├── Artist1/
│   ├── Album1/song1.flac
│   └── Album2/song3.flac
└── Artist2/Album2/Disc1/song2.flac
```

## When something fails

If any file fails, a dialog lists each one with its reason, and the full list is written
to `~/audio_converter_last_run.log`. Double-click a row for that file's error.

Before a run starts, every destination folder is probed with a real test write. Folders
that cannot be written to are named up front and you choose whether to continue. This
catches read-only folders that `os.access()` reports as writable because of ACLs.

## Known limitations

- **Skipping is by file extension, not by codec.** An `.m4a` containing ALAC is treated
  as already-AAC and skipped when AAC is the target. Convert to a different format, or
  remove the extension from the format's alias set, if that matters to you.
- **Conversion is serial.** One ffmpeg process at a time regardless of core count.
- **WAV and AIFF cannot carry cover art.** Art is stripped for those targets. Tags are
  preserved where the container supports them.
- **Cancel stops between files** in the common case. If ffmpeg is mid-file it is killed
  and the partial output is removed, but this path is less exercised than the rest.
- Files are converted at a per-file timeout of 15 minutes; anything slower is killed and
  marked Failed.
- **A single folder scan stops at 20,000 audio files.** Hidden directories, `node_modules`,
  `~/Library` and system paths such as `/System` and `/private` are skipped, and symlinks
  are not followed. Picking a drive root or your home folder prompts for confirmation
  first, because scanning either one is rarely what you meant.

## Troubleshooting

**ffmpeg not found** — `brew install ffmpeg`, then restart the app.

**Drag and drop does nothing** — `tkinterdnd2` is missing. `pip install tkinterdnd2`,
or use the Select button. The status bar says which state you are in at launch.

**No module named tkinter** — your Python was built without Tk. On macOS with Homebrew,
`brew install python-tk`.

**Every file failed, or "Permission denied"** — the destination folder is read-only.
This is common with album folders imported by other software: the folder can be mode
`r-xr-xr-x` even though the audio files inside it are writable. In Finder, select the
folder, press Cmd-I, and unlock it under Sharing & Permissions. Or from a terminal:
`chmod u+w "/path/to/folder"`. To find every locked folder under a library:
`find ~/Music -type d ! -perm -u+w`.

**Originals were not deleted** — the conversion failed verification, the file was
skipped, or Trash was unavailable. The status column and status bar say which.

## License

MIT. See [LICENSE](LICENSE).
