import argparse
import json
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from tkinter import ttk
import random
import time
import tempfile
import wave
import pygame
try:
    import numpy as np
    HAVE_NUMPY = True
except Exception:
    np = None
    HAVE_NUMPY = False
try:
    from pydub import AudioSegment
    from pydub.utils import which as pydub_which
    HAVE_PYDUB = True
except Exception:
    AudioSegment = None
    pydub_which = None
    HAVE_PYDUB = False
try:
    import imageio_ffmpeg
    HAVE_IMAGEIO_FFMPEG = True
except Exception:
    imageio_ffmpeg = None
    HAVE_IMAGEIO_FFMPEG = False

HAVE_FFMPEG = False
if HAVE_PYDUB:
    try:
        ffmpeg_path = None
        if pydub_which:
            ffmpeg_path = pydub_which("ffmpeg")
        if not ffmpeg_path and HAVE_IMAGEIO_FFMPEG:
            ffmpeg_path = imageio_ffmpeg.get_exe()
        if ffmpeg_path:
            AudioSegment.converter = ffmpeg_path
            HAVE_FFMPEG = True
    except Exception:
        HAVE_FFMPEG = False

SAVE_FILE = Path("save.json")
SUPPORTED_EXTENSIONS = {"mp3", "wav", "ogg", "flac"}

# ---------------------------------------------------------------------------
# Parse optional CLI arguments (forwarded from main.py)
# ---------------------------------------------------------------------------
_parser = argparse.ArgumentParser(add_help=False)
_parser.add_argument("-d", "--directory", type=Path, help="Music folder")
_parser.add_argument("-q", "--queue", type=Path, help="Queue file")
_parser.add_argument("-m", "--music", type=Path, help="Path to a music file to play")
_cli_args, _ = _parser.parse_known_args()

# Validate --music path early
if _cli_args.music and not _cli_args.music.is_file():
    print(f'Error: The Music File in the "{_cli_args.music}" is missing')
    sys.exit(1)

DEFAULT_STATE = {
    "current-folder": None,
    "current-file": None,
    "settings": {
        "volume": 100,
        "shuffle": False,
        "loop": "off",
    },
    "queue-file": None,
}




def load_state():
    if SAVE_FILE.exists():
        try:
            with SAVE_FILE.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                return {**DEFAULT_STATE, **data}
        except (json.JSONDecodeError, OSError):
            pass
    return DEFAULT_STATE.copy()


