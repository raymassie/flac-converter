#!/usr/bin/env python3
"""
Audio Converter

A GUI application for batch-converting audio files between FLAC, WAV, AIFF,
AAC and MP3 using ffmpeg, preserving the original folder structure.

Formerly "FLAC Converter".
"""

import os
import sys
import shutil
import subprocess
import tempfile
import threading
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

# Optional drag-and-drop support. The app runs without it, minus the drop target.
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    DND_AVAILABLE = True
except Exception:
    TkinterDnD = None
    DND_FILES = None
    DND_AVAILABLE = False


APP_NAME = "Audio Converter"
FILE_TIMEOUT = 900  # seconds per file before ffmpeg is killed

# Extensions we are willing to pick up when scanning a folder.
AUDIO_EXTENSIONS = {
    '.m4a', '.mp3', '.wav', '.aac', '.ogg', '.oga', '.opus',
    '.flac', '.aiff', '.aif', '.aifc', '.wma', '.alac', '.ape', '.wv',
}

# Folder scanning limits. A recursive scan of a drive root can otherwise walk
# millions of entries and take the UI down with it.
MAX_SCAN_FILES = 20000
SCAN_PROGRESS_EVERY = 100  # directories between status updates

# Absolute directories that never contain the user's music library and that
# are expensive or unsafe to walk.
SKIP_ABS_DIRS = {
    '/System', '/private', '/dev', '/proc', '/sys', '/net', '/Network',
    '/Library', '/bin', '/sbin', '/usr', '/cores', '/opt',
    'C:\\Windows', 'C:\\$Recycle.Bin',
}
SKIP_DIR_NAMES = {
    'node_modules', '$RECYCLE.BIN', 'System Volume Information',
    'Library',  # ~/Library on macOS
}


def risky_scan_root(folder):
    """Describe why scanning this folder is a bad idea, or None if it is fine."""
    try:
        path = Path(folder).expanduser().resolve()
    except Exception:
        path = Path(folder)
    try:
        if path.parent == path or os.path.ismount(str(path)):
            return "the top level of a drive"
    except Exception:
        pass
    try:
        if path == Path.home():
            return "your entire home folder"
    except Exception:
        pass
    return None


def walk_audio_files(folder, cancel_event, progress):
    """Walk folder lazily for audio files.

    Returns (paths, truncated). Never sorts the whole tree into memory, never
    follows symlinks, skips system and hidden directories, and stops early if
    cancel_event is set or MAX_SCAN_FILES is reached.
    """
    results = []
    truncated = False
    directories = 0
    for dirpath, dirnames, filenames in os.walk(
        str(folder), followlinks=False, onerror=lambda exc: None
    ):
        if cancel_event.is_set():
            break
        dirnames[:] = [
            d for d in sorted(dirnames)
            if not d.startswith('.')
            and d not in SKIP_DIR_NAMES
            and os.path.join(dirpath, d) not in SKIP_ABS_DIRS
        ]
        for name in sorted(filenames):
            if name.startswith('.'):
                continue
            if os.path.splitext(name)[1].lower() in AUDIO_EXTENSIONS:
                results.append(Path(dirpath) / name)
                if len(results) >= MAX_SCAN_FILES:
                    truncated = True
                    break
        if truncated:
            break
        directories += 1
        if directories % SCAN_PROGRESS_EVERY == 0:
            progress(dirpath, len(results))
    return results, truncated


# Output format definitions.
#   ext       output file extension
#   args      ffmpeg codec arguments
#   art       whether the container can carry embedded cover art
#   aliases   input extensions considered "already in this format"
FORMATS = {
    "FLAC": {
        "ext": ".flac",
        "args": ["-c:a", "flac", "-compression_level", "8"],
        "art": True,
        "aliases": {".flac"},
    },
    "WAV": {
        "ext": ".wav",
        "args": ["-c:a", "pcm_s16le"],
        "art": False,
        "aliases": {".wav"},
    },
    "AIFF": {
        "ext": ".aiff",
        "args": ["-c:a", "pcm_s16be"],
        "art": False,
        "aliases": {".aiff", ".aif", ".aifc"},
    },
    "AAC (.m4a)": {
        "ext": ".m4a",
        "args": ["-c:a", "aac", "-b:a", "256k"],
        "art": True,
        "aliases": {".m4a", ".aac"},
    },
    "MP3": {
        "ext": ".mp3",
        "args": ["-c:a", "libmp3lame", "-b:a", "320k"],
        "art": True,
        "aliases": {".mp3"},
    },
}

FORMAT_PLACEHOLDER = "Conversion format..."

STATUS_PENDING = "Pending"
STATUS_WORKING = "Converting..."
STATUS_SUCCESS = "\u2705 Success"
STATUS_SKIPPED = "\u23ed Skipped"
STATUS_FAILED = "\u274c Failed"
STATUS_CANCELLED = "\u26d4 Cancelled"


