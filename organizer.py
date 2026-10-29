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