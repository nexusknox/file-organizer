"""Core logic for File Organizer.

No UI code lives here, so everything can be tested on temporary folders.
"""

import json
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