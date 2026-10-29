"""Core logic for File Organizer.

No UI code lives here, so everything can be tested on temporary folders.
"""

import json
import stat
from dataclasses import dataclass
from pathlib import Path


def load_rules(path: Path) -> dict[str, list[str]]:
    """Read rules.json and return {category: [extensions]}."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def categorize(filename: str, rules: dict[str, list[str]]) -> str | None:
    """Return the category for this file, or None if no rule matches.

    Examples:
        categorize("photo.jpg", rules)  -> "Images"
        categorize("PHOTO.JPG", rules)  -> "Images"   (case doesn't matter)
        categorize("notes", rules)      -> None       (no extension)
        categorize("mystery.xyz", rules) -> None      (no rule)

    Hints:
        - Path(filename).suffix gives you the extension, e.g. ".jpg"
        - .lower() makes it case-insensitive
        - loop over rules.items() to get (category, extensions)
    """
    extension = Path(filename).suffix.lower()

    for category, extensions in rules.items():
        if extension in extensions:
            return category

    return None


# ---------------------------------------------------------------------------
# Planning: work out what WOULD move, without touching anything
# ---------------------------------------------------------------------------


# If a folder contains any of these, it's a code project or app folder.
# Moving files inside it could break it, so we leave it alone.
PROJECT_MARKERS = {
    ".git", "package.json", "requirements.txt", "pyproject.toml",
    ".venv", "venv", "node_modules", "setup.py", "Cargo.toml", "pom.xml",
}

# Files that must stay where they are, even if they match a rule.
SKIP_NAMES = {"desktop.ini", "thumbs.db"}
SKIP_EXTENSIONS = {".lnk", ".url"}  # shortcuts belong where the user put them


@dataclass
class Move:
    """One planned move: source file -> destination path."""
    source: Path
    destination: Path


def is_project_folder(folder: Path) -> bool:
    """True if the folder looks like a code project (has a marker inside)."""
    return any((folder / marker).exists() for marker in PROJECT_MARKERS)


def is_hidden_or_system(path: Path) -> bool:
    """True for dot-files, and for files Windows marks as hidden or system."""
    if path.name.startswith("."):
        return True
    # st_file_attributes only exists on Windows; elsewhere treat it as 0
    attributes = getattr(path.stat(), "st_file_attributes", 0)
    return bool(attributes & (stat.FILE_ATTRIBUTE_HIDDEN | stat.FILE_ATTRIBUTE_SYSTEM))


def should_skip(path: Path) -> bool:
    """True for files the organizer must never move."""
    return (
        path.name.lower() in SKIP_NAMES
        or path.suffix.lower() in SKIP_EXTENSIONS
        or is_hidden_or_system(path)
    )


def unique_destination(destination: Path, taken: set[Path]) -> Path:
    """Add ' (1)', ' (2)'... if the name is used on disk or already planned.

    This is how we guarantee the organizer never overwrites a file.
    """
    candidate = destination
    counter = 1
    while candidate.exists() or candidate in taken:
        candidate = destination.with_name(f"{destination.stem} ({counter}){destination.suffix}")
        counter += 1
    return candidate


def plan_moves(folder: Path, rules: dict[str, list[str]]) -> list[Move]:
    """Return the moves needed to sort the loose files in `folder`.

    Only files directly inside `folder` are planned. Subfolders are never
    moved or looked inside. Nothing on disk changes here.
    """
    if is_project_folder(folder):
        return []

    moves: list[Move] = []
    taken: set[Path] = set()

    for path in sorted(folder.iterdir()):
        if not path.is_file() or should_skip(path):
            continue

        category = categorize(path.name, rules)
        if category is None:
            continue  # unknown type: leave it where it is

        destination = unique_destination(folder / category / path.name, taken)
        taken.add(destination)
        moves.append(Move(source=path, destination=destination))

    return moves


# ---------------------------------------------------------------------------
# Applying: actually move the files, and record everything for undo
# ---------------------------------------------------------------------------

@dataclass
class RunResult:
    """What happened during apply or undo, for the UI to show."""
    done: int = 0
    failed: list[str] = None  # friendly messages, one per file that failed

    def __post_init__(self):
        if self.failed is None:
            self.failed = []


def apply_moves(moves: list[Move], log_path: Path) -> RunResult:
    """Move each file to its destination and write an undo log.

    - Never overwrites: if the destination appeared since planning, skip it.
    - One failed file (e.g. open in another app) doesn't stop the rest.
    - The log is written even if something goes wrong halfway, so undo
      always knows exactly what was moved.
    """
    result = RunResult()
    log = {"moves": [], "created_folders": []}

    try:
        for move in moves:
            parent = move.destination.parent
            if not parent.exists():
                parent.mkdir(parents=True)
                log["created_folders"].append(str(parent))

            if move.destination.exists():
                result.failed.append(f"{move.source.name}: a file with that name is already there")
                continue

            try:
                move.source.rename(move.destination)
            except OSError:
                result.failed.append(f"{move.source.name}: couldn't move it (it may be open in another app)")
                continue

            log["moves"].append({"source": str(move.source), "destination": str(move.destination)})
            result.done += 1
    finally:
        save_log(log, log_path)

    return result


def save_log(log: dict, log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)


def undo_last_run(log_path: Path) -> RunResult:
    """Put every file from the last run back where it was.

    Moves are undone in reverse order. A file is only moved back if its
    original spot is still free, so undo never overwrites anything either.
    Folders the run created are removed only if they are empty again.
    """
    result = RunResult()

    if not log_path.exists():
        result.failed.append("There's nothing to undo yet.")
        return result

    with open(log_path, encoding="utf-8") as f:
        log = json.load(f)

    not_undone = []  # moves we couldn't reverse, kept so the user can retry

    for entry in reversed(log["moves"]):
        source = Path(entry["source"])
        destination = Path(entry["destination"])

        if not destination.exists():
            # the user moved or deleted it since; nothing we can put back
            result.failed.append(f"{destination.name}: it's no longer in {destination.parent.name}")
            continue
        if source.exists():
            result.failed.append(f"{source.name}: another file now has its original name")
            not_undone.append(entry)
            continue

        try:
            destination.rename(source)
            result.done += 1
        except OSError:
            result.failed.append(f"{destination.name}: couldn't move it back (it may be open in another app)")
            not_undone.append(entry)

    for folder in reversed(log["created_folders"]):
        try:
            Path(folder).rmdir()  # rmdir only works on empty folders, so this is safe
        except OSError:
            pass  # not empty (user added files) or already gone: leave it

    if not_undone:
        # keep a log of what's left, so pressing Undo again can retry
        save_log({"moves": list(reversed(not_undone)), "created_folders": []}, log_path)
    else:
        log_path.unlink()  # fully undone, so there's nothing left to undo
    return result