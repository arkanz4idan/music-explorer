import argparse
import subprocess
import sys
from pathlib import Path


def launch_gui(folder: Path | None = None, queue: Path | None = None, music: Path | None = None) -> None:
    """Launch the Tkinter GUI.
    Optional ``folder``, ``queue``, and ``music`` arguments are passed through
    the command line to ``gui.py`` if supplied.
    """
    cmd = [sys.executable, "gui.py"]
    if folder:
        cmd.extend(["-d", str(folder)])
    if queue:
        cmd.extend(["-q", str(queue)])
    if music:
        cmd.extend(["-m", str(music)])
    subprocess.run(cmd, check=False)


def launch_cli(folder: Path | None = None, queue: Path | None = None, music: Path | None = None) -> None:
    """Launch the Textual TUI CLI.
    Optional ``folder``, ``queue``, and ``music`` arguments are passed to ``cli.py``.
    """
    cmd = [sys.executable, "cli.py"]
    if folder:
        cmd.extend(["-d", str(folder)])
    if queue:
        cmd.extend(["-q", str(queue)])
    if music:
        cmd.extend(["-m", str(music)])
    subprocess.run(cmd, check=False)


def interactive_menu() -> None:
    """Simple text menu used when no ``--type`` argument is provided."""
    while True:
        print("\nMUSIC EXPLORER")
        print("1. GUI Player")
        print("2. Terminal Player (TUI)")
        print("0. Exit")
        choice = input("Choose option: ").strip()
        if choice == "1":
            launch_gui()
        elif choice == "2":
            launch_cli()
        elif choice == "0":
            break
        else:
            print("Invalid input, please try again.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Music Explorer")
    parser.add_argument("-t", "--type", choices=["gui", "cli"], help="Run GUI or CLI directly")
    parser.add_argument("-m", "--music", type=Path, help="Path to a music file to play")
    parser.add_argument("-d", "--directory", type=Path, help="Music folder to load (optional)")
    parser.add_argument("-q", "--queue", type=Path, help="Path to queue.json (optional)")
    args = parser.parse_args()

    # Validate optional paths
    folder = args.directory if args.directory and args.directory.is_dir() else None
    queue = args.queue if args.queue and args.queue.is_file() else None
    music = None
    if args.music:
        if not args.music.is_file():
            print(f'Error: The Music File in the "{args.music}" is missing')
            sys.exit(1)
        music = args.music

    if args.type == "gui":
        launch_gui(folder, queue, music)
    elif args.type == "cli":
        launch_cli(folder, queue, music)
    else:
        interactive_menu()


if __name__ == "__main__":
    main()