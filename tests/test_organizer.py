from pathlib import Path

from organizer import categorize, load_rules

RULES = load_rules(Path(__file__).parent.parent / "rules.json")


def test_known_extension():
    assert categorize("photo.jpg", RULES) == "Images"


def test_uppercase_extension():
    assert categorize("PHOTO.JPG", RULES) == "Images"


def test_each_category_has_a_working_example():
    assert categorize("report.pdf", RULES) == "Documents"
    assert categorize("budget.xlsx", RULES) == "Spreadsheets"
    assert categorize("song.mp3", RULES) == "Audio"
    assert categorize("setup.exe", RULES) == "Installers"


def test_unknown_extension_returns_none():
    assert categorize("mystery.xyz", RULES) is None


def test_no_extension_returns_none():
    assert categorize("README", RULES) is None


def test_only_last_extension_counts():
    # "backup.tar.gz" ends in .gz, which is an archive
    assert categorize("backup.tar.gz", RULES) == "Archives"


def test_dot_in_name_is_not_an_extension():
    # "my.photos" has suffix ".photos", which isn't a rule
    assert categorize("my.photos", RULES) is None
