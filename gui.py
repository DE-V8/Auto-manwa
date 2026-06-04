import os
import sys
import json
import shutil
import queue
import threading
import subprocess
import io
import customtkinter as ctk
from tkinter import filedialog, messagebox


def get_base_dir():
    """
    Returns the base directory of the app whether running as:
    - A regular Python script  → the folder containing gui.py
    - A frozen PyInstaller exe → the folder containing AtoManwa.exe (sys.executable)
    """
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle — exe sits in dist/AtoManwa/
        return os.path.dirname(sys.executable)
    # Running as plain Python script
    return os.path.dirname(os.path.abspath(__file__))


def get_bundle_dir():
    """
    Returns the bundle directory containing packaged assets (e.g. data, tools).
    - When frozen (PyInstaller): sys._MEIPASS
    - When running as script: same directory as gui.py
    """
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = get_base_dir()
BUNDLE_DIR = get_bundle_dir()

# Add scripts directory to path
scripts_dir = os.path.join(BUNDLE_DIR, 'scripts')
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)
if BUNDLE_DIR not in sys.path:
    sys.path.insert(0, BUNDLE_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from scripts.gemini_helper import generate_script
from scripts.tts_helper import generate_voiceovers
from scripts.video_helper import assemble_video

# Set customtkinter appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
TOOLS_DIR = os.path.join(BASE_DIR, "tools")
COMICS_DOWNLOADER_EXE = os.path.join(TOOLS_DIR, "comics-downloader.exe")


class GUIStdoutRedirector:
    """Redirects standard output to a thread-safe Queue."""
    def __init__(self, log_queue):
        self.log_queue = log_queue

    def write(self, string):
        self.log_queue.put(string)

    def flush(self):
        pass


class ChapterQueueItem(ctk.CTkFrame):
    """A single row in the Chapter Queue list showing path + remove button."""
    def __init__(self, parent, path, remove_callback, index, **kwargs):
        super().__init__(parent, corner_radius=6, fg_color="#1e2530", **kwargs)
        self.path = path
        self.grid_columnconfigure(0, weight=1)

        label_text = f"  [{index}]  {os.path.basename(path)}"
        self.label = ctk.CTkLabel(
            self, text=label_text, anchor="w",
            font=ctk.CTkFont(size=11), text_color="#c8cdd5"
        )
        self.label.grid(row=0, column=0, sticky="ew", padx=(6, 0), pady=4)

        self.remove_btn = ctk.CTkButton(
            self, text="✕", width=28, height=24,
            fg_color="#5a1e1e", hover_color="#7a2e2e",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda: remove_callback(self)
        )
        self.remove_btn.grid(row=0, column=1, padx=(4, 6), pady=4)


class ManhwaShortsGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configure window
        self.title("Ato Manwa - Hindi Video Generator")
        self.geometry("1100x820")
        self.resizable(True, True)
        self.minsize(950, 700)

        # Load Config
        self.config = self.load_config()
        self.last_output_path = ""
        self._chapter_queue_paths = []   # list of str paths in queue order

        # Scan for background music files (both bundled and user-provided next to EXE)
        bundled_music_dir = os.path.abspath(os.path.join(BUNDLE_DIR, "data", "music"))
        self.music_dir = os.path.abspath(os.path.join(BASE_DIR, "data", "music"))
        os.makedirs(self.music_dir, exist_ok=True)
        valid_music_exts = (".mp3", ".wav", ".ogg")
        
        music_files = set()
        for d in (bundled_music_dir, self.music_dir):
            if os.path.exists(d):
                for f in os.listdir(d):
                    if f.lower().endswith(valid_music_exts):
                        music_files.add(f)
        self.music_options = ["No Music"] + sorted(list(music_files))

        # Main grid layout
        self.grid_columnconfigure(0, weight=4, minsize=520)  # Left panel
        self.grid_columnconfigure(1, weight=5, minsize=580)  # Right panel
        self.grid_rowconfigure(0, weight=1)

        # Create Left scrollable frame and Right Parent Frame
        self.left_frame = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color="transparent")
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=(20, 5), pady=20)
        self.left_frame.grid_columnconfigure(0, weight=1)

        self.right_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 20), pady=20)
        self.right_frame.grid_columnconfigure(0, weight=1)
        self.right_frame.grid_rowconfigure(0, weight=1)

        # --- LEFT PANEL COMPONENTS ---

        # 1. Title/Header
        self.title_label = ctk.CTkLabel(self.left_frame, text="ATO MANWA", font=ctk.CTkFont(family="Impact", size=36))
        self.title_label.grid(row=0, column=0, sticky="w", pady=(0, 5))

        self.subtitle_label = ctk.CTkLabel(
            self.left_frame, text="Hindi Manhwa Video Recaps & Shorts",
            font=ctk.CTkFont(size=13, weight="bold"), text_color="grey"
        )
        self.subtitle_label.grid(row=1, column=0, sticky="w", pady=(0, 10))

        # 2. Config Box Frame
        self.config_frame = ctk.CTkFrame(self.left_frame, corner_radius=10, border_width=1, border_color="#333333")
        self.config_frame.grid(row=2, column=0, sticky="ew", pady=(0, 12), padx=5)
        self.config_frame.grid_columnconfigure(0, weight=1)
        self.config_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self.config_frame, text="Settings & API Keys",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=15, pady=(10, 5))

        # API Key Field
        self.api_key_entry = ctk.CTkEntry(
            self.config_frame, placeholder_text="Gemini API Key (GEMINI_API_KEY)", show="*", width=300)
        self.api_key_entry.grid(row=1, column=0, columnspan=2, sticky="ew", padx=15, pady=5)

        saved_key = self.config.get("gemini", {}).get("api_key", "")
        if saved_key:
            self.api_key_entry.insert(0, saved_key)

        # Dropdowns side-by-side: Voice and Subtitle Color
        ctk.CTkLabel(self.config_frame, text="Narration Voice:").grid(row=2, column=0, sticky="w", padx=15, pady=(5, 0))
        self.voice_var = ctk.StringVar(value=self.config.get("tts", {}).get("voice", "hi-IN-MadhurNeural"))
        self.voice_dropdown = ctk.CTkOptionMenu(
            self.config_frame, values=["hi-IN-MadhurNeural", "hi-IN-SwaraNeural"], variable=self.voice_var)
        self.voice_dropdown.grid(row=3, column=0, padx=15, pady=(2, 10), sticky="ew")

        ctk.CTkLabel(self.config_frame, text="Subtitle Color:").grid(row=2, column=1, sticky="w", padx=15, pady=(5, 0))
        saved_color_hex = self.config.get("video", {}).get("subtitle_color", "#FFFF00").upper()
        color_map_hex_to_name = {
            "#FFFF00": "Yellow", "#FFFFFF": "White", "#00FF00": "Green",
            "#00FFFF": "Cyan", "#FF0000": "Red", "#FF6B00": "Orange"
        }
        default_color_name = color_map_hex_to_name.get(saved_color_hex, "Yellow")
        self.color_var = ctk.StringVar(value=default_color_name)
        self.color_dropdown = ctk.CTkOptionMenu(
            self.config_frame,
            values=["Yellow", "White", "Green", "Cyan", "Red", "Orange"],
            variable=self.color_var
        )
        self.color_dropdown.grid(row=3, column=1, padx=15, pady=(2, 10), sticky="ew")

        # Subtitle Font Size and FFmpeg Preset
        ctk.CTkLabel(self.config_frame, text="Subtitle Font Size:").grid(row=4, column=0, sticky="w", padx=15, pady=(5, 0))
        saved_fontsize = str(self.config.get("video", {}).get("subtitle_fontsize", 55))
        self.fontsize_var = ctk.StringVar(value=saved_fontsize)
        self.fontsize_dropdown = ctk.CTkOptionMenu(
            self.config_frame, values=["35", "45", "55", "65", "75"], variable=self.fontsize_var)
        self.fontsize_dropdown.grid(row=5, column=0, padx=15, pady=(2, 10), sticky="ew")

        ctk.CTkLabel(self.config_frame, text="FFmpeg CPU Preset:").grid(row=4, column=1, sticky="w", padx=15, pady=(5, 0))
        saved_preset = self.config.get("video", {}).get("ffmpeg_preset", "ultrafast")
        self.preset_var = ctk.StringVar(value=saved_preset)
        self.preset_dropdown = ctk.CTkOptionMenu(
            self.config_frame,
            values=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium"],
            variable=self.preset_var
        )
        self.preset_dropdown.grid(row=5, column=1, padx=15, pady=(2, 10), sticky="ew")

        # GPU Acceleration Toggle
        self.gpu_switch = ctk.CTkSwitch(
            self.config_frame, text="GPU Acceleration (NVENC)", command=self.check_gpu_status)
        self.gpu_switch.grid(row=6, column=0, columnspan=2, sticky="w", padx=15, pady=(5, 2))
        saved_gpu = self.config.get("video", {}).get("use_gpu", True)
        if saved_gpu:
            self.gpu_switch.select()

        self.gpu_status_label = ctk.CTkLabel(
            self.config_frame, text="GPU: Checking...", font=ctk.CTkFont(size=11), text_color="grey")
        self.gpu_status_label.grid(row=7, column=0, columnspan=2, sticky="w", padx=15, pady=(0, 5))
        self.after(500, self.check_gpu_status)

        # Save Button
        self.save_key_btn = ctk.CTkButton(self.config_frame, text="Save Settings", command=self.save_settings)
        self.save_key_btn.grid(row=8, column=0, columnspan=2, sticky="ew", padx=15, pady=(5, 10))

        # 3. Comics Downloader Frame
        self.downloader_frame = ctk.CTkFrame(
            self.left_frame, corner_radius=10, border_width=1, border_color="#333333")
        self.downloader_frame.grid(row=3, column=0, sticky="ew", pady=(0, 12), padx=5)
        self.downloader_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.downloader_frame, text="Chapter Downloader (comics-downloader)",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=15, pady=(10, 5))

        self.url_entry = ctk.CTkEntry(
            self.downloader_frame, placeholder_text="Enter Chapter URL (e.g. Manganato chapter link)")
        self.url_entry.grid(row=1, column=0, sticky="ew", padx=15, pady=5)

        self.download_btn = ctk.CTkButton(
            self.downloader_frame, text="Download Chapter Images",
            fg_color="#1f538d", hover_color="#14375e", command=self.start_download)
        self.download_btn.grid(row=2, column=0, sticky="ew", padx=15, pady=(5, 15))

        # 4. Video Generator Frame
        self.generator_frame = ctk.CTkFrame(
            self.left_frame, corner_radius=10, border_width=1, border_color="#333333")
        self.generator_frame.grid(row=4, column=0, sticky="ew", pady=(0, 5), padx=5)
        self.generator_frame.grid_columnconfigure(0, weight=1)
        self.generator_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self.generator_frame, text="Video Generator Options",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=15, pady=(10, 5))

        # --- Single Chapter Quick-Select Row ---
        single_label = ctk.CTkLabel(
            self.generator_frame, text="Single Chapter (Quick):",
            font=ctk.CTkFont(size=12), text_color="#aaaaaa"
        )
        single_label.grid(row=1, column=0, columnspan=2, sticky="w", padx=15, pady=(5, 0))

        self.folder_select_frame = ctk.CTkFrame(self.generator_frame, fg_color="transparent")
        self.folder_select_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=15, pady=(2, 5))
        self.folder_select_frame.grid_columnconfigure(0, weight=1)
        self.folder_select_frame.grid_columnconfigure(1, weight=1)

        self.folder_entry = ctk.CTkEntry(
            self.folder_select_frame, placeholder_text="Select Images Folder or PDF file...")
        self.folder_entry.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 5))

        default_sample = os.path.join(BUNDLE_DIR, "data", "sample_chapter")
        if os.path.exists(default_sample):
            self.folder_entry.insert(0, default_sample)

        self.browse_btn = ctk.CTkButton(
            self.folder_select_frame, text="Browse Folder / PDF", command=self.browse_folder)
        self.browse_btn.grid(row=1, column=0, padx=(0, 5), sticky="ew")

        self.select_files_btn = ctk.CTkButton(
            self.folder_select_frame, text="Select Images Directly",
            fg_color="#444444", hover_color="#555555", command=self.select_images_directly)
        self.select_files_btn.grid(row=1, column=1, padx=(5, 0), sticky="ew")

        # --- Multi-Chapter Queue Section ---
        queue_section_label = ctk.CTkLabel(
            self.generator_frame,
            text="📚  Multi-Chapter Queue  (2-3 chapters → 1 combined video)",
            font=ctk.CTkFont(size=12, weight="bold"), text_color="#e09030"
        )
        queue_section_label.grid(row=3, column=0, columnspan=2, sticky="w", padx=15, pady=(10, 3))

        # Queue scrollable list
        self.queue_listbox = ctk.CTkScrollableFrame(
            self.generator_frame, height=90, corner_radius=6,
            fg_color="#12161e", border_width=1, border_color="#2a3040"
        )
        self.queue_listbox.grid(row=4, column=0, columnspan=2, sticky="ew", padx=15, pady=(0, 4))
        self.queue_listbox.grid_columnconfigure(0, weight=1)

        self._queue_empty_label = ctk.CTkLabel(
            self.queue_listbox,
            text="No chapters queued. Use 'Add to Queue' to add up to 3 chapters.",
            font=ctk.CTkFont(size=11), text_color="#555"
        )
        self._queue_empty_label.grid(row=0, column=0, padx=10, pady=20)

        # Queue buttons row
        self.queue_btn_frame = ctk.CTkFrame(self.generator_frame, fg_color="transparent")
        self.queue_btn_frame.grid(row=5, column=0, columnspan=2, sticky="ew", padx=15, pady=(0, 5))
        self.queue_btn_frame.grid_columnconfigure(0, weight=1)
        self.queue_btn_frame.grid_columnconfigure(1, weight=1)
        self.queue_btn_frame.grid_columnconfigure(2, weight=1)

        self.add_queue_btn = ctk.CTkButton(
            self.queue_btn_frame, text="➕  Add to Queue",
            fg_color="#1f538d", hover_color="#14375e",
            command=self.add_chapter_to_queue
        )
        self.add_queue_btn.grid(row=0, column=0, padx=(0, 4), sticky="ew")

        self.queue_mode_label = ctk.CTkLabel(
            self.queue_btn_frame,
            text="0 / 3 chapters",
            font=ctk.CTkFont(size=11), text_color="#777"
        )
        self.queue_mode_label.grid(row=0, column=1, sticky="ew")

        self.clear_queue_btn = ctk.CTkButton(
            self.queue_btn_frame, text="🗑  Clear Queue",
            fg_color="#5a2a1a", hover_color="#7a3a2a",
            command=self.clear_chapter_queue
        )
        self.clear_queue_btn.grid(row=0, column=2, padx=(4, 0), sticky="ew")

        # Queue use info
        self.queue_info_label = ctk.CTkLabel(
            self.generator_frame,
            text="ℹ️  Queue overrides the Single Chapter field when non-empty.",
            font=ctk.CTkFont(size=11), text_color="#666"
        )
        self.queue_info_label.grid(row=6, column=0, columnspan=2, sticky="w", padx=15, pady=(0, 5))

        # Divider
        divider = ctk.CTkFrame(self.generator_frame, height=1, fg_color="#2a3040")
        divider.grid(row=7, column=0, columnspan=2, sticky="ew", padx=15, pady=(5, 8))

        # Layout Format and Target Duration
        ctk.CTkLabel(self.generator_frame, text="Layout Format:").grid(
            row=8, column=0, sticky="w", padx=15, pady=(5, 0))
        self.format_var = ctk.StringVar(value="Shorts (Vertical 9:16)")
        self.format_dropdown = ctk.CTkOptionMenu(
            self.generator_frame,
            values=["Shorts (Vertical 9:16)", "Long Recap (Horizontal 16:9)"],
            variable=self.format_var
        )
        self.format_dropdown.grid(row=8, column=0, padx=15, pady=(25, 5), sticky="ew")

        ctk.CTkLabel(self.generator_frame, text="Target Duration:").grid(
            row=8, column=1, sticky="w", padx=15, pady=(5, 0))
        self.duration_var = ctk.StringVar(value="60 seconds")
        self.duration_dropdown = ctk.CTkOptionMenu(
            self.generator_frame,
            values=["30 seconds", "60 seconds", "90 seconds", "Full Chapter"],
            variable=self.duration_var
        )
        self.duration_dropdown.grid(row=8, column=1, padx=15, pady=(25, 5), sticky="ew")

        # Background Music Controls
        ctk.CTkLabel(self.generator_frame, text="Background Music:").grid(
            row=9, column=0, sticky="w", padx=15, pady=(5, 0))
        self.music_var = ctk.StringVar(value="No Music")
        self.music_dropdown = ctk.CTkOptionMenu(
            self.generator_frame, values=self.music_options, variable=self.music_var)
        self.music_dropdown.grid(row=9, column=0, padx=15, pady=(25, 5), sticky="ew")

        # Music Volume Slider Frame
        self.volume_frame = ctk.CTkFrame(self.generator_frame, fg_color="transparent")
        self.volume_frame.grid(row=9, column=1, sticky="ew", padx=15, pady=(20, 5))
        self.volume_frame.grid_columnconfigure(0, weight=1)

        saved_vol = self.config.get("video", {}).get("bg_music_volume", 0.10)
        saved_vol_percent = int(saved_vol * 100)

        self.volume_label = ctk.CTkLabel(self.volume_frame, text=f"Volume: {saved_vol_percent}%")
        self.volume_label.grid(row=0, column=0, sticky="w")

        self.volume_slider = ctk.CTkSlider(
            self.volume_frame, from_=0, to=50, number_of_steps=10, command=self.update_volume_label)
        self.volume_slider.set(saved_vol_percent)
        self.volume_slider.grid(row=1, column=0, sticky="ew")

        # Split switch
        self.split_switch = ctk.CTkSwitch(
            self.generator_frame, text="Split Chapter into 2 Parts (Option B)")
        self.split_switch.grid(row=10, column=0, columnspan=2, sticky="w", padx=15, pady=(10, 2))

        # Mock switch
        self.mock_switch = ctk.CTkSwitch(
            self.generator_frame, text="Mock Mode (Run offline test without Gemini API key)")
        self.mock_switch.grid(row=11, column=0, columnspan=2, sticky="w", padx=15, pady=(2, 10))
        self.mock_switch.select()

        # --- START BUTTON ---
        self.start_btn = ctk.CTkButton(
            self.generator_frame,
            text="▶  START GENERATION",
            font=ctk.CTkFont(size=18, weight="bold"),
            height=52,
            fg_color="#e05c00",
            hover_color="#a84400",
            corner_radius=10,
            command=self.start_generation
        )
        self.start_btn.grid(row=12, column=0, columnspan=2, sticky="ew", padx=15, pady=(10, 5))

        self.generate_btn = ctk.CTkButton(
            self.generator_frame, text="⚡ Generate video ⚡",
            font=ctk.CTkFont(size=13, weight="bold"), height=34,
            fg_color="#2b7a42", hover_color="#1d522c",
            command=self.start_generation
        )
        self.generate_btn.grid(row=13, column=0, columnspan=2, sticky="ew", padx=15, pady=(0, 5))

        # Visual Progress Bar
        self.progress_bar = ctk.CTkProgressBar(
            self.generator_frame, orientation="horizontal", mode="determinate")
        self.progress_bar.grid(row=14, column=0, columnspan=2, sticky="ew", padx=15, pady=(0, 15))
        self.progress_bar.set(0)

        # --- RIGHT PANEL COMPONENTS ---

        # 1. Scrollable Console/Log
        self.console_frame = ctk.CTkFrame(
            self.right_frame, corner_radius=10, border_width=1, border_color="#333333")
        self.console_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 15))
        self.console_frame.grid_columnconfigure(0, weight=1)
        self.console_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(self.console_frame, text="Pipeline Execution Logs",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=15, pady=(10, 5))

        self.log_textbox = ctk.CTkTextbox(
            self.console_frame, font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#0b0e14", text_color="#abb2bf", state="disabled")
        self.log_textbox.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))

        # Initialize thread-safe log queue and redirect stdout/stderr
        self.log_queue = queue.Queue()
        self.stdout_redirector = GUIStdoutRedirector(self.log_queue)
        self._real_stdout = sys.__stdout__
        self._real_stderr = sys.__stderr__
        sys.stdout = self.stdout_redirector
        sys.stderr = self.stdout_redirector

        self.check_log_queue()

        # 2. Output Preview Panel
        self.output_frame = ctk.CTkFrame(
            self.right_frame, corner_radius=10, border_width=1, border_color="#333333")
        self.output_frame.grid(row=1, column=0, sticky="ew")
        self.output_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.output_frame, text="Render Output",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=15, pady=(10, 0))

        # --- Save Location Picker ---
        self.save_loc_frame = ctk.CTkFrame(self.output_frame, fg_color="transparent")
        self.save_loc_frame.grid(row=1, column=0, sticky="ew", padx=15, pady=(4, 2))
        self.save_loc_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self.save_loc_frame,
            text="📁  Save Video To:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 3))

        self.save_location_entry = ctk.CTkEntry(
            self.save_loc_frame,
            placeholder_text="Default: generated/videos/  (click Browse to change)",
            font=ctk.CTkFont(size=11)
        )
        self.save_location_entry.grid(row=1, column=0, sticky="ew", padx=(0, 6))

        self.browse_save_btn = ctk.CTkButton(
            self.save_loc_frame,
            text="Browse",
            width=80,
            fg_color="#1f538d",
            hover_color="#14375e",
            command=self.browse_save_location
        )
        self.browse_save_btn.grid(row=1, column=1)

        self.reset_save_btn = ctk.CTkButton(
            self.save_loc_frame,
            text="Reset to Default",
            width=120,
            height=24,
            fg_color="transparent",
            hover_color="#2a2a2a",
            border_width=1,
            border_color="#444",
            font=ctk.CTkFont(size=11),
            command=self.reset_save_location
        )
        self.reset_save_btn.grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # --- Last render status label ---
        self.output_path_label = ctk.CTkLabel(
            self.output_frame, text="No video generated yet.",
            font=ctk.CTkFont(size=12, slant="italic"), text_color="grey")
        self.output_path_label.grid(row=2, column=0, sticky="w", padx=15, pady=(6, 2))

        self.buttons_frame = ctk.CTkFrame(self.output_frame, fg_color="transparent")
        self.buttons_frame.grid(row=3, column=0, sticky="ew", padx=15, pady=(0, 15))

        self.open_folder_btn = ctk.CTkButton(
            self.buttons_frame, text="Open Folder", width=120,
            state="disabled", command=self.open_output_folder)
        self.open_folder_btn.pack(side="left", padx=(0, 10))

        self.play_video_btn = ctk.CTkButton(
            self.buttons_frame, text="Play Video ▶", width=120,
            fg_color="#333333", hover_color="#444444",
            state="disabled", command=self.play_video)
        self.play_video_btn.pack(side="left")

        print("Ato Manwa GUI Initialized. Ready to generate!")
        print("[INFO] Use the ▶ START GENERATION button or ⚡ Generate video ⚡ to begin.")
        print("[INFO] Multi-Chapter Queue: Add 2-3 chapters to combine into 1 video.")

    # -----------------------------------------------------------------------
    # Chapter Queue Management
    # -----------------------------------------------------------------------

    def _refresh_queue_display(self):
        """Rebuild the visible queue list from _chapter_queue_paths."""
        # Destroy all existing children
        for widget in self.queue_listbox.winfo_children():
            widget.destroy()

        if not self._chapter_queue_paths:
            self._queue_empty_label = ctk.CTkLabel(
                self.queue_listbox,
                text="No chapters queued. Use 'Add to Queue' to add up to 3 chapters.",
                font=ctk.CTkFont(size=11), text_color="#555"
            )
            self._queue_empty_label.grid(row=0, column=0, padx=10, pady=20)
        else:
            for i, path in enumerate(self._chapter_queue_paths):
                item = ChapterQueueItem(
                    self.queue_listbox, path,
                    remove_callback=self._remove_queue_item,
                    index=i + 1
                )
                item.grid(row=i, column=0, sticky="ew", padx=4, pady=(2, 0))
                self.queue_listbox.grid_columnconfigure(0, weight=1)

        count = len(self._chapter_queue_paths)
        self.queue_mode_label.configure(text=f"{count} / 3 chapters")

    def _remove_queue_item(self, item_widget):
        """Remove a chapter from the queue by its widget."""
        path = item_widget.path
        if path in self._chapter_queue_paths:
            self._chapter_queue_paths.remove(path)
        self._refresh_queue_display()

    def add_chapter_to_queue(self):
        """Open a browser dialog and add the selected path to the queue."""
        if len(self._chapter_queue_paths) >= 3:
            messagebox.showwarning(
                "Queue Full",
                "You can queue a maximum of 3 chapters at a time.\n"
                "Remove one before adding more."
            )
            return

        choice = messagebox.askyesno(
            "Add to Queue",
            "Would you like to add a PDF File?\n\n(Click 'No' to add a Folder instead)"
        )
        if choice:
            path = filedialog.askopenfilename(
                title="Select Manhwa PDF File for Queue",
                filetypes=[("PDF Files", "*.pdf")]
            )
        else:
            path = filedialog.askdirectory(title="Select Chapter Images Directory for Queue")

        if path:
            if path in self._chapter_queue_paths:
                messagebox.showinfo("Already Added", "This chapter is already in the queue.")
                return
            self._chapter_queue_paths.append(path)
            self._refresh_queue_display()
            print(f"[QUEUE] Added: {os.path.basename(path)}  ({len(self._chapter_queue_paths)}/3)")

    def clear_chapter_queue(self):
        """Remove all entries from the queue."""
        if self._chapter_queue_paths:
            self._chapter_queue_paths.clear()
            self._refresh_queue_display()
            print("[QUEUE] Queue cleared.")

    # -----------------------------------------------------------------------
    # Log & UI helpers
    # -----------------------------------------------------------------------

    def check_log_queue(self):
        MAX_LINES_PER_CYCLE = 50
        processed = 0
        while not self.log_queue.empty() and processed < MAX_LINES_PER_CYCLE:
            try:
                string = self.log_queue.get_nowait()
                processed += 1
                if string.startswith("[PROGRESS_VAL]:"):
                    try:
                        val = float(string.split(":")[1])
                        self.progress_bar.set(val)
                    except ValueError:
                        pass
                else:
                    self.log_textbox.configure(state="normal")
                    self.log_textbox.insert("end", string)
                    self.log_textbox.see("end")
                    self.log_textbox.configure(state="disabled")
            except queue.Empty:
                break
        self.after(100, self.check_log_queue)

    def update_volume_label(self, val):
        self.volume_label.configure(text=f"Volume: {int(val)}%")

    def check_gpu_status(self):
        use_gpu = self.gpu_switch.get()
        if not use_gpu:
            self.gpu_status_label.configure(text="GPU: Disabled (using CPU)", text_color="grey")
            return

        def _check():
            try:
                result = subprocess.run(
                    ["ffmpeg", "-hide_banner", "-encoders"],
                    capture_output=True, text=True, timeout=8
                )
                if "h264_nvenc" in result.stdout:
                    self.gpu_status_label.configure(
                        text="✅ GPU NVENC Available! Rendering will be accelerated.",
                        text_color="#2bc97a"
                    )
                else:
                    self.gpu_status_label.configure(
                        text="⚠️ NVENC not found — will fall back to CPU.",
                        text_color="#f0a500"
                    )
            except FileNotFoundError:
                self.gpu_status_label.configure(text="❌ ffmpeg not found in PATH.", text_color="#e05c5c")
            except Exception as e:
                self.gpu_status_label.configure(text=f"GPU check error: {e}", text_color="#e05c5c")

        threading.Thread(target=_check, daemon=True).start()

    def load_config(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def save_settings(self):
        key = self.api_key_entry.get().strip()
        voice = self.voice_var.get()
        color_name = self.color_var.get()
        font_size = int(self.fontsize_var.get())
        preset = self.preset_var.get()
        music_vol = self.volume_slider.get() / 100.0

        color_map_name_to_hex = {
            "Yellow": "#FFFF00", "White": "#FFFFFF", "Green": "#00FF00",
            "Cyan": "#00FFFF", "Red": "#FF0000", "Orange": "#FF6B00"
        }
        color_hex = color_map_name_to_hex.get(color_name, "#FFFF00")

        for section in ("gemini", "tts", "video"):
            if section not in self.config:
                self.config[section] = {}

        self.config["gemini"]["api_key"] = key
        self.config["tts"]["voice"] = voice
        self.config["video"]["subtitle_color"] = color_hex
        self.config["video"]["subtitle_fontsize"] = font_size
        self.config["video"]["ffmpeg_preset"] = preset
        self.config["video"]["bg_music_volume"] = music_vol
        self.config["video"]["use_gpu"] = bool(self.gpu_switch.get())

        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
            print("[INFO] Settings successfully saved to config.json!")
            messagebox.showinfo("Success", "Settings successfully saved!")
        except Exception as e:
            print(f"[ERROR] Failed to save settings: {e}")
            messagebox.showerror("Error", f"Failed to save settings: {e}")

    def browse_folder(self):
        choice = messagebox.askyesno(
            "Select Input Type",
            "Would you like to select a PDF File?\n\n(Click 'No' to select a Folder instead)"
        )
        if choice:
            file_path = filedialog.askopenfilename(
                title="Select Manhwa PDF File", filetypes=[("PDF Files", "*.pdf")])
            if file_path:
                self.folder_entry.delete(0, "end")
                self.folder_entry.insert(0, file_path)
                print(f"[INFO] Selected PDF: {file_path}")
        else:
            folder = filedialog.askdirectory(title="Select Chapter Images Directory")
            if folder:
                self.folder_entry.delete(0, "end")
                self.folder_entry.insert(0, folder)
                print(f"[INFO] Selected chapter folder: {folder}")

    def select_images_directly(self):
        files = filedialog.askopenfilenames(
            title="Select Image Panels Directly",
            filetypes=[("Image Files", "*.jpg *.jpeg *.png *.webp")]
        )
        if files:
            temp_dir = os.path.abspath(
                os.path.join(BASE_DIR, "generated", "temp", "selected_images"))
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            os.makedirs(temp_dir, exist_ok=True)

            for idx, file_path in enumerate(files):
                _, ext = os.path.splitext(file_path)
                dest_name = f"{idx+1:03d}{ext}"
                shutil.copy(file_path, os.path.join(temp_dir, dest_name))

            self.folder_entry.delete(0, "end")
            self.folder_entry.insert(0, temp_dir)
            print(f"[INFO] Selected {len(files)} individual files. Copied sequentially to: {temp_dir}")

    # -----------------------------------------------------------------------
    # Download
    # -----------------------------------------------------------------------

    def start_download(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Warning", "Please enter a chapter URL first!")
            return

        if not os.path.exists(COMICS_DOWNLOADER_EXE):
            messagebox.showerror(
                "Error",
                f"comics-downloader.exe not found at:\n{COMICS_DOWNLOADER_EXE}\n\n"
                "Please run 'install_tools.py' first."
            )
            return

        self.download_btn.configure(state="disabled", text="Downloading...")
        thread = threading.Thread(target=self.run_download, args=(url,))
        thread.daemon = True
        thread.start()

    def run_download(self, url):
        print(f"\n--- Starting Download: {url} ---")
        try:
            cmd = [COMICS_DOWNLOADER_EXE, "-url", url, "-images-only"]
            process = subprocess.Popen(
                cmd, cwd=TOOLS_DIR,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, shell=True
            )
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                print(line, end="")

            process.wait()
            print("\n--- Download Task Finished ---")
            print("[INFO] Please move the downloaded images folder into the data/ directory.")
            messagebox.showinfo("Download Complete", "Chapter images downloaded!\nCheck the tools/ directory.")
        except Exception as e:
            print(f"[ERROR] Downloader failed: {e}")
            messagebox.showerror("Download Error", f"Failed to download: {e}")
        finally:
            self.download_btn.configure(state="normal", text="Download Chapter Images")

    # -----------------------------------------------------------------------
    # Generation Pipeline
    # -----------------------------------------------------------------------

    def start_generation(self):
        """Validate inputs and kick off background generation thread."""
        # Determine source: queue takes priority over single folder
        if self._chapter_queue_paths:
            chapter_sources = list(self._chapter_queue_paths)
            for src in chapter_sources:
                is_pdf = src.lower().endswith('.pdf')
                if not is_pdf and not os.path.isdir(src):
                    messagebox.showerror("Error", f"Queued path does not exist or is not a folder:\n{src}")
                    return
                elif is_pdf and not os.path.isfile(src):
                    messagebox.showerror("Error", f"Queued PDF file does not exist:\n{src}")
                    return
            print(f"[INFO] Using Chapter Queue: {len(chapter_sources)} chapter(s)")
        else:
            single = self.folder_entry.get().strip()
            if not single:
                messagebox.showwarning("Warning", "Please select a chapter images folder/PDF or add chapters to the queue!")
                return
            is_pdf = single.lower().endswith('.pdf')
            if not is_pdf and not os.path.isdir(single):
                messagebox.showerror("Error", f"Path '{single}' does not exist or is not a folder.")
                return
            elif is_pdf and not os.path.isfile(single):
                messagebox.showerror("Error", f"PDF File '{single}' does not exist.")
                return
            chapter_sources = [single]

        self.generate_btn.configure(state="disabled", text="Generating...")
        self.start_btn.configure(state="disabled", text="⏳ Generating...")
        use_gpu = bool(self.gpu_switch.get())

        thread = threading.Thread(
            target=self.run_generation, args=(chapter_sources, use_gpu), daemon=True)
        thread.start()

    def _resolve_chapter_images(self, sources):
        """
        Given a list of chapter source paths (folders or PDFs), resolve all image
        paths in order, and return:
            image_paths        — flat list of all image paths
            chapter_boundaries — list of start indices [0, n1, n1+n2, ...]
            combined_name      — a short label for the output filename
        """
        from main import natural_sort_key, extract_pdf_pages

        all_image_paths = []
        chapter_boundaries = []
        names = []
        valid_exts = ('.jpg', '.jpeg', '.png', '.webp')

        for src in sources:
            chapter_boundaries.append(len(all_image_paths))

            if src.lower().endswith('.pdf'):
                temp_pdf_dir = os.path.abspath(os.path.join(
                    BASE_DIR, 'generated', 'temp',
                    f'pdf_{os.path.splitext(os.path.basename(src))[0]}'
                ))
                extract_pdf_pages(src, temp_pdf_dir)
                chapter_dir = temp_pdf_dir
            else:
                chapter_dir = src

            img_filenames = sorted(
                [f for f in os.listdir(chapter_dir) if f.lower().endswith(valid_exts)],
                key=natural_sort_key
            )
            if not img_filenames:
                print(f"[WARNING] No images found in '{chapter_dir}'. Skipping.")
                continue

            for fn in img_filenames:
                all_image_paths.append(os.path.join(chapter_dir, fn))

            names.append(os.path.basename(src.rstrip('/\\')))
            print(f"[INFO] Chapter '{os.path.basename(src)}': {len(img_filenames)} panels loaded.")

        combined_name = "_and_".join(names) if len(names) > 1 else (names[0] if names else "output")
        return all_image_paths, chapter_boundaries, combined_name

    def run_generation(self, chapter_sources, use_gpu=True):
        """Main pipeline: script → voiceover → video."""
        print("[PROGRESS_VAL]:0.02")
        print(f"\n================ STARTING PIPELINE ================")
        ch_labels = " + ".join(os.path.basename(s) for s in chapter_sources)
        print(f"Chapters: {ch_labels}")

        try:
            # --- Resolve images from all chapters ---
            image_paths, chapter_boundaries, combined_name = self._resolve_chapter_images(chapter_sources)

            if not image_paths:
                print("[ERROR] No valid images found across all selected chapters.")
                messagebox.showerror("Error", "No valid images found in the selected chapter(s).")
                return

            print(f"[INFO] Total panels loaded: {len(image_paths)} across {len(chapter_sources)} chapter(s).")
            print(f"[INFO] Chapter boundaries at image indices: {chapter_boundaries}")

            use_mock = self.mock_switch.get()
            api_key = self.api_key_entry.get().strip()

            if not use_mock and not api_key:
                print("[ERROR] Gemini API Key is required for production mode!")
                messagebox.showerror("API Error", "Please provide a Gemini API Key or enable Mock Mode.")
                return

            model_name = self.config.get("gemini", {}).get("model", "gemini-2.5-flash")
            tts_voice = self.voice_var.get()

            # Sync current GUI settings into config dict
            color_map_name_to_hex = {
                "Yellow": "#FFFF00", "White": "#FFFFFF", "Green": "#00FF00",
                "Cyan": "#00FFFF", "Red": "#FF0000", "Orange": "#FF6B00"
            }
            color_hex = color_map_name_to_hex.get(self.color_var.get(), "#FFFF00")

            if "video" not in self.config:
                self.config["video"] = {}
            self.config["video"]["subtitle_color"] = color_hex
            self.config["video"]["subtitle_fontsize"] = int(self.fontsize_var.get())
            self.config["video"]["ffmpeg_preset"] = self.preset_var.get()
            self.config["video"]["use_gpu"] = use_gpu

            video_format = "horizontal" if self.format_var.get().startswith("Long") else "vertical"
            target_duration = (
                "30s" if "30" in self.duration_var.get()
                else "60s" if "60" in self.duration_var.get()
                else "90s" if "90" in self.duration_var.get()
                else "full"
            )
            split_parts = self.split_switch.get()

            selected_music = self.music_var.get()
            bg_music_path = None if selected_music == "No Music" else os.path.join(self.music_dir, selected_music)
            bg_music_volume = self.volume_slider.get() / 100.0

            print(f"[INFO] Config: Format={video_format}, Duration={target_duration}, "
                  f"Split={split_parts}, Music={selected_music}, Vol={int(self.volume_slider.get())}%")
            print("[PROGRESS_VAL]:0.15")

            # --- STEP 1: Script Generation ---
            print("\n--- STEP 1: Story Understanding & Script Generation via Gemini ---")
            if use_mock:
                print("[INFO] Running in MOCK Mode (multi-chapter aware)...")
                parts = self._build_mock_script(image_paths, chapter_boundaries, split_parts)
            else:
                script_data = generate_script(
                    image_paths,
                    api_key,
                    model_name=model_name,
                    video_format=video_format,
                    target_duration=target_duration,
                    split_parts=split_parts,
                    chapter_boundaries=chapter_boundaries,
                )
                parts = script_data.get("parts", [])
                if not parts:
                    print("[ERROR] Empty script response from Gemini.")
                    return

                # Resolve image filenames → full paths
                for part in parts:
                    for idx, seg in enumerate(part.get("segments", [])):
                        img_fn = seg["image_file"]
                        # Search across all image paths
                        matched = next(
                            (p for p in image_paths if os.path.basename(p) == img_fn), None
                        )
                        if matched:
                            seg["image_file"] = matched
                        else:
                            print(f"[WARNING] Image '{img_fn}' not found. Auto-mapping sequentially.")
                            seg["image_file"] = image_paths[min(idx, len(image_paths) - 1)]

            print(f"[INFO] Script generated: {len(parts)} video part(s).")
            print("[PROGRESS_VAL]:0.40")

            # --- STEP 2 + 3: Voiceover + Render for each part ---
            for p_idx, part in enumerate(parts):
                part_num = part.get("part_number", 1)
                part_title = part.get("part_title", f"Part {part_num}")
                segments = part.get("segments", [])

                print(f"\n================ PROCESSING: {part_title} ================")
                if not segments:
                    continue

                format_suffix = "horizontal" if video_format == "horizontal" else "shorts"
                suffix = f"_part{part_num}" if split_parts else ""

                # Use user-chosen save location if set, otherwise default
                custom_save_dir = self.save_location_entry.get().strip()
                if custom_save_dir and os.path.isdir(custom_save_dir):
                    output_dir = custom_save_dir
                else:
                    output_dir = os.path.join(BASE_DIR, 'generated', 'videos')
                os.makedirs(output_dir, exist_ok=True)
                output_path = os.path.abspath(
                    os.path.join(output_dir, f"{combined_name}{suffix}_{format_suffix}.mp4"))
                temp_audio_dir = os.path.join(
                    BASE_DIR, 'generated', 'temp', f'audio_part{part_num}')

                print(f"\n--- STEP 2: Voice Narration & Word Timing (Part {part_num}) ---")
                segments_with_audio = generate_voiceovers(segments, temp_audio_dir, voice=tts_voice)

                p_progress = 0.40 + (p_idx + 0.5) * (0.50 / len(parts))
                print(f"[PROGRESS_VAL]:{p_progress:.2f}")

                print(f"\n--- STEP 3: Video Rendering (Part {part_num}) ---")
                print("[INFO] Rendering video... GUI may be unresponsive during this step.")

                sys.stdout = self._real_stdout
                sys.stderr = self._real_stderr
                try:
                    assemble_video(
                        segments_with_audio, output_path, self.config,
                        video_format=video_format,
                        bg_music_path=bg_music_path,
                        bg_music_volume=bg_music_volume
                    )
                finally:
                    sys.stdout = self.stdout_redirector
                    sys.stderr = self.stdout_redirector

                print(f"[SUCCESS] Part {part_num} successfully created: {os.path.basename(output_path)}")

                self.last_output_path = output_path
                self.output_path_label.configure(
                    text=f"Saved: {os.path.basename(output_path)}", text_color="#2b7a42")
                self.open_folder_btn.configure(state="normal")
                self.play_video_btn.configure(
                    state="normal", fg_color="#1f538d", hover_color="#14375e")

                p_done_progress = 0.40 + (p_idx + 1) * (0.50 / len(parts))
                print(f"[PROGRESS_VAL]:{p_done_progress:.2f}")

            print(f"\n================ PIPELINE SUCCESS ================")
            print("[PROGRESS_VAL]:1.0")
            messagebox.showinfo(
                "Success",
                f"Generated {len(parts)} video part(s) successfully!\n\n"
                f"Source: {ch_labels}"
            )

        except Exception as e:
            import traceback
            print(f"\n[PIPELINE FAILURE] Error: {e}")
            print(traceback.format_exc())
            messagebox.showerror("Pipeline Failure", f"An error occurred during video creation:\n{e}")
        finally:
            self.generate_btn.configure(state="normal", text="⚡ Generate video ⚡")
            self.start_btn.configure(state="normal", text="▶  START GENERATION")

    def _build_mock_script(self, image_paths, chapter_boundaries, split_parts):
        """
        Build a realistic mock script that spans multiple chapters.
        chapter_boundaries: list of start-indices [0, n1, n2, ...]
        """
        num_chapters = len(chapter_boundaries)
        total = len(image_paths)

        def _seg(voice, sub, img_idx):
            return {
                "voice_text": voice,
                "subtitle_text": sub,
                "image_file": image_paths[min(img_idx, total - 1)]
            }

        if num_chapters >= 2:
            ch2_start = chapter_boundaries[1] if len(chapter_boundaries) > 1 else total // 2
        else:
            ch2_start = total // 2

        if split_parts:
            parts = [
                {
                    "part_number": 1,
                    "part_title": "Part 1: Chapter 1 — The Beginning",
                    "segments": [
                        _seg("सब लोग इस शिकारी को कमजोर समझते थे...", "Sab log is hunter ko kamzor samajhte the...", 0),
                        _seg("लेकिन डंगऑन के अंदर उसे एक सीक्रेट पॉवर मिली।", "lekin dungeon ke andar use ek secret power mili.", 1),
                        _seg("तभी उसके सामने एक भयानक मॉन्स्टर आ गया!", "Tabhi uske saamne ek bhayanak monster aa gaya!", min(2, total - 1)),
                    ]
                },
                {
                    "part_number": 2,
                    "part_title": "Part 2: Chapter 2 — The Revelation",
                    "segments": [
                        _seg("नए चैप्टर में सब कुछ बदल गया!", "Naye chapter mein sab kuch badal gaya!", ch2_start),
                        _seg("उसने अपनी गॉड-लेवल एबिलिटी एक्टिवेट की!", "Usne apni god-level ability activate ki!", min(ch2_start + 1, total - 1)),
                        _seg("एक ही वार में सब खत्म! पर असली कहानी अभी बाकी है।", "Ek hi waar mein sab khatam! Par asli kahani abhi baaki hai.", min(ch2_start + 2, total - 1)),
                    ]
                },
            ]
        else:
            segments = [
                _seg("सब लोग इस शिकारी को कमजोर समझते थे...", "Sab log is hunter ko kamzor samajhte the...", 0),
                _seg("लेकिन डंगऑन में उसे एक सीक्रेट पॉवर मिली।", "Lekin dungeon mein use ek secret power mili.", min(1, total - 1)),
                _seg("उसने अकेले ही सारे मॉन्सटर्स का खात्मा किया!", "Usne akele hi saare monsters ka khatma kiya!", min(2, total - 1)),
            ]
            if num_chapters >= 2:
                segments += [
                    _seg("नए चैप्टर में एक बड़ा खुलासा हुआ!", "Naye chapter mein ek bada khulasa hua!", ch2_start),
                    _seg("अब कोई भी उसके सामने टिक नहीं सकता था।", "Ab koi bhi uske saamne tik nahi sakta tha.", min(ch2_start + 1, total - 1)),
                ]
            segments.append(
                _seg("लेकिन असली ट्विस्ट अभी बाकी है... सब्सक्राइब करें!", "Lekin asli twist abhi baaki hai... Subscribe karein!", min(total - 1, total - 1))
            )
            parts = [{"part_number": 1, "part_title": "Full Multi-Chapter Recap", "segments": segments}]

        return parts

    # -----------------------------------------------------------------------
    # Output actions
    # -----------------------------------------------------------------------

    def browse_save_location(self):
        """Open a folder picker so the user can choose where to save rendered videos."""
        folder = filedialog.askdirectory(title="Choose Video Save Location")
        if folder:
            self.save_location_entry.delete(0, "end")
            self.save_location_entry.insert(0, folder)
            print(f"[INFO] Save location set to: {folder}")

    def reset_save_location(self):
        """Reset save location back to the default generated/videos/ folder."""
        self.save_location_entry.delete(0, "end")
        print("[INFO] Save location reset to default: generated/videos/")

    def open_output_folder(self):
        if self.last_output_path and os.path.exists(self.last_output_path):
            os.startfile(os.path.dirname(self.last_output_path))

    def play_video(self):
        if self.last_output_path and os.path.exists(self.last_output_path):
            os.startfile(self.last_output_path)



# =============================================================================
# FFmpeg Setup Wizard  — runs ONCE before the main app if FFmpeg is missing
# =============================================================================

class FFmpegSetupWizard(ctk.CTkToplevel):
    """
    A modal dialog shown on first run (or whenever FFmpeg is missing).
    Asks the user's permission, then downloads + extracts FFmpeg automatically.
    FFmpeg is stored in  <BASE_DIR>/tools/ffmpeg/  so no system-wide changes
    are needed and the app manages its own copy.
    """

    FFMPEG_URL = (
        "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    )
    FFMPEG_LOCAL_DIR = os.path.join(BASE_DIR, "tools", "ffmpeg")

    def __init__(self, parent, on_complete_callback):
        super().__init__(parent)
        self.on_complete_callback = on_complete_callback
        self._download_thread = None
        self._cancelled = False

        # --- Window setup ---
        self.title("FFmpeg Setup Required")
        self.geometry("540x440")
        self.resizable(False, False)
        self.grab_set()          # Make it modal (blocks the parent)
        self.lift()
        self.focus_force()

        # Close = skip (let app open anyway)
        self.protocol("WM_DELETE_WINDOW", self._on_skip)

        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)

        # Header icon + title
        header = ctk.CTkFrame(self, fg_color="#1a1f2e", corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="⚙️  FFmpeg Setup",
            font=ctk.CTkFont(size=22, weight="bold")
        ).grid(row=0, column=0, pady=(20, 4))

        ctk.CTkLabel(
            header, text="One-time setup to enable video rendering",
            font=ctk.CTkFont(size=12), text_color="#888"
        ).grid(row=1, column=0, pady=(0, 16))

        # Body
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="ew", padx=30, pady=(20, 0))
        body.grid_columnconfigure(0, weight=1)

        info_text = (
            "AtoManwa needs FFmpeg to create videos.\n\n"
            "FFmpeg is a free, open-source tool used by millions of video apps.\n"
            "It will be downloaded (~80 MB) and saved inside the app folder —\n"
            "no system installation or admin rights required.\n\n"
            "Source:  www.gyan.dev/ffmpeg/builds  (official Windows builds)"
        )
        ctk.CTkLabel(
            body, text=info_text,
            font=ctk.CTkFont(size=12), justify="left",
            wraplength=460, anchor="w"
        ).grid(row=0, column=0, sticky="w")

        # Progress section (hidden initially)
        self.progress_frame = ctk.CTkFrame(body, fg_color="transparent")
        self.progress_frame.grid(row=1, column=0, sticky="ew", pady=(16, 0))
        self.progress_frame.grid_columnconfigure(0, weight=1)
        self.progress_frame.grid_remove()   # Hidden until download starts

        self.status_label = ctk.CTkLabel(
            self.progress_frame, text="Starting download...",
            font=ctk.CTkFont(size=11), text_color="#aaa", anchor="w"
        )
        self.status_label.grid(row=0, column=0, sticky="w")

        self.progress_bar = ctk.CTkProgressBar(
            self.progress_frame, orientation="horizontal",
            mode="determinate", height=14
        )
        self.progress_bar.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self.progress_bar.set(0)

        self.percent_label = ctk.CTkLabel(
            self.progress_frame, text="0%",
            font=ctk.CTkFont(size=11), text_color="#aaa"
        )
        self.percent_label.grid(row=2, column=0, sticky="e")

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew", padx=30, pady=24)
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)

        self.skip_btn = ctk.CTkButton(
            btn_frame, text="Skip (FFmpeg already installed)",
            fg_color="transparent", hover_color="#2a2a2a",
            border_width=1, border_color="#444",
            font=ctk.CTkFont(size=12),
            command=self._on_skip
        )
        self.skip_btn.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        self.download_btn = ctk.CTkButton(
            btn_frame,
            text="⬇  Download FFmpeg (Free)",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#e05c00", hover_color="#a84400",
            height=44,
            command=self._start_download
        )
        self.download_btn.grid(row=0, column=1, padx=(8, 0), sticky="ew")

        # Warning note
        ctk.CTkLabel(
            self, text="You can also skip this and install FFmpeg yourself — see README.md",
            font=ctk.CTkFont(size=10), text_color="#555"
        ).grid(row=3, column=0, pady=(0, 12))

    def _start_download(self):
        """Kick off the background download + extract thread."""
        self.download_btn.configure(state="disabled", text="Downloading...")
        self.skip_btn.configure(state="disabled")
        self.progress_frame.grid()          # Show progress section
        self.update_idletasks()

        self._download_thread = threading.Thread(
            target=self._download_and_extract, daemon=True)
        self._download_thread.start()

    def _update_progress(self, downloaded, total, status_text=None):
        """Thread-safe UI update called from the download thread via after()."""
        def _do():
            if total > 0:
                frac = min(downloaded / total, 1.0)
                self.progress_bar.set(frac)
                self.percent_label.configure(text=f"{int(frac*100)}%")
            if status_text:
                self.status_label.configure(text=status_text)
        self.after(0, _do)

    def _download_and_extract(self):
        """Run in a background thread: download zip → extract ffmpeg.exe."""
        import urllib.request
        import zipfile
        import tempfile

        zip_tmp = None
        try:
            os.makedirs(self.FFMPEG_LOCAL_DIR, exist_ok=True)
            zip_tmp = os.path.join(self.FFMPEG_LOCAL_DIR, "_ffmpeg_download.zip")

            # ---- Download ----
            self._update_progress(0, 1, "Connecting to gyan.dev...")

            def _progress_hook(block_num, block_size, total_size):
                downloaded = block_num * block_size
                mb_done = downloaded / (1024 * 1024)
                mb_total = total_size / (1024 * 1024) if total_size > 0 else 0
                self._update_progress(
                    downloaded, total_size,
                    f"Downloading FFmpeg...  {mb_done:.1f} / {mb_total:.1f} MB"
                )

            urllib.request.urlretrieve(self.FFMPEG_URL, zip_tmp, _progress_hook)

            # ---- Extract only ffmpeg.exe + ffprobe.exe ----
            self._update_progress(1, 1, "Extracting FFmpeg binaries...")
            with zipfile.ZipFile(zip_tmp, 'r') as zf:
                for member in zf.namelist():
                    # The zip has structure: ffmpeg-N.N-essentials_build/bin/ffmpeg.exe
                    filename = os.path.basename(member)
                    if filename in ("ffmpeg.exe", "ffprobe.exe", "ffplay.exe"):
                        target_path = os.path.join(self.FFMPEG_LOCAL_DIR, filename)
                        with zf.open(member) as src, open(target_path, "wb") as dst:
                            dst.write(src.read())

            # Verify the exe landed correctly
            ffmpeg_exe = os.path.join(self.FFMPEG_LOCAL_DIR, "ffmpeg.exe")
            if not os.path.exists(ffmpeg_exe):
                raise FileNotFoundError(
                    "ffmpeg.exe not found after extraction. "
                    "The zip structure may have changed — please report this."
                )

            # Inject path for this session
            _inject_ffmpeg_path(self.FFMPEG_LOCAL_DIR)

            # Remove the zip to save space
            os.remove(zip_tmp)

            self.after(0, self._on_download_success)

        except Exception as e:
            # Clean up partial zip
            if zip_tmp and os.path.exists(zip_tmp):
                try:
                    os.remove(zip_tmp)
                except Exception:
                    pass
            self.after(0, lambda err=str(e): self._on_download_error(err))

    def _on_download_success(self):
        self.progress_bar.set(1.0)
        self.percent_label.configure(text="100%")
        self.status_label.configure(
            text="✅  FFmpeg ready! Launching AtoManwa...", text_color="#2bc97a")
        self.download_btn.configure(
            text="✅  Done — Opening App", fg_color="#2b7a42", state="disabled")
        self.after(1400, self._finish)

    def _on_download_error(self, error_msg):
        self.status_label.configure(
            text=f"❌  Download failed: {error_msg}", text_color="#e05c5c")
        self.download_btn.configure(
            text="Retry Download", state="normal",
            fg_color="#e05c00", hover_color="#a84400",
            command=self._start_download
        )
        self.skip_btn.configure(state="normal")

    def _on_skip(self):
        self._finish()

    def _finish(self):
        self.grab_release()
        self.destroy()
        self.on_complete_callback()


