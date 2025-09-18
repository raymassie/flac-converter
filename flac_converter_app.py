#!/usr/bin/env python3
"""
FLAC Converter App - Clean Working Version

A simple GUI application for converting audio files to FLAC format.
Automatically organizes files into Artist/Album folder structure.
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import subprocess
import queue

class AudioConverter:
    """Handles audio file conversion using ffmpeg"""
    
    def __init__(self):
        self.ffmpeg_path = self._find_ffmpeg()
    
    def _find_ffmpeg(self):
        """Find ffmpeg executable"""
        possible_paths = [
            'ffmpeg',
            '/opt/homebrew/bin/ffmpeg',
            '/usr/local/bin/ffmpeg',
            '/usr/bin/ffmpeg'
        ]
        
        for path in possible_paths:
            try:
                result = subprocess.run([path, '-version'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    return path
            except:
                continue
        
        return None
    
    def convert_file(self, input_path, output_dir, relative_path=None):
        """Convert a single audio file to FLAC with folder structure preservation"""
        if not self.ffmpeg_path:
            return False, "ffmpeg not found"
        
        try:
            input_path = Path(input_path)
            output_dir = Path(output_dir)
            
            if relative_path:
                # Preserve the original folder structure
                output_path = output_dir / relative_path.with_suffix('.flac')
                print(f"Preserving structure - Output file will be: {output_path}")
            else:
                # Fallback: just use filename
                output_path = output_dir / f"{input_path.stem}.flac"
                print(f"No relative path - Output file will be: {output_path}")
            
            # Create output directory if it doesn't exist
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Build ffmpeg command
            cmd = [
                self.ffmpeg_path,
                '-i', str(input_path),
                '-acodec', 'flac',
                '-y',  # Overwrite output files
                str(output_path)
            ]
            
            print(f"Running command: {' '.join(cmd)}")
            
            # Run conversion
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                return True, str(output_path)
            else:
                print(f"Conversion failed with error: {result.stderr}")
                return False, result.stderr
                
        except Exception as e:
            return False, str(e)

class FLACConverterApp:
    """Main GUI application"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("FLAC Converter - Audio File Converter")
        self.root.geometry("800x600")
        self.root.minsize(700, 500)
        
        # Initialize converter
        self.converter = AudioConverter()
        self.files_to_convert = []
        self.file_info = []  # Store file info with original paths
        self.output_directory = None
        self.common_root = None  # Track common root for folder structure
        self.conversion_thread = None  # Track conversion thread
        self.stop_conversion = False  # Flag to stop conversion
        
        # Setup UI
        self.setup_ui()
        
        # Check ffmpeg
        if not self.converter.ffmpeg_path:
            messagebox.showerror("Error", "ffmpeg not found. Please install ffmpeg.")
    
    def setup_ui(self):
        """Setup the user interface"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # Header section
        header_frame = ttk.Frame(main_frame)
        header_frame.grid(row=0, column=0, columnspan=3, pady=(0, 20), sticky=(tk.W, tk.E))
        
        # Title
        title_label = ttk.Label(header_frame, text="🎵 FLAC Converter", 
                               font=('Helvetica', 20, 'bold'))
        title_label.pack()
        
        # Subtitle
        subtitle_label = ttk.Label(header_frame, text="High-quality audio conversion with folder structure preservation", 
                                  font=('Helvetica', 11), foreground='#666666')
        subtitle_label.pack(pady=(5, 0))
        
        # File selection buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=1, column=0, columnspan=3, pady=(0, 15), sticky=(tk.W, tk.E))
        
        # Style the buttons
        button_style = {'width': 15, 'padding': (10, 5)}
        
        ttk.Button(button_frame, text="📁 Select Files", 
                  command=self.select_files, **button_style).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="📂 Select Folder", 
                  command=self.select_folder, **button_style).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="🗑️ Clear List", 
                  command=self.clear_list, **button_style).pack(side=tk.LEFT)
        
        # File list
        self.setup_file_list(main_frame)
        
        # Progress section
        self.setup_progress_section(main_frame)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready - Select files to convert")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, 
                              relief=tk.SUNKEN, anchor=tk.W, padding=(10, 5))
        status_bar.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
    
    def setup_file_list(self, parent):
        """Setup the file list"""
        files_frame = ttk.LabelFrame(parent, text="Files to Convert", padding="10")
        files_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 15))
        files_frame.columnconfigure(0, weight=1)
        files_frame.rowconfigure(0, weight=1)
        
        # Files treeview
        columns = ('File', 'Path', 'Size', 'Status')
        self.files_tree = ttk.Treeview(files_frame, columns=columns, show='headings', height=10)
        
        # Configure columns
        self.files_tree.heading('File', text='File Name')
        self.files_tree.heading('Path', text='Folder Path')
        self.files_tree.heading('Size', text='Size')
        self.files_tree.heading('Status', text='Status')
        
        self.files_tree.column('File', width=200, minwidth=150)
        self.files_tree.column('Path', width=300, minwidth=200)
        self.files_tree.column('Size', width=80, minwidth=60)
        self.files_tree.column('Status', width=100, minwidth=80)
        
        # Scrollbar
        files_scrollbar = ttk.Scrollbar(files_frame, orient=tk.VERTICAL, command=self.files_tree.yview)
        self.files_tree.configure(yscrollcommand=files_scrollbar.set)
        
        # Grid
        self.files_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        files_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Make files frame expand
        files_frame.columnconfigure(0, weight=1)
        files_frame.rowconfigure(0, weight=1)
    
    def setup_progress_section(self, parent):
        """Setup the progress tracking section"""
        progress_frame = ttk.LabelFrame(parent, text="Conversion Progress", padding="15")
        progress_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 15))
        progress_frame.columnconfigure(1, weight=1)
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, 
                                           maximum=100, mode='determinate', length=300)
        self.progress_bar.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 10))
        
        # Progress label
        self.progress_label = ttk.Label(progress_frame, text="0%", font=('Helvetica', 10, 'bold'))
        self.progress_label.grid(row=0, column=2, padx=(0, 10))
        
        # Convert button
        self.convert_btn = ttk.Button(progress_frame, text="🔄 Start Conversion", 
                                     command=self.toggle_conversion, state=tk.DISABLED,
                                     width=20, padding=(10, 8))
        self.convert_btn.grid(row=1, column=1, pady=(15, 0))
        
        # Make progress frame expand
        progress_frame.columnconfigure(1, weight=1)
    
    def select_files(self):
        """Open file dialog to select files"""
        files = filedialog.askopenfilenames(
            title="Select Audio Files",
            filetypes=[
                ("Audio Files", "*.m4a *.mp3 *.wav *.aac *.ogg *.flac *.aiff *.aif"),
                ("M4A Files", "*.m4a"),
                ("MP3 Files", "*.mp3"),
                ("WAV Files", "*.wav"),
                ("AIFF Files", "*.aiff *.aif"),
                ("All Files", "*.*")
            ]
        )
        
        for file in files:
            self.add_file(file)
        
        self.update_convert_button()
        self.status_var.set(f"Added {len(files)} file(s)")
    
    def select_folder(self):
        """Open folder dialog to select folder"""
        folder = filedialog.askdirectory(title="Select Folder with Audio Files")
        if folder:
            self.add_folder(folder)
            self.update_convert_button()
            self.status_var.set(f"Added folder: {folder}")
    
    def clear_list(self):
        """Clear all files from the list"""
        for item in self.files_tree.get_children():
            self.files_tree.delete(item)
        self.files_to_convert.clear()
        self.file_info.clear()
        self.common_root = None
        self.stop_conversion = False
        self.conversion_thread = None
        self.convert_btn.config(text="🔄 Start Conversion", state=tk.DISABLED)
        self.progress_var.set(0)
        self.progress_label.config(text="0%")
        self.status_var.set("File list cleared")
    
    def add_file(self, file_path):
        """Add a single file to the list"""
        try:
            file_path = Path(file_path)
            if file_path.exists():
                # Get file size
                size = file_path.stat().st_size
                size_str = self.format_size(size)
                
                # Store file info with full path for now
                file_info = {
                    'path': str(file_path),
                    'size': size_str
                }
                self.file_info.append(file_info)
                
                # Add to treeview
                item = self.files_tree.insert('', 'end', values=(
                    file_path.name,
                    str(file_path.parent),
                    size_str,
                    'Pending'
                ))
                
                # Store full path
                self.files_tree.set(item, 'File', str(file_path))
                self.files_to_convert.append(str(file_path))
                
        except Exception as e:
            messagebox.showerror("Error", f"Error adding file {file_path}: {str(e)}")
    
    def _find_common_root(self, root1, root2):
        """Find the common root between two paths"""
        try:
            # Don't resolve symlinks to avoid /private prefix issues
            root1 = Path(root1)
            root2 = Path(root2)
            
            # Find common parts
            parts1 = root1.parts
            parts2 = root2.parts
            
            common_parts = []
            for part1, part2 in zip(parts1, parts2):
                if part1 == part2:
                    common_parts.append(part1)
                else:
                    break
            
            if common_parts:
                return Path(*common_parts)
            else:
                # No common root, use the parent of the first file
                return root1.parent
        except:
            return root1
    
    def add_folder(self, folder_path):
        """Add all audio files from a folder"""
        try:
            folder_path = Path(folder_path)
            audio_extensions = {'.m4a', '.mp3', '.wav', '.aac', '.ogg', '.flac', '.aiff', '.aif'}
            
            for file_path in folder_path.rglob('*'):
                if file_path.is_file() and file_path.suffix.lower() in audio_extensions:
                    self.add_file(file_path)
                    
        except Exception as e:
            messagebox.showerror("Error", f"Error processing folder {folder_path}: {str(e)}")
    
    def update_convert_button(self):
        """Update the convert button state"""
        if self.files_tree.get_children():
            if self.conversion_thread and self.conversion_thread.is_alive():
                # Conversion is running, show stop button
                self.convert_btn.config(state=tk.NORMAL, text="🛑 Stop Conversion")
            else:
                # No conversion running, show start button
                self.convert_btn.config(state=tk.NORMAL, text="🔄 Start Conversion")
        else:
            # No files, disable button
            self.convert_btn.config(state=tk.DISABLED, text="🔄 Start Conversion")
    
    def toggle_conversion(self):
        """Toggle between start and stop conversion"""
        if self.conversion_thread and self.conversion_thread.is_alive():
            # Stop conversion
            self.stop_conversion = True
            self.convert_btn.config(text="🛑 Stopping...", state=tk.DISABLED)
            self.status_var.set("Stopping conversion...")
        else:
            # Start conversion
            self.start_conversion()
    
    def calculate_common_root(self):
        """Calculate the common root of all selected files"""
        if not self.files_to_convert:
            return None
        
        paths = [Path(f) for f in self.files_to_convert]
        common_root = paths[0].parent
        
        for path in paths[1:]:
            common_root = self._find_common_root(common_root, path.parent)
        
        return common_root
    
    def start_conversion(self):
        """Start the conversion process"""
        if not self.files_to_convert:
            return
        
        # Get output directory
        self.output_directory = filedialog.askdirectory(title="Select Output Directory")
        if not self.output_directory:
            return
        
        # Calculate common root for all files
        self.common_root = self.calculate_common_root()
        print(f"Common root calculated: {self.common_root}")
        
        # Reset stop flag
        self.stop_conversion = False
        
        # Start conversion in background
        self.convert_btn.config(text="🛑 Stop Conversion", state=tk.NORMAL)
        self.progress_var.set(0)
        
        # Start conversion thread
        self.conversion_thread = threading.Thread(target=self.conversion_worker, daemon=True)
        self.conversion_thread.start()
        
        self.status_var.set("Conversion started...")
    
    def conversion_worker(self):
        """Background worker for conversion"""
        try:
            total_files = len(self.files_to_convert)
            converted_count = 0
            
            for i, file_path in enumerate(self.files_to_convert):
                # Check if stop was requested
                if self.stop_conversion:
                    self.root.after(0, self.conversion_stopped)
                    return
                
                # Update progress
                progress = (i / total_files) * 100
                self.root.after(0, self.update_progress, progress, f"Converting {Path(file_path).name}")
                
                # Calculate relative path for this file
                file_path_obj = Path(file_path)
                if self.common_root and self.common_root in file_path_obj.parents:
                    relative_path = Path(file_path_obj.relative_to(self.common_root))
                else:
                    relative_path = Path(file_path_obj.name)
                
                # Convert file
                success, result = self.converter.convert_file(file_path, self.output_directory, relative_path)
                
                # Update file status
                self.root.after(0, self.update_file_status, i, success, result)
                
                if success:
                    converted_count += 1
                
                # Update progress
                progress = ((i + 1) / total_files) * 100
                self.root.after(0, self.update_progress, progress, f"Completed {i + 1}/{total_files}")
            
            # Conversion complete
            self.root.after(0, self.conversion_complete)
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Conversion error: {str(e)}"))
            self.root.after(0, self.conversion_complete)
    
    def update_progress(self, progress, message):
        """Update progress bar and label"""
        self.progress_var.set(progress)
        self.progress_label.config(text=f"{progress:.1f}%")
        self.status_var.set(message)
    
    def update_file_status(self, index, success, result):
        """Update the status of a converted file"""
        try:
            items = self.files_tree.get_children()
            if 0 <= index < len(items):
                item = items[index]
                
                if success:
                    self.files_tree.set(item, 'Status', '✅ Success')
                else:
                    self.files_tree.set(item, 'Status', '❌ Failed')
                
        except Exception as e:
            print(f"Error updating file status: {e}")
    
    def conversion_stopped(self):
        """Called when conversion is stopped by user"""
        self.convert_btn.config(state=tk.NORMAL, text="🔄 Start Conversion")
        self.status_var.set("Conversion stopped by user")
        messagebox.showinfo("Stopped", "Conversion stopped by user")
    
    def conversion_complete(self):
        """Called when conversion is complete"""
        self.convert_btn.config(state=tk.NORMAL, text="🔄 Start Conversion")
        self.status_var.set("Conversion complete!")
        
        if self.output_directory:
            messagebox.showinfo("Complete", f"Conversion complete! Files saved to:\n{self.output_directory}")
    
    def format_size(self, size_bytes):
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"

def main():
    """Main entry point"""
    # Check if tkinter is available
    try:
        import tkinter
    except ImportError:
        print("Error: tkinter is not available. Please install Python with tkinter support.")
        sys.exit(1)
    
    # Create and run the application
    root = tk.Tk()
    app = FLACConverterApp(root)
    
    # Start the main loop
    root.mainloop()

if __name__ == "__main__":
    main()