def shorten(path):
    """Render a path with the user's home directory collapsed to ~."""
    if path is None:
        return "\u2014"
    text = str(path)
    home = str(Path.home())
    if text.startswith(home):
        text = "~" + text[len(home):]
    return text


CHOOSE_FOLDERS_APPLESCRIPT = """
set chosen to choose folder with prompt "Select one or more folders of audio files" with multiple selections allowed
set out to ""
repeat with item_ref in chosen
    set out to out & POSIX path of item_ref & linefeed
end repeat
return out
"""


def choose_folders_native():
    """macOS folder chooser that allows shift-click multi-selection.

    Tk's tk_chooseDirectory has no multiple-selection option, so on macOS this
    shells out to AppleScript's `choose folder`, which does.

    Returns a list of paths, [] if the user cancelled, or None if the native
    chooser is unavailable and the caller should fall back to Tk.
    """
    if sys.platform != 'darwin':
        return None
    try:
        result = subprocess.run(
            ['osascript', '-e', CHOOSE_FOLDERS_APPLESCRIPT],
            capture_output=True, text=True, timeout=3600,
        )
    except Exception:
        return None

    if result.returncode != 0:
        stderr = result.stderr or ""
        # -128 is the standard "user cancelled" AppleScript error.
        if 'User canceled' in stderr or '-128' in stderr:
            return []
        return None

    folders = [line for line in result.stdout.splitlines() if line.strip()]
    return folders or []


def folder_is_writable(folder):
    """Probe whether a file can actually be created in folder.

    os.access() lies in the presence of ACLs and read-only mounts, so this
    writes a real temporary file. Walks up to the nearest existing ancestor
    when the folder has not been created yet.
    """
    probe = Path(folder)
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    try:
        with tempfile.NamedTemporaryFile(dir=str(probe), prefix='.acwrite'):
            pass
        return True
    except Exception:
        return False


def move_to_trash(path):
    """Move a file to the system Trash. Returns (ok, error_message)."""
    path = Path(path)
    try:
        from send2trash import send2trash
        send2trash(str(path))
        return True, None
    except ImportError:
        pass
    except Exception as exc:
        return False, str(exc)

    if sys.platform == 'darwin':
        script = (
            'tell application "Finder" to delete POSIX file "%s"'
            % str(path).replace('\\', '\\\\').replace('"', '\\"')
        )
        try:
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                return True, None
            return False, (result.stderr or "osascript failed").strip()
        except Exception as exc:
            return False, str(exc)

    return False, "no Trash support on this platform (install send2trash)"


class AudioConverter:
    """Wraps ffmpeg."""

    def __init__(self):
        self.ffmpeg_path = self._find_ffmpeg()
        self.current_process = None

    def _find_ffmpeg(self):
        found = shutil.which('ffmpeg')
        if found:
            return found
        for candidate in ('/opt/homebrew/bin/ffmpeg', '/usr/local/bin/ffmpeg', '/usr/bin/ffmpeg'):
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
        return None

    def available_formats(self):
        """Return the subset of FORMATS this ffmpeg build can actually encode."""
        if not self.ffmpeg_path:
            return list(FORMATS.keys())
        try:
            result = subprocess.run(
                [self.ffmpeg_path, '-hide_banner', '-encoders'],
                capture_output=True, text=True, timeout=30,
            )
            listing = result.stdout
        except Exception:
            return list(FORMATS.keys())

        usable = []
        for name, spec in FORMATS.items():
            codec = spec['args'][spec['args'].index('-c:a') + 1]
            if (' %s ' % codec) in listing:
                usable.append(name)
        return usable or list(FORMATS.keys())

    def _build_command(self, source, destination, spec, include_art):
        cmd = [
            self.ffmpeg_path,
            '-hide_banner', '-nostdin', '-loglevel', 'error', '-y',
            '-i', str(source),
        ]
        if include_art and spec['art']:
            cmd += ['-map', '0:a', '-map', '0:v?', '-c:v', 'copy']
        else:
            cmd += ['-map', '0:a', '-vn']
        cmd += ['-map_metadata', '0']
        cmd += spec['args']
        cmd += [str(destination)]
        return cmd

    def _run(self, cmd):
        """Run ffmpeg, tracking the process so it can be cancelled."""
        try:
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
        except Exception as exc:
            return None, str(exc)

        self.current_process = process
        try:
            _, stderr = process.communicate(timeout=FILE_TIMEOUT)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            return None, "ffmpeg timed out after %d seconds" % FILE_TIMEOUT
        finally:
            self.current_process = None

        return process.returncode, (stderr or "").strip()

    def cancel(self):
        """Kill the ffmpeg process currently running, if any."""
        process = self.current_process
        if process and process.poll() is None:
            try:
                process.kill()
            except Exception:
                pass

    def convert(self, source, destination, spec):
        """Convert one file. Returns (ok, message)."""
        if not self.ffmpeg_path:
            return False, "ffmpeg not found"

        source = Path(source)
        destination = Path(destination)

        if not source.exists():
            return False, "source file no longer exists"

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            return False, "cannot create output folder: %s" % exc

        if not folder_is_writable(destination.parent):
            return False, "folder is read-only, cannot write here: %s" % destination.parent

        # First attempt keeps embedded cover art where the container allows it.
        returncode, stderr = self._run(self._build_command(source, destination, spec, True))

        # Some sources carry cover art ffmpeg refuses to copy. Retry audio-only.
        if returncode != 0 and spec['art']:
            returncode, stderr = self._run(self._build_command(source, destination, spec, False))

        if returncode is None:
            return False, stderr
        if returncode != 0:
            return False, stderr or ("ffmpeg exited with code %s" % returncode)

        if not destination.exists():
            return False, "ffmpeg reported success but no output file was written"
        try:
            if destination.stat().st_size == 0:
                return False, "output file is empty"
        except Exception as exc:
            return False, "cannot stat output file: %s" % exc

        return True, str(destination)


