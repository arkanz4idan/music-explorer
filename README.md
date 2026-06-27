# 🎵 Music Explorer

Welcome to **Music Explorer**! This is a simple, lightweight, and clean desktop audio player built using Python and Tkinter. It scans your chosen folder for music files, allows you to manage playlists, and offers features like volume control, shuffling, and looping.

---

## ✨ Features

- **📂 Easy Folder Navigation**: Choose any folder containing audio files, and Music Explorer will scan and import them automatically.
- **🎧 Broad Audio Format Support**: Supports playback for `.mp3`, `.wav`, `.ogg`, and `.flac` files.
- **🎛️ Standard Playback Controls**: Easily Play, Pause/Resume, Stop, or skip to the Next/Previous tracks.
- **🔄 Loop Modes**: Cycle through different loop configurations:
  - **Off**: Play list through once.
  - **All**: Repeat the entire playlist.
  - **One**: Repeat the currently playing track.
- **🔀 Shuffle & Queue**: Toggle shuffle mode to randomize playlist order, which also updates and saves the queue automatically.
- **📝 Queue Serialization**: Every time a folder is loaded or shuffled, the playback order is saved to `queue.json` in that directory, allowing other programs or future sessions to know the current sequence.
- **💾 Settings Persistence**: Automatically remembers your settings (volume, last selected folder, last played file) across launches via a local state file (`save.json`).

---

## 🚀 Getting Started

### Prerequisites

You need **Python 3.8+** installed. Then, install the required dependencies (primarily `pygame` for audio playback and UI window configuration):

```bash
pip install -r requirements.txt
```

### Running the App

To start Music Explorer, execute the main script:

```bash
python main.py
```

or just use uv:

```bash
uv run main.py
```

---

## 🛠️ Project Structure

- `main.py`: The Main Script
- `gui.py`: The entry point containing the Tkinter user interface and audio playback logic.
- `cli.py`: The entry point containing the Textual user interface and audio playback logic.
- `[selected_music_folder]/queue.json`: Automatically created inside the selected music folder to persist the current tracks queue order.
- `save.json`: Automatically created file storing your volume settings and last active folders.
- `pyproject.toml`: Python package dependencies.