def save_state(state):
    try:
        with SAVE_FILE.open("w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=4)
    except OSError:
        messagebox.showwarning("Save failed", "Unable to write save.json")


def is_audio_file(path):
    return path.suffix.lower().lstrip(".") in SUPPORTED_EXTENSIONS


def scan_folder(folder):
    if not folder or not os.path.isdir(folder):
        return []
    results = []
    for entry in sorted(os.listdir(folder), key=str.lower):
        path = Path(folder) / entry
        if path.is_file() and is_audio_file(path):
            results.append(path)
    return results


def main():
    pygame.mixer.init()
    state = load_state()

    # Apply CLI overrides
    if _cli_args.directory and _cli_args.directory.is_dir():
        state["current-folder"] = str(_cli_args.directory)
    if _cli_args.music:
        # Use the music file's parent folder and select that file
        state["current-folder"] = str(_cli_args.music.parent)
        state["current-file"] = str(_cli_args.music)

    playlist = []
    current_index = 0
    music_loaded = False
    is_playing = False
    is_paused = False
    is_random = state["settings"].get("shuffle", False)
    # Restore loop mode from saved settings
    _loop_str = state["settings"].get("loop", "off")
    loop_mode = {"off": 0, "all": 1, "one": 2}.get(_loop_str, 0)
    current_length = 0.0

    root = tk.Tk()
    root.title("Music Explorer")
    root.geometry("700x500")
    root.resizable(False, False)

    # Create notebook (tabbed interface)
    notebook = ttk.Notebook(root)
    notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # ==================== PLAYER TAB ====================
    player_frame = ttk.Frame(notebook, padding=10)
    notebook.add(player_frame, text="Player")

    # Folder selection
    folder_frame = ttk.Frame(player_frame)
    folder_frame.pack(fill=tk.X, pady=(0, 10))

    folder_button = ttk.Button(folder_frame, text="Choose Folder")
    folder_button.pack(side=tk.LEFT)

    current_folder_label = ttk.Label(folder_frame, text="No folder selected", foreground="gray")
    current_folder_label.pack(side=tk.LEFT, padx=(10, 0))

    # Playlist
    list_frame = ttk.Frame(player_frame)
    list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    playlist_box = tk.Listbox(list_frame, height=12, activestyle="none")
    playlist_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    # Ensure selection is visible across themes
    try:
        playlist_box.config(selectbackground="#4da6ff", selectforeground="#000000")
    except Exception:
        pass

    scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=playlist_box.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    playlist_box.config(yscrollcommand=scrollbar.set)

    # Progress bar
    progress_frame = ttk.Frame(player_frame)
    progress_frame.pack(fill=tk.X, pady=(0, 5))
    
    time_label = ttk.Label(progress_frame, text="0:00 / 0:00", width=20)
    time_label.pack(side=tk.LEFT, padx=(0, 5))
    
    progress_bar = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL, mode="determinate", length=300)
    progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)

    # Playback controls
    controls_frame = ttk.Frame(player_frame)
    controls_frame.pack(fill=tk.X, pady=(0, 10))

    play_button = ttk.Button(controls_frame, text="Play", width=10)
    pause_button = ttk.Button(controls_frame, text="Pause/Resume", width=10)
    stop_button = ttk.Button(controls_frame, text="Stop", width=10)
    prev_button = ttk.Button(controls_frame, text="⏮ Prev", width=10)
    next_button = ttk.Button(controls_frame, text="Next ⏭", width=10)

    play_button.pack(side=tk.LEFT, padx=2)
    pause_button.pack(side=tk.LEFT, padx=2)
    stop_button.pack(side=tk.LEFT, padx=2)
    prev_button.pack(side=tk.LEFT, padx=2)
    next_button.pack(side=tk.LEFT, padx=2)

    # Status
    status_label = ttk.Label(player_frame, text="Ready", relief=tk.SUNKEN)
    status_label.pack(fill=tk.X)

    # ==================== SETTINGS TAB ====================
    settings_frame = ttk.Frame(notebook, padding=20)
    notebook.add(settings_frame, text="Settings")

    # Volume
    volume_label = ttk.Label(settings_frame, text=f"Volume: {state['settings']['volume']}%")
    volume_label.pack(anchor=tk.W, pady=(0, 5))

    volume_slider = ttk.Scale(
        settings_frame,
        from_=0,
        to=100,
        orient=tk.HORIZONTAL,
        length=300,
    )
    volume_slider.set(state["settings"]["volume"])
    volume_slider.pack(anchor=tk.W, fill=tk.X, pady=(0, 20))



    # Loop mode
    loop_label = ttk.Label(settings_frame, text="Loop: Off")
    loop_label.pack(anchor=tk.W, pady=(0, 5))
    loop_button = ttk.Button(settings_frame, text="Toggle Loop Mode", width=20)
    loop_button.pack(anchor=tk.W, pady=(0, 20))

    # Random
    random_label = ttk.Label(settings_frame, text="Shuffle: Off")
    random_label.pack(anchor=tk.W, pady=(0, 5))
    random_button = ttk.Button(settings_frame, text="Shuffle Playlist", width=20)
    random_button.pack(anchor=tk.W, pady=(0, 20))

    # Info
    info_text = ttk.Label(
        settings_frame,
        text="Supported formats: MP3, WAV, OGG, FLAC\n\nUse the Player tab to browse and play music.",
        justify=tk.LEFT,
    )
    info_text.pack(anchor=tk.NW)

    # ==================== CALLBACK FUNCTIONS ====================

    def update_playlist(folder):
        nonlocal playlist, current_index
        all_files = scan_folder(folder)
        queue_file = Path(folder) / "queue.json"
        loaded_playlist = []
        if queue_file.exists():
            try:
                with queue_file.open("r", encoding="utf-8") as f:
                    saved_names = json.load(f)
                if isinstance(saved_names, list):
                    files_by_name = {p.name: p for p in all_files}
                    seen = set()
                    for filename in saved_names:
                        if filename in files_by_name and filename not in seen:
                            loaded_playlist.append(files_by_name[filename])
                            seen.add(filename)
                    # Add any newly added files that weren't in the saved queue
                    for p in all_files:
                        if p.name not in seen:
                            loaded_playlist.append(p)
            except Exception:
                pass

        if loaded_playlist:
            playlist = loaded_playlist
        else:
            playlist = all_files

        playlist_box.delete(0, tk.END)
        for path in playlist:
            playlist_box.insert(tk.END, path.name)
        if playlist:
            if state["current-file"]:
                for idx, path in enumerate(playlist):
                    if str(path) == state["current-file"]:
                        current_index = idx
                        playlist_box.select_set(idx)
                        playlist_box.see(idx)
                        break
                else:
                    current_index = 0
                    state["current-file"] = str(playlist[0])
                    playlist_box.select_set(0)
            else:
                current_index = 0
                state["current-file"] = str(playlist[0])
                playlist_box.select_set(0)
        else:
            current_index = 0
            state["current-file"] = None

    def save_queue_json(folder):
        """Save playlist order to queue.json in the folder."""
        queue_file = Path(folder) / "queue.json"
        queue_data = [p.name for p in playlist]
        try:
            with queue_file.open("w", encoding="utf-8") as f:
                json.dump(queue_data, f, indent=4)
        except OSError:
            pass  # Silently fail if can't write

    def set_folder():
        nonlocal is_playing
        folder = filedialog.askdirectory(title="Select music folder")
        if folder:
            state["current-folder"] = folder
            is_playing = False
            pygame.mixer.music.stop()
            update_playlist(folder)
            save_queue_json(folder)
            save_state(state)
            current_folder_label.config(text=folder)
            status_label.config(text=f"Folder: {Path(folder).name}")

    def load_track(index):
        nonlocal current_index, music_loaded, current_length
        if not playlist:
            return
        index = max(0, min(index, len(playlist) - 1))
        current_index = index
        track_path = playlist[current_index]
        try:
            pygame.mixer.music.load(track_path)
            music_loaded = True
            try:
                snd = pygame.mixer.Sound(str(track_path))
                current_length = snd.get_length()
            except Exception:
                current_length = 0.0
            state["current-file"] = str(track_path)
            playlist_box.select_clear(0, tk.END)
            playlist_box.select_set(current_index)
            playlist_box.see(current_index)
            status_label.config(text=f"Loaded: {track_path.name}")
            save_state(state)
        except pygame.error as error:
            music_loaded = False
            messagebox.showerror("Playback error", f"Could not load {track_path.name}: {error}")

    def play_music():
        nonlocal is_playing, is_paused, current_length, music_loaded
        if not playlist:
            messagebox.showinfo("No track", "Choose a music folder with tracks first.")
            return
        if not state["current-file"] or not Path(state["current-file"]).exists() or not music_loaded:
            load_track(current_index)
        track_path = Path(state["current-file"]) if state.get("current-file") else playlist[current_index]
        try:
            pygame.mixer.music.load(str(track_path))
            pygame.mixer.music.play()
            is_playing = True
            is_paused = False
            status_label.config(text=f"Playing: {track_path.name}")
        except pygame.error as error:
            messagebox.showerror("Playback error", f"Could not play track: {error}")

    def pause_music():
        nonlocal is_playing, is_paused
        try:
            if pygame.mixer.music.get_busy() and not is_paused:
                pygame.mixer.music.pause()
                is_paused = True
                is_playing = False
                status_label.config(text="Paused")
            elif is_paused:
                pygame.mixer.music.unpause()
                is_paused = False
                is_playing = True
                if state["current-file"]:
                    status_label.config(text=f"Playing: {Path(state['current-file']).name}")
            else:
                status_label.config(text="No track loaded")
        except pygame.error:
            status_label.config(text="Error with pause")

    def stop_music():
        nonlocal is_playing, is_paused
        pygame.mixer.music.stop()
        is_playing = False
        is_paused = False
        status_label.config(text="Stopped")

    def next_track():
        if playlist:
            load_track((current_index + 1) % len(playlist))
            play_music()

    def previous_track():
        if playlist:
            load_track((current_index - 1) % len(playlist))
            play_music()

    def toggle_random():
        """Toggle random/shuffle mode."""
        nonlocal is_random, current_index
        if not playlist:
            messagebox.showinfo("No tracks", "Choose a music folder first.")
            return
        is_random = not is_random
        state["settings"]["shuffle"] = is_random
        save_state(state)
        if is_random:
            random.shuffle(playlist)
            current_index = 0
            playlist_box.delete(0, tk.END)
            for path in playlist:
                playlist_box.insert(tk.END, path.name)
            playlist_box.select_set(0)
            load_track(0)
            random_label.config(text="Shuffle: On")
            status_label.config(text="Shuffle enabled")
        else:
            # Restore original order from queue.json
            update_playlist(state["current-folder"])
            current_index = 0
            playlist_box.select_set(0)
            load_track(0)
            random_label.config(text="Shuffle: Off")
            status_label.config(text="Shuffle disabled")

    def toggle_loop():
        """Toggle loop mode: Off -> Loop All -> Loop One -> Off."""
        nonlocal loop_mode
        loop_mode = (loop_mode + 1) % 3
        modes = ["Off", "All", "One"]
        mode_keys = ["off", "all", "one"]
        state["settings"]["loop"] = mode_keys[loop_mode]
        save_state(state)
        loop_label.config(text=f"Loop: {modes[loop_mode]}")
        status_label.config(text=f"Loop mode: {modes[loop_mode]}")



    def update_progress():
        """Update progress bar and time display for music playback."""
        try:
            if is_playing:
                pos = pygame.mixer.music.get_pos() / 1000
                length = current_length
                if length:
                    progress = (pos / length) * 100
                    progress_bar['value'] = min(progress, 100)
                    mins, secs = int(pos // 60), int(pos % 60)
                    total_mins, total_secs = int(length // 60), int(length % 60)
                    time_label.config(text=f"{mins}:{secs:02d} / {total_mins}:{total_secs:02d}")
        except Exception:
            pass
        root.after(100, update_progress)

    def check_track_finished():
        """Check if current track finished and auto-play next, respecting loop and random modes."""
        nonlocal is_playing
        finished = False
        if is_playing and not pygame.mixer.music.get_busy() and not is_paused:
            finished = True

        if finished:
            if loop_mode == 2:  # Loop one
                play_music()
            elif playlist:
                if loop_mode == 0 and current_index >= len(playlist) - 1:
                    is_playing = False
                    status_label.config(text="Finished")
                else:
                    load_track((current_index + 1) % len(playlist))
                    play_music()
        root.after(500, check_track_finished)

    def on_track_select(event=None):
        selection = playlist_box.curselection()
        if selection:
            load_track(selection[0])

    def change_volume(value):
        volume = int(float(value))
        pygame.mixer.music.set_volume(volume / 100)
        state["settings"]["volume"] = volume
        save_state(state)
        volume_label.config(text=f"Volume: {volume}%")

    def on_exit():
        save_state(state)
        pygame.mixer.music.stop()
        pygame.quit()
        root.destroy()

    # ==================== BIND EVENTS ====================
    folder_button.config(command=set_folder)
    play_button.config(command=play_music)
    pause_button.config(command=pause_music)
    stop_button.config(command=stop_music)
    prev_button.config(command=previous_track)
    next_button.config(command=next_track)
    random_button.config(command=toggle_random)
    loop_button.config(command=toggle_loop)
    playlist_box.bind("<<ListboxSelect>>", on_track_select)
    volume_slider.config(command=change_volume)

    # ==================== INITIALIZATION ====================
    # Restore shuffle / loop UI from saved state
    if is_random:
        random_label.config(text="Shuffle: On")
    modes_display = ["Off", "All", "One"]
    loop_label.config(text=f"Loop: {modes_display[loop_mode]}")

    if state["current-folder"]:
        if os.path.isdir(state["current-folder"]):
            current_folder_label.config(text=state["current-folder"])
            update_playlist(state["current-folder"])
            status_label.config(text=f"Ready: {Path(state['current-folder']).name}")
        else:
            messagebox.showwarning(
                "Folder not found",
                f"The previously saved music folder no longer exists:\n{state['current-folder']}\n\nIt may have been moved or deleted."
            )
            state["current-folder"] = None
            state["current-file"] = None
            save_state(state)

    if state["current-file"] and Path(state["current-file"]).exists():
        current_file = Path(state["current-file"])
        status_label.config(text=f"Ready: {current_file.name}")

    pygame.mixer.music.set_volume(state["settings"]["volume"] / 100)
    root.protocol("WM_DELETE_WINDOW", on_exit)
    # Start auto-next checker and progress updater
    check_track_finished()
    update_progress()
    root.mainloop()


if __name__ == "__main__":
    main()
