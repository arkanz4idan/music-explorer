import argparse
import subprocess
import sys
from pathlib import Path


def launch_gui(folder: Path | None = None, queue: Path | None = None) -> None:
    """Launch the Tkinter GUI.
    Optional ``folder`` and ``queue`` arguments are passed through the command line
    to ``gui.py`` if supplied.
    """
    cmd = [sys.executable, "gui.py"]
    if folder:
        cmd.extend(["-d", str(folder)])
    if queue:
        cmd.extend(["-q", str(queue)])
    subprocess.run(cmd, check=False)


def launch_cli(folder: Path | None = None, queue: Path | None = None) -> None:
    """Launch the Textual TUI CLI.
    Optional ``folder`` and ``queue`` arguments are passed to ``cli.py``.
    """
    cmd = [sys.executable, "cli.py"]
    if folder:
        cmd.extend(["-d", str(folder)])
    if queue:
        cmd.extend(["-q", str(queue)])
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
    parser.add_argument("-d", "--directory", type=Path, help="Music folder to load (optional)")
    parser.add_argument("-q", "--queue", type=Path, help="Path to queue.json (optional)")
    args = parser.parse_args()

    # Validate optional paths – ignore if they don't exist
    folder = args.directory if args.directory and args.directory.is_dir() else None
    queue = args.queue if args.queue and args.queue.is_file() else None

    if args.type == "gui":
        launch_gui(folder, queue)
    elif args.type == "cli":
        launch_cli(folder, queue)
    else:
        interactive_menu()


if __name__ == "__main__":
    main()