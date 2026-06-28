import pathlib
import sys
from pathlib import Path
import json
import random
import argparse

import pygame

from textual.app import App, ComposeResult
from textual.widgets import (
    Header, Footer, ListView, ListItem, Button, Static,
    TabbedContent, TabPane, ProgressBar,
)
from textual.containers import Horizontal, Vertical
from textual.timer import Timer

# ---------------------------------------------------------------------------
# Parse optional CLI arguments
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("-d", "--directory", type=Path, help="Music folder to load")
parser.add_argument("-q", "--queue", type=Path, help="Path to queue.json")
parser.add_argument("-m", "--music", type=Path, help="Path to a music file to play")
cli_args, _ = parser.parse_known_args()

# Validate --music path early
if cli_args.music and not cli_args.music.is_file():
    print(f'Error: The Music File in the "{cli_args.music}" is missing')
    sys.exit(1)

initial_folder = str(cli_args.directory) if cli_args.directory and cli_args.directory.is_dir() else None
initial_music_file = cli_args.music if cli_args.music else None

# ---------------------------------------------------------------------------
# Persistence helpers (shared format with gui.py)
# ---------------------------------------------------------------------------
SAVE_FILE = pathlib.Path("save.json")
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
            with SAVE_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return {**DEFAULT_STATE, **data}
        except Exception:
            pass
    return DEFAULT_STATE.copy()


def save_state(state):
    try:
        with SAVE_FILE.open("w", encoding="utf-8") as f:
            json.dump(state, f, indent=4)
    except OSError:
        pass


SUPPORTED = {".mp3", ".wav", ".ogg", ".flac"}


def scan_folder(folder_path):
    if not folder_path or not pathlib.Path(folder_path).is_dir():
        return []
    files = [
        p for p in pathlib.Path(folder_path).iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED
    ]
    return sorted(files, key=lambda p: p.name.lower())


def load_playlist_from_queue(folder_path):
    """Load playlist order from queue.json if it exists, like gui.py does."""
    all_files = scan_folder(folder_path)
    queue_file = Path(folder_path) / "queue.json"
    if queue_file.exists():
        try:
            with queue_file.open("r", encoding="utf-8") as f:
                saved_names = json.load(f)
            if isinstance(saved_names, list):
                files_by_name = {p.name: p for p in all_files}
                ordered = []
                seen = set()
                for name in saved_names:
                    if name in files_by_name and name not in seen:
                        ordered.append(files_by_name[name])
                        seen.add(name)
                for p in all_files:
                    if p.name not in seen:
                        ordered.append(p)
                return ordered
        except Exception:
            pass
    return all_files


# ===========================================================================
# Textual App
# ===========================================================================
class MusicCLI(App):
    CSS_PATH = "cli.tcss"
    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def __init__(self):
        super().__init__()
        self.state = load_state()
        if initial_music_file:
            # --music overrides: use file's parent as folder, select the file
            self.state["current-folder"] = str(initial_music_file.parent)
            self.state["current-file"] = str(initial_music_file)
        elif initial_folder:
            self.state["current-folder"] = initial_folder

        self.playlist: list[Path] = []
        self.current_index = 0
        self.is_playing = False
        self.is_paused = False
        self.is_shuffling = self.state["settings"].get("shuffle", False)
        # Restore loop mode from saved settings
        _loop_str = self.state["settings"].get("loop", "off")
        self.loop_mode = {"off": 0, "all": 1, "one": 2}.get(_loop_str, 0)
        self.current_length = 0.0
        self.music_loaded = False

        pygame.mixer.init()
        pygame.mixer.music.set_volume(self.state["settings"]["volume"] / 100)

    # ── Layout ────────────────────────────────────────────────────────────
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent():
            # ==================== PLAYER TAB ====================
            with TabPane("Player", id="player_tab"):
                # Folder row
                with Horizontal(id="folder_row"):
                    yield Button("Choose Folder", id="choose_folder")
                    yield Static("No folder selected", id="folder_label")

                # Track list
                yield ListView(id="track_list")

                # Progress bar row
                with Horizontal(id="progress_row"):
                    yield Static("0:00 / 0:00", id="time_label")
                    yield ProgressBar(total=100, show_eta=False, show_percentage=False, id="progress_bar")

                # Playback controls
                with Horizontal(id="controls_row"):
                    yield Button("Play", id="play")
                    yield Button("Pause/Resume", id="pause")
                    yield Button("Stop", id="stop")
                    yield Button("⏮ Prev", id="prev")
                    yield Button("Next ⏭", id="next")

                # Status
                yield Static("Ready", id="status")

            # ==================== SETTINGS TAB ====================
            with TabPane("Settings", id="settings_tab"):
                # Volume
                yield Static(f"Volume: {self.state['settings']['volume']}%", id="volume_label")
                with Horizontal(id="volume_row"):
                    yield Button("−", id="vol_down")
                    yield ProgressBar(total=100, show_eta=False, show_percentage=False, id="volume_bar")
                    yield Button("+", id="vol_up")

                # Loop
                yield Static("Loop: Off", id="loop_label")
                yield Button("Toggle Loop Mode", id="loop")

                # Shuffle
                yield Static("Shuffle: Off", id="shuffle_label")
                yield Button("Shuffle Playlist", id="shuffle")

                # Info
                yield Static(
                    "Supported formats: MP3, WAV, OGG, FLAC\n\n"
                    "Use the Player tab to browse and play music.",
                    id="info_text",
                )
        yield Footer()

    # ── Mount / timers ────────────────────────────────────────────────────
    async def on_mount(self) -> None:
        # Load saved folder
        folder = self.state.get("current-folder")
        if folder and pathlib.Path(folder).is_dir():
            self.query_one("#folder_label", Static).update(folder)
            await self.refresh_playlist()
            self.query_one("#status", Static).update(f"Ready: {Path(folder).name}")
        # Restore saved file selection
        if self.state.get("current-file") and Path(self.state["current-file"]).exists():
            self.query_one("#status", Static).update(
                f"Ready: {Path(self.state['current-file']).name}"
            )
        # Set initial volume bar
        vol = self.state["settings"]["volume"]
        self.query_one("#volume_bar", ProgressBar).update(progress=vol)

        # Restore shuffle / loop UI from saved state
        if self.is_shuffling:
            self.query_one("#shuffle_label", Static).update("Shuffle: On")
        modes_display = ["Off", "All", "One"]
        self.query_one("#loop_label", Static).update(f"Loop: {modes_display[self.loop_mode]}")

        # Periodic timers (like gui.py's root.after)
        self.set_interval(0.25, self.update_progress)
        self.set_interval(0.5, self.check_track_finished)

    # ── Playlist ──────────────────────────────────────────────────────────
    async def refresh_playlist(self):
        folder = self.state.get("current-folder")
        if not folder:
            return
        self.playlist = load_playlist_from_queue(folder)
        lv = self.query_one("#track_list", ListView)
        lv.clear()
        for p in self.playlist:
            lv.append(ListItem(Static(p.name)))
        if self.playlist:
            # Try to restore last-selected file
            target = self.state.get("current-file")
            self.current_index = 0
            if target:
                for idx, p in enumerate(self.playlist):
                    if str(p) == target:
                        self.current_index = idx
                        break
            lv.index = self.current_index
            self.state["current-file"] = str(self.playlist[self.current_index])
            save_state(self.state)

    # ── Track loading / playback ──────────────────────────────────────────
    def load_track(self, index: int):
        if not self.playlist:
            return
        index = max(0, min(index, len(self.playlist) - 1))
        self.current_index = index
        track = self.playlist[index]
        try:
            pygame.mixer.music.load(str(track))
            self.music_loaded = True
            try:
                snd = pygame.mixer.Sound(str(track))
                self.current_length = snd.get_length()
            except Exception:
                self.current_length = 0.0
            self.state["current-file"] = str(track)
            lv = self.query_one("#track_list", ListView)
            lv.index = index
            self.query_one("#status", Static).update(f"Loaded: {track.name}")
            save_state(self.state)
        except pygame.error as e:
            self.music_loaded = False
            self.query_one("#status", Static).update(f"Error: {e}")

    def play_music(self):
        if not self.playlist:
            self.query_one("#status", Static).update("No tracks – choose a folder first.")
            return
        if not self.music_loaded:
            self.load_track(self.current_index)
        track = self.playlist[self.current_index]
        try:
            pygame.mixer.music.load(str(track))
            pygame.mixer.music.play()
            self.is_playing = True
            self.is_paused = False
            self.query_one("#status", Static).update(f"Playing: {track.name}")
        except pygame.error as e:
            self.query_one("#status", Static).update(f"Error: {e}")

    def pause_music(self):
        try:
            if pygame.mixer.music.get_busy() and not self.is_paused:
                pygame.mixer.music.pause()
                self.is_paused = True
                self.is_playing = False
                self.query_one("#status", Static).update("Paused")
            elif self.is_paused:
                pygame.mixer.music.unpause()
                self.is_paused = False
                self.is_playing = True
                if self.state.get("current-file"):
                    self.query_one("#status", Static).update(
                        f"Playing: {Path(self.state['current-file']).name}"
                    )
            else:
                self.query_one("#status", Static).update("No track loaded")
        except pygame.error:
            self.query_one("#status", Static).update("Error with pause")

    def stop_music(self):
        pygame.mixer.music.stop()
        self.is_playing = False
        self.is_paused = False
        self.query_one("#status", Static).update("Stopped")

    def next_track(self):
        if self.playlist:
            self.load_track((self.current_index + 1) % len(self.playlist))
            self.play_music()

    def prev_track(self):
        if self.playlist:
            self.load_track((self.current_index - 1) % len(self.playlist))
            self.play_music()

    # ── Settings actions ──────────────────────────────────────────────────
    def toggle_shuffle(self):
        if not self.playlist:
            return
        self.is_shuffling = not self.is_shuffling
        self.state["settings"]["shuffle"] = self.is_shuffling
        save_state(self.state)
        if self.is_shuffling:
            random.shuffle(self.playlist)
            self.current_index = 0
            lv = self.query_one("#track_list", ListView)
            lv.clear()
            for p in self.playlist:
                lv.append(ListItem(Static(p.name)))
            lv.index = 0
            self.load_track(0)
            self.query_one("#shuffle_label", Static).update("Shuffle: On")
            self.query_one("#status", Static).update("Shuffle enabled")
        else:
            folder = self.state.get("current-folder")
            if folder:
                self.playlist = load_playlist_from_queue(folder)
                lv = self.query_one("#track_list", ListView)
                lv.clear()
                for p in self.playlist:
                    lv.append(ListItem(Static(p.name)))
                self.current_index = 0
                lv.index = 0
                self.load_track(0)
            self.query_one("#shuffle_label", Static).update("Shuffle: Off")
            self.query_one("#status", Static).update("Shuffle disabled")

    def toggle_loop(self):
        self.loop_mode = (self.loop_mode + 1) % 3
        modes = ["Off", "All", "One"]
        mode_keys = ["off", "all", "one"]
        self.state["settings"]["loop"] = mode_keys[self.loop_mode]
        save_state(self.state)
        self.query_one("#loop_label", Static).update(f"Loop: {modes[self.loop_mode]}")
        self.query_one("#status", Static).update(f"Loop mode: {modes[self.loop_mode]}")

    def change_volume(self, delta: int):
        vol = self.state["settings"]["volume"]
        vol = max(0, min(100, vol + delta))
        pygame.mixer.music.set_volume(vol / 100)
        self.state["settings"]["volume"] = vol
        save_state(self.state)
        self.query_one("#volume_label", Static).update(f"Volume: {vol}%")
        self.query_one("#volume_bar", ProgressBar).update(progress=vol)

    # ── Progress / auto-next (mirrors gui.py timers) ──────────────────────
    def update_progress(self) -> None:
        try:
            if self.is_playing and self.current_length:
                pos = pygame.mixer.music.get_pos() / 1000
                progress = (pos / self.current_length) * 100
                self.query_one("#progress_bar", ProgressBar).update(progress=min(progress, 100))
                mins, secs = int(pos // 60), int(pos % 60)
                t_mins, t_secs = int(self.current_length // 60), int(self.current_length % 60)
                self.query_one("#time_label", Static).update(
                    f"{mins}:{secs:02d} / {t_mins}:{t_secs:02d}"
                )
        except Exception:
            pass

    def check_track_finished(self) -> None:
        if self.is_playing and not pygame.mixer.music.get_busy() and not self.is_paused:
            # Track ended
            if self.loop_mode == 2:        # loop one
                self.play_music()
            elif self.playlist:
                if self.loop_mode == 0 and self.current_index >= len(self.playlist) - 1:
                    self.is_playing = False
                    self.query_one("#status", Static).update("Finished")
                else:
                    self.load_track((self.current_index + 1) % len(self.playlist))
                    self.play_music()

    # ── Event handlers ────────────────────────────────────────────────────
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "choose_folder":
            # In the terminal we can't use a GUI file dialog, so we
            # prompt the user for a path via the Textual Input widget.
            self.push_screen(FolderInputScreen(), callback=self.on_folder_chosen)
        elif bid == "play":
            self.play_music()
        elif bid == "pause":
            self.pause_music()
        elif bid == "stop":
            self.stop_music()
        elif bid == "prev":
            self.prev_track()
        elif bid == "next":
            self.next_track()
        elif bid == "loop":
            self.toggle_loop()
        elif bid == "shuffle":
            self.toggle_shuffle()
        elif bid == "vol_up":
            self.change_volume(5)
        elif bid == "vol_down":
            self.change_volume(-5)

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = self.query_one("#track_list", ListView).index
        if idx is not None:
            self.load_track(idx)

    async def on_folder_chosen(self, folder: str | None) -> None:
        if folder and pathlib.Path(folder).is_dir():
            self.state["current-folder"] = folder
            self.is_playing = False
            pygame.mixer.music.stop()
            save_state(self.state)
            self.query_one("#folder_label", Static).update(folder)
            await self.refresh_playlist()
            self.query_one("#status", Static).update(f"Folder: {Path(folder).name}")
        elif folder:
            self.query_one("#status", Static).update(f"Invalid folder: {folder}")

    async def action_quit(self) -> None:
        save_state(self.state)
        pygame.mixer.music.stop()
        self.exit()


# ---------------------------------------------------------------------------
# Small modal screen for folder path input (replaces tkinter filedialog)
# ---------------------------------------------------------------------------
from textual.screen import ModalScreen
from textual.widgets import Input


class FolderInputScreen(ModalScreen[str | None]):
    """Tiny modal that asks the user to type a folder path."""

    def compose(self) -> ComposeResult:
        with Vertical(id="folder_dialog"):
            yield Static("Enter music folder path:", id="dialog_title")
            yield Input(placeholder="/path/to/music", id="folder_input")
            with Horizontal(id="dialog_buttons"):
                yield Button("OK", variant="primary", id="dialog_ok")
                yield Button("Cancel", id="dialog_cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "dialog_ok":
            value = self.query_one("#folder_input", Input).value.strip()
            self.dismiss(value or None)
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        self.dismiss(value or None)


if __name__ == "__main__":
    MusicCLI().run()