class AudioConverterApp:
    """Main GUI."""

    def __init__(self, root):
        self.root = root
        self.root.title("%s - Batch Audio File Converter" % APP_NAME)
        self.root.geometry("900x760")
        self.root.minsize(780, 620)

        self.converter = AudioConverter()

        # Worker threads never touch Tk. They push callbacks onto this queue
        # and the main thread drains it on a timer.
        self.ui_queue = queue.Queue()

        self.rows = {}              # tree item id -> {'src': Path, 'dst': Path|None, 'status': str}
        self.seen_sources = set()   # resolved source paths, for de-duplication
        self.common_root = None
        self.output_dir = None
        self.conversion_thread = None
        self.stop_requested = False
        self.run_state = 'idle'     # idle | running | stopping | done

        # Folder scanning runs on a worker thread so a huge tree cannot freeze
        # the UI. State below is only touched on the main thread except for
        # scan_cancel, which is an Event.
        self.scan_thread = None
        self.scan_cancel = threading.Event()
        self.pending_paths = []
        self.scan_total = 0
        self.scan_added = 0
        self.scan_truncated = False
        self.scan_ask_more = False

        self.same_folder = tk.BooleanVar(value=False)
        self.delete_originals = tk.BooleanVar(value=False)
        self.format_choice = tk.StringVar(value=FORMAT_PLACEHOLDER)
        self.progress_value = tk.DoubleVar(value=0.0)
        self.status_text = tk.StringVar(value="Ready - add files or folders to convert")

        self.build_ui()
        self.root.bind('<Escape>', self.cancel_scan)
        self.enable_drag_and_drop()
        self.drain_ui_queue()

        if not self.converter.ffmpeg_path:
            messagebox.showerror(
                "ffmpeg not found",
                "ffmpeg could not be located.\n\n"
                "Install it with:  brew install ffmpeg\n\n"
                "The application will run but cannot convert anything.",
            )
            self.status_text.set("ffmpeg not found - conversion unavailable")

    # ------------------------------------------------------------------ UI

    def build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main = ttk.Frame(self.root, padding="16")
        main.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        main.columnconfigure(0, weight=1)
        main.rowconfigure(5, weight=1)

        # Header ------------------------------------------------------------
        header = ttk.Frame(main)
        header.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 14))
        header.columnconfigure(0, weight=1)

        ttk.Label(
            header, text="\u266b %s" % APP_NAME, font=('Helvetica', 26, 'bold'),
            anchor=tk.CENTER,
        ).grid(row=0, column=0, sticky=(tk.W, tk.E))

        ttk.Label(
            header,
            text="High-quality audio conversion with folder structure preservation",
            font=('Helvetica', 12), foreground='#666666', anchor=tk.CENTER,
        ).grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(4, 0))

        # Select / Destination ----------------------------------------------
        buttons = ttk.Frame(main)
        buttons.grid(row=1, column=0, pady=(0, 10))

        self.select_button = ttk.Button(
            buttons, text="Select", width=24, command=self.show_select_menu,
        )
        self.select_button.pack(side=tk.LEFT, padx=(0, 12))

        self.select_menu = tk.Menu(self.root, tearoff=0)
        self.select_menu.add_command(label="Choose Files\u2026", command=self.choose_files)
        self.select_menu.add_command(label="Choose Folders\u2026", command=self.choose_folders)

        self.destination_button = ttk.Button(
            buttons, text="Destination", width=24, command=self.choose_destination,
        )
        self.destination_button.pack(side=tk.LEFT)

        # Same-folder checkbox ------------------------------------------------
        ttk.Checkbutton(
            main, text="Save to same folder as originals",
            variable=self.same_folder, command=self.on_same_folder_toggle,
        ).grid(row=2, column=0, pady=(0, 10))

        # Format selector -----------------------------------------------------
        formats = self.converter.available_formats()
        self.format_box = ttk.Combobox(
            main, textvariable=self.format_choice, state='readonly',
            values=[FORMAT_PLACEHOLDER] + formats, width=30, justify=tk.CENTER,
        )
        self.format_box.grid(row=3, column=0, pady=(0, 16))
        self.format_box.bind('<<ComboboxSelected>>', self.on_format_change)

        # List header ---------------------------------------------------------
        list_header = ttk.Frame(main)
        list_header.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(0, 6))
        list_header.columnconfigure(0, weight=1)

        ttk.Label(
            list_header, text="Files to Convert", font=('Helvetica', 13, 'bold'),
        ).grid(row=0, column=0, sticky=tk.W)

        ttk.Button(
            list_header, text="Clear List", width=16, command=self.clear_list,
        ).grid(row=0, column=1, sticky=tk.E)

        # File table ----------------------------------------------------------
        table = ttk.Frame(main)
        table.grid(row=5, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 14))
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)

        columns = ('track', 'original', 'destination', 'status')
        self.tree = ttk.Treeview(table, columns=columns, show='headings', height=14)
        self.tree.heading('track', text='Track Name')
        self.tree.heading('original', text='Original')
        self.tree.heading('destination', text='Destination')
        self.tree.heading('status', text='Status')
        self.tree.column('track', width=210, minwidth=140, anchor=tk.W)
        self.tree.column('original', width=250, minwidth=160, anchor=tk.W)
        self.tree.column('destination', width=250, minwidth=160, anchor=tk.W)
        self.tree.column('status', width=120, minwidth=100, anchor=tk.W)

        scrollbar = ttk.Scrollbar(table, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        self.tree.bind('<Double-1>', self.show_row_detail)
        self.tree.bind('<BackSpace>', self.remove_selected)
        self.tree.bind('<Delete>', self.remove_selected)

        # Progress ------------------------------------------------------------
        progress = ttk.Frame(main, relief=tk.GROOVE, borderwidth=1, padding="14")
        progress.grid(row=6, column=0, sticky=(tk.W, tk.E))
        progress.columnconfigure(1, weight=1)

        ttk.Label(
            progress, text="Conversion Progress", font=('Helvetica', 12, 'bold'),
        ).grid(row=0, column=0, sticky=tk.W, padx=(0, 12))

        self.progress_bar = ttk.Progressbar(
            progress, variable=self.progress_value, maximum=100, mode='determinate',
        )
        self.progress_bar.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 12))

        self.progress_label = ttk.Label(progress, text="0.0%", font=('Helvetica', 11, 'bold'), width=8)
        self.progress_label.grid(row=0, column=2, sticky=tk.W, padx=(0, 16))

        ttk.Checkbutton(
            progress, text="Delete original files", variable=self.delete_originals,
            command=self.on_delete_toggle,
        ).grid(row=0, column=3, sticky=tk.E)

        self.start_button = ttk.Button(
            progress, text="Start", width=22, command=self.on_start_button,
            state=tk.DISABLED,
        )
        self.start_button.grid(row=1, column=3, sticky=tk.E, pady=(12, 0))

        # Status bar ------------------------------------------------------------
        ttk.Label(
            main, textvariable=self.status_text, relief=tk.SUNKEN,
            anchor=tk.W, padding=(10, 5),
        ).grid(row=7, column=0, sticky=(tk.W, tk.E), pady=(12, 0))

    def enable_drag_and_drop(self):
        if not DND_AVAILABLE:
            self.status_text.set(
                "Ready - drag and drop unavailable (pip install tkinterdnd2). Use Select instead."
            )
            return
        try:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind('<<Drop>>', self.on_drop)
        except Exception as exc:
            self.status_text.set("Ready - drag and drop could not start: %s" % exc)

    # ------------------------------------------------------------- selection

    def show_select_menu(self):
        button = self.select_button
        try:
            self.select_menu.tk_popup(
                button.winfo_rootx(),
                button.winfo_rooty() + button.winfo_height(),
            )
        finally:
            self.select_menu.grab_release()

    def choose_files(self):
        paths = filedialog.askopenfilenames(
            title="Select Audio Files",
            filetypes=[
                ("Audio Files", "*.m4a *.mp3 *.wav *.aac *.ogg *.opus *.flac *.aiff *.aif *.wma"),
                ("All Files", "*.*"),
            ],
        )
        if not paths:
            return
        added = sum(1 for path in paths if self.add_file(path))
        self.after_add(added, len(paths))

    def choose_folders(self):
        """Pick folders and scan them in the background.

        On macOS the native chooser takes several folders at once (shift-click
        or cmd-click). Everywhere else Tk allows only one per dialog, so the
        app asks whether to add another afterwards.
        """
        if self.scan_busy():
            return

        folders = choose_folders_native()
        if folders is None:
            folder = filedialog.askdirectory(title="Select a folder of audio files")
            if not folder:
                return
            self.start_folder_scan([folder], ask_more=True)
            return

        if not folders:
            return
        self.start_folder_scan(folders)

    def choose_destination(self):
        folder = filedialog.askdirectory(title="Select Destination Folder")
        if not folder:
            return
        self.output_dir = Path(folder)
        if self.same_folder.get():
            self.same_folder.set(False)
        self.refresh_destinations()
        self.status_text.set("Destination: %s" % shorten(self.output_dir))
        self.refresh_start_button()

    def on_drop(self, event):
        try:
            paths = self.root.tk.splitlist(event.data)
        except Exception:
            paths = [event.data]

        if self.scan_busy():
            return

        added = 0
        scanned = 0
        folders = []
        for raw in paths:
            path = Path(raw)
            if path.is_dir():
                folders.append(str(path))
            elif path.is_file():
                scanned += 1
                if self.add_file(path):
                    added += 1
        if scanned:
            self.after_add(added, scanned)
        if folders:
            self.start_folder_scan(folders)

    def after_add(self, added, scanned):
        skipped = scanned - added
        if added and skipped:
            self.status_text.set("Added %d file(s), skipped %d duplicate(s)" % (added, skipped))
        elif added:
            self.status_text.set("Added %d file(s)" % added)
        elif scanned:
            self.status_text.set("No new files added (%d already in the list)" % skipped)
        else:
            self.status_text.set("No supported audio files found")
        self.recalculate_common_root()
        self.refresh_destinations()
        self.refresh_start_button()

    # ----------------------------------------------------------------- model

    def add_file(self, path):
        """Add one file. Returns True if it was newly added."""
        try:
            path = Path(path)
            if not path.is_file():
                return False
            key = str(path.resolve())
            if key in self.seen_sources:
                return False
            self.seen_sources.add(key)

            item = self.tree.insert('', 'end', values=(
                path.name, shorten(path.parent), "\u2014", STATUS_PENDING,
            ))
            self.rows[item] = {'src': path, 'dst': None, 'status': STATUS_PENDING}
            return True
        except Exception as exc:
            messagebox.showerror("Error", "Could not add %s:\n%s" % (path, exc))
            return False

    # ------------------------------------------------------------- scanning

    def scan_busy(self):
        return self.scan_thread is not None and self.scan_thread.is_alive()

    def confirm_scan_root(self, folder):
        risk = risky_scan_root(folder)
        if risk is None:
            return True
        return messagebox.askokcancel(
            "Scan %s?" % risk,
            "You picked %s, which is %s.\n\n"
            "Scanning that means walking every folder on it. It can take a "
            "very long time and turn up tens of thousands of files.\n\n"
            "Pick the folder your music actually lives in unless you really "
            "mean this." % (shorten(Path(folder)), risk),
            default=messagebox.CANCEL,
            icon=messagebox.WARNING,
        )

    def start_folder_scan(self, folders, ask_more=False):
        if self.scan_busy():
            return
        folders = [f for f in folders if self.confirm_scan_root(f)]
        if not folders:
            if ask_more:
                self.ask_another_folder()
            return
        self.scan_cancel.clear()
        self.set_scan_busy(True)
        self.status_text.set("Scanning\u2026  (press Esc to cancel)")
        self.scan_thread = threading.Thread(
            target=self.scan_worker, args=(folders, ask_more), daemon=True,
        )
        self.scan_thread.start()

    def scan_worker(self, folders, ask_more):
        """Runs off the main thread. Only talks to Tk through self.post."""
        found = []
        truncated = False
        for folder in folders:
            try:
                files, cut = walk_audio_files(
                    folder, self.scan_cancel,
                    lambda where, count: self.post(self.scan_progress, where, count),
                )
            except Exception as exc:
                self.post(
                    messagebox.showerror, "Error",
                    "Could not read folder %s:\n%s" % (folder, exc),
                )
                continue
            found.extend(files)
            truncated = truncated or cut
            if self.scan_cancel.is_set():
                break
        self.post(self.finish_scan, found, truncated, ask_more)

    def scan_progress(self, where, count):
        self.status_text.set(
            "Scanning %s\u2026 %d audio file(s) so far  (Esc to cancel)"
            % (shorten(Path(where)), count)
        )

    def finish_scan(self, paths, truncated, ask_more):
        self.pending_paths = list(paths)
        self.scan_total = len(paths)
        self.scan_added = 0
        self.scan_truncated = truncated
        self.scan_ask_more = ask_more
        self.insert_batch()

    def insert_batch(self):
        """Insert scan results a chunk at a time so the UI keeps breathing."""
        chunk, self.pending_paths = self.pending_paths[:200], self.pending_paths[200:]
        for path in chunk:
            if self.add_file(path):
                self.scan_added += 1
        if self.pending_paths and not self.scan_cancel.is_set():
            self.status_text.set(
                "Adding files\u2026 %d of %d"
                % (self.scan_total - len(self.pending_paths), self.scan_total)
            )
            self.root.after(1, self.insert_batch)
            return
        self.pending_paths = []
        self.set_scan_busy(False)
        self.after_add(self.scan_added, self.scan_total)
        if self.scan_truncated:
            messagebox.showwarning(
                "Stopped early",
                "Stopped after %d audio files. Add a smaller folder if you "
                "need the rest." % MAX_SCAN_FILES,
            )
        if self.scan_ask_more and not self.scan_cancel.is_set():
            self.ask_another_folder()

    def ask_another_folder(self):
        if messagebox.askyesno(
            "Add another folder?",
            "Folder added. Do you want to add another folder of audio files?",
            default=messagebox.NO,
        ):
            self.choose_folders()

    def cancel_scan(self, event=None):
        if self.scan_busy() or self.pending_paths:
            self.scan_cancel.set()
            self.pending_paths = []
            self.status_text.set("Scan cancelled")

    def set_scan_busy(self, busy):
        state = ['disabled'] if busy else ['!disabled']
        for widget in (self.select_button, self.destination_button):
            try:
                widget.state(state)
            except Exception:
                pass
        if not busy and self.same_folder.get():
            try:
                self.destination_button.state(['disabled'])
            except Exception:
                pass
        if busy:
            self.start_button.config(state=tk.DISABLED)
        else:
            self.refresh_start_button()

    def remove_selected(self, event=None):
        if self.run_state == 'running':
            return
        for item in self.tree.selection():
            row = self.rows.pop(item, None)
            if row:
                self.seen_sources.discard(str(row['src'].resolve()))
            self.tree.delete(item)
        self.recalculate_common_root()
        self.refresh_destinations()
        self.refresh_start_button()

    def clear_list(self):
        if self.run_state == 'running':
            return
        for item in list(self.rows):
            self.tree.delete(item)
        self.rows.clear()
        self.seen_sources.clear()
        self.common_root = None
        self.run_state = 'idle'
        self.progress_value.set(0)
        self.progress_label.config(text="0.0%")
        self.status_text.set("File list cleared")
        self.refresh_start_button()

    def recalculate_common_root(self):
        parents = [row['src'].parent for row in self.rows.values()]
        if not parents:
            self.common_root = None
            return
        common = parents[0].parts
        for parent in parents[1:]:
            parts = parent.parts
            length = 0
            for a, b in zip(common, parts):
                if a != b:
                    break
                length += 1
            common = common[:length]
        self.common_root = Path(*common) if common else None

    def current_spec(self):
        return FORMATS.get(self.format_choice.get())

    def compute_destination(self, source):
        spec = self.current_spec()
        if spec is None:
            return None
        extension = spec['ext']
        if self.same_folder.get():
            return source.with_suffix(extension)
        if self.output_dir is None:
            return None
        if self.common_root is not None:
            try:
                relative = source.relative_to(self.common_root)
            except ValueError:
                relative = Path(source.name)
        else:
            relative = Path(source.name)
        return self.output_dir / relative.with_suffix(extension)

    def is_already_target_format(self, source):
        spec = self.current_spec()
        if spec is None:
            return False
        return source.suffix.lower() in spec['aliases']

    def refresh_destinations(self):
        for item, row in self.rows.items():
            destination = self.compute_destination(row['src'])
            row['dst'] = destination

            if destination is None:
                shown = "\u2014"
            else:
                shown = shorten(destination.parent)
            self.tree.set(item, 'destination', shown)

            if row['status'] in (STATUS_PENDING, STATUS_SKIPPED):
                if self.current_spec() and self.is_already_target_format(row['src']):
                    row['status'] = STATUS_SKIPPED
                else:
                    row['status'] = STATUS_PENDING
                self.tree.set(item, 'status', row['status'])

    # --------------------------------------------------------------- events

    def on_same_folder_toggle(self):
        if self.same_folder.get():
            self.destination_button.state(['disabled'])
        else:
            self.destination_button.state(['!disabled'])
        self.refresh_destinations()
        self.refresh_start_button()

    def on_format_change(self, event=None):
        if self.format_choice.get() == FORMAT_PLACEHOLDER:
            self.refresh_start_button()
            return
        self.reset_finished_state()
        self.refresh_destinations()
        self.refresh_start_button()

    def on_delete_toggle(self):
        if self.delete_originals.get():
            confirmed = messagebox.askyesno(
                "Delete originals",
                "Original files will be moved to the Trash after a successful "
                "conversion is verified.\n\n"
                "Files skipped because they are already in the target format are "
                "never deleted.\n\nEnable this?",
            )
            if not confirmed:
                self.delete_originals.set(False)

    def reset_finished_state(self):
        if self.run_state == 'done':
            self.run_state = 'idle'
            self.progress_value.set(0)
            self.progress_label.config(text="0.0%")

    def ready_to_convert(self):
        if not self.rows:
            return False, "Add files to convert"
        if not self.converter.ffmpeg_path:
            return False, "ffmpeg not found"
        if self.current_spec() is None:
            return False, "Choose a conversion format"
        if not self.same_folder.get() and self.output_dir is None:
            return False, "Choose a destination folder"
        return True, ""

    def refresh_start_button(self):
        if self.run_state == 'running':
            self.start_button.config(text="In Progress", state=tk.NORMAL)
            return
        if self.run_state == 'stopping':
            self.start_button.config(text="Stopping\u2026", state=tk.DISABLED)
            return
        if self.run_state == 'done':
            self.start_button.config(text="Complete", state=tk.DISABLED)
            return

        ready, reason = self.ready_to_convert()
        self.start_button.config(
            text="Start", state=tk.NORMAL if ready else tk.DISABLED,
        )
        if not ready and self.rows:
            self.status_text.set(reason)

    def on_start_button(self):
        if self.run_state == 'running':
            self.stop_requested = True
            self.run_state = 'stopping'
            self.refresh_start_button()
            self.status_text.set("Stopping\u2026")
            self.converter.cancel()
            return
        if self.run_state in ('idle', 'done'):
            self.start_conversion()

    # ------------------------------------------------------------ conversion

    def unwritable_destinations(self, jobs):
        """Destination folders that cannot actually be written to."""
        checked = {}
        for job in jobs:
            if job['skip'] or job['dst'] is None:
                continue
            key = str(job['dst'].parent)
            if key not in checked:
                checked[key] = folder_is_writable(job['dst'].parent)
        return [Path(key) for key, ok in checked.items() if not ok]

    def show_row_detail(self, event=None):
        for item in self.tree.selection():
            row = self.rows.get(item)
            if not row:
                continue
            detail = row.get('detail')
            messagebox.showinfo(
                row['src'].name,
                "Status: %s\n\nSource: %s\nDestination: %s\n\n%s" % (
                    row.get('status', '\u2014'),
                    shorten(row['src']),
                    shorten(row.get('dst')),
                    detail or "No further detail recorded.",
                ),
            )
            return

    def failure_lines(self):
        lines = []
        for item in self.tree.get_children():
            row = self.rows.get(item)
            if row and row.get('status') == STATUS_FAILED:
                lines.append("%s\n    %s" % (
                    row['src'].name, row.get('detail') or "no reason recorded",
                ))
        return lines

    def write_failure_log(self, lines):
        path = Path.home() / "audio_converter_last_run.log"
        try:
            with open(path, 'w') as handle:
                handle.write("\n".join(lines) + "\n")
            return path
        except Exception:
            return None

    def start_conversion(self):
        ready, reason = self.ready_to_convert()
        if not ready:
            messagebox.showwarning("Not ready", reason)
            return

        # Reset any statuses from a previous run.
        for item, row in self.rows.items():
            if self.is_already_target_format(row['src']):
                row['status'] = STATUS_SKIPPED
            else:
                row['status'] = STATUS_PENDING
            self.tree.set(item, 'status', row['status'])

        # Snapshot everything the worker needs while we are still on the main
        # thread. Tk is not thread-safe: the worker must never touch a widget
        # or a Tk variable directly, only post() callbacks back to this thread.
        spec = self.current_spec()
        jobs = []
        for item in self.tree.get_children():
            row = self.rows.get(item)
            if row is None:
                continue
            jobs.append({
                'item': item,
                'src': row['src'],
                'dst': row['dst'],
                'skip': self.is_already_target_format(row['src']),
            })

        blocked = self.unwritable_destinations(jobs)
        if blocked:
            listing = "\n".join("    " + shorten(path) for path in blocked[:10])
            if len(blocked) > 10:
                listing += "\n    \u2026 and %d more" % (len(blocked) - 10)
            proceed = messagebox.askokcancel(
                "Read-only destination folder(s)",
                "These folders cannot be written to:\n\n%s\n\n"
                "Files headed there will fail. In Finder, select the folder, "
                "press Cmd-I and unlock it under Sharing & Permissions.\n\n"
                "Continue with the rest?" % listing,
                icon=messagebox.WARNING,
            )
            if not proceed:
                self.status_text.set("Cancelled - destination folder is read-only")
                return

        self.stop_requested = False
        self.run_state = 'running'
        self.progress_value.set(0)
        self.progress_label.config(text="0.0%")
        self.refresh_start_button()

        self.conversion_thread = threading.Thread(
            target=self.conversion_worker,
            args=(jobs, spec, self.delete_originals.get()),
            daemon=True,
        )
        self.conversion_thread.start()

    def conversion_worker(self, jobs, spec, delete_originals):
        total = len(jobs)

        converted = 0
        skipped = 0
        failed = 0
        trash_failures = 0

        try:
            for index, job in enumerate(jobs):
                item = job['item']

                if self.stop_requested:
                    for remaining in jobs[index:]:
                        self.post(self.set_status, remaining['item'], STATUS_CANCELLED)
                    self.post(self.conversion_stopped, converted, skipped, failed)
                    return

                source = job['src']
                destination = job['dst']

                if job['skip']:
                    skipped += 1
                    self.post(self.set_status, item, STATUS_SKIPPED)
                    self.post(self.update_progress, (index + 1) / total * 100,
                              "Skipped %s (already %s)" % (source.name, spec['ext']))
                    continue

                if destination is None:
                    failed += 1
                    self.post(self.set_status, item, STATUS_FAILED, "no destination resolved")
                    continue

                if destination.resolve() == source.resolve():
                    skipped += 1
                    self.post(self.set_status, item, STATUS_SKIPPED)
                    continue

                self.post(self.set_status, item, STATUS_WORKING)
                self.post(self.update_progress, index / total * 100,
                          "Converting %s" % source.name)

                ok, message = self.converter.convert(source, destination, spec)

                if ok:
                    converted += 1
                    if delete_originals:
                        trashed, error = move_to_trash(source)
                        if trashed:
                            self.post(self.set_status, item, STATUS_SUCCESS)
                        else:
                            trash_failures += 1
                            self.post(self.set_status, item,
                                      "\u2705 Success (not deleted)", error)
                    else:
                        self.post(self.set_status, item, STATUS_SUCCESS)
                else:
                    if self.stop_requested:
                        # ffmpeg was killed by the cancel request, not a real failure.
                        self.post(self.set_status, item, STATUS_CANCELLED)
                        try:
                            if destination.exists():
                                destination.unlink()
                        except Exception:
                            pass
                    else:
                        failed += 1
                        self.post(self.set_status, item, STATUS_FAILED, message)

                self.post(self.update_progress, (index + 1) / total * 100,
                          "Completed %d of %d" % (index + 1, total))

            self.post(self.conversion_complete, converted, skipped, failed, trash_failures,
                      delete_originals)

        except Exception as exc:
            self.post(self.conversion_failed, str(exc))

    def post(self, function, *args):
        """Queue a call to be run on the Tk main thread.

        Tk is single-threaded and root.after() is not safe to call from a
        worker thread, so the worker only ever puts work here.
        """
        self.ui_queue.put((function, args))

    def drain_ui_queue(self):
        """Run queued callbacks on the main thread, then reschedule."""
        while True:
            try:
                function, args = self.ui_queue.get_nowait()
            except queue.Empty:
                break
            try:
                function(*args)
            except Exception as exc:
                print("UI callback error: %s" % exc)
        try:
            self.root.after(50, self.drain_ui_queue)
        except tk.TclError:
            pass  # window is being destroyed

    def set_status(self, item, status, detail=None):
        row = self.rows.get(item)
        if row is None:
            return
        row['status'] = status
        self.tree.set(item, 'status', status)
        if detail:
            row['detail'] = detail
            self.status_text.set("%s: %s" % (row['src'].name, detail))

    def update_progress(self, percent, message):
        self.progress_value.set(percent)
        self.progress_label.config(text="%.1f%%" % percent)
        self.status_text.set(message)

    def conversion_stopped(self, converted, skipped, failed):
        self.run_state = 'idle'
        self.stop_requested = False
        self.refresh_start_button()
        self.status_text.set(
            "Stopped - %d converted, %d skipped, %d failed" % (converted, skipped, failed)
        )

    def conversion_complete(self, converted, skipped, failed, trash_failures,
                            delete_originals=False):
        self.run_state = 'done'
        self.progress_value.set(100)
        self.progress_label.config(text="100.0%")
        self.refresh_start_button()

        summary = "Conversion complete - %d converted, %d skipped, %d failed" % (
            converted, skipped, failed)
        if trash_failures:
            summary += ", %d original(s) could not be moved to Trash" % trash_failures
        self.status_text.set(summary)

        where = "the original folders" if self.same_folder.get() else shorten(self.output_dir)

        failures = self.failure_lines()
        if failures:
            log_path = self.write_failure_log(failures)
            shown = failures[:10]
            extra = ""
            if len(failures) > 10:
                extra = "\n\u2026 and %d more." % (len(failures) - 10)
            if log_path:
                extra += "\n\nFull list: %s" % shorten(log_path)
            messagebox.showerror(
                "Finished with failures",
                "%s\n\n%s%s\n\nDouble-click any row to see its error."
                % (summary, "\n".join(shown), extra),
            )
            return

        messagebox.showinfo("Complete", "%s\n\nOutput: %s" % (summary, where))

    def conversion_failed(self, message):
        self.run_state = 'idle'
        self.refresh_start_button()
        self.status_text.set("Conversion error: %s" % message)
        messagebox.showerror("Error", "Conversion error:\n%s" % message)


def main():
    if DND_AVAILABLE:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()

    AudioConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