# =============================================================================
# FFmpeg path helpers
# =============================================================================

def _ffmpeg_local_dir():
    return os.path.join(BASE_DIR, "tools", "ffmpeg")


def _inject_ffmpeg_path(ffmpeg_dir):
    """Add ffmpeg_dir to PATH for this session so moviepy/subprocess can find it."""
    current_path = os.environ.get("PATH", "")
    if ffmpeg_dir not in current_path:
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + current_path


def check_ffmpeg() -> str:
    """
    Returns:
      'system'  — ffmpeg found in system PATH (nothing to do)
      'local'   — ffmpeg found in tools/ffmpeg/ (injected into PATH)
      'missing' — not found anywhere (show setup wizard)
    """
    import shutil

    # 1. Check system PATH first
    if shutil.which("ffmpeg"):
        return "system"

    # 2. Check our local copy
    local_exe = os.path.join(_ffmpeg_local_dir(), "ffmpeg.exe")
    if os.path.exists(local_exe):
        _inject_ffmpeg_path(_ffmpeg_local_dir())
        return "local"

    return "missing"


# =============================================================================
# Entry point
# =============================================================================

if __name__ == "__main__":
    # Bootstrap a hidden root so we can show the wizard before the main window
    import tkinter as tk

    status = check_ffmpeg()

    if status == "missing":
        # Show the setup wizard; it calls _launch_main_app when done/skipped
        _root_hidden = ctk.CTk()
        _root_hidden.withdraw()   # Keep it invisible

        def _launch_main_app():
            _root_hidden.destroy()
            app = ManhwaShortsGUI()
            app.mainloop()

        wizard = FFmpegSetupWizard(_root_hidden, on_complete_callback=_launch_main_app)
        _root_hidden.mainloop()
    else:
        if status == "local":
            print(f"[FFmpeg] Using local copy from: {_ffmpeg_local_dir()}")
        # FFmpeg already available — open the main app directly
        app = ManhwaShortsGUI()
        app.mainloop()
