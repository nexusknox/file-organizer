from pathlib import Path

from organizer import load_rules, plan_moves

RULES = load_rules(Path(__file__).parent.parent / "rules.json")


def make_files(folder: Path, *names: str) -> None:
    for name in names:
        (folder / name).write_text("x")


def as_names(moves, folder: Path) -> dict[str, str]:
    """{"photo.jpg": "Images/photo.jpg"} - easier to read in asserts."""
    return {
        m.source.name: m.destination.relative_to(folder).as_posix() for m in moves
    }


def test_files_are_planned_into_category_folders(tmp_path):
    make_files(tmp_path, "photo.jpg", "report.pdf", "song.mp3")
    assert as_names(plan_moves(tmp_path, RULES), tmp_path) == {
        "photo.jpg": "Images/photo.jpg",
        "report.pdf": "Documents/report.pdf",
        "song.mp3": "Audio/song.mp3",
    }


def test_planning_does_not_change_anything(tmp_path):
    make_files(tmp_path, "photo.jpg")
    plan_moves(tmp_path, RULES)
    assert (tmp_path / "photo.jpg").exists()
    assert not (tmp_path / "Images").exists()


def test_unknown_files_are_left_alone(tmp_path):
    make_files(tmp_path, "mystery.xyz", "README")
    assert plan_moves(tmp_path, RULES) == []


def test_subfolders_are_never_moved_or_entered(tmp_path):
    sub = tmp_path / "New folder"
    sub.mkdir()
    make_files(sub, "inside.jpg")
    assert plan_moves(tmp_path, RULES) == []


def test_project_folder_is_skipped(tmp_path):
    (tmp_path / ".git").mkdir()
    make_files(tmp_path, "photo.jpg")
    assert plan_moves(tmp_path, RULES) == []


def test_shortcuts_and_system_files_are_skipped(tmp_path):
    make_files(tmp_path, "Chrome.lnk", "desktop.ini", ".hidden.jpg")
    assert plan_moves(tmp_path, RULES) == []


def test_existing_file_is_never_overwritten(tmp_path):
    (tmp_path / "Images").mkdir()
    make_files(tmp_path / "Images", "photo.jpg")
    make_files(tmp_path, "photo.jpg")
    assert as_names(plan_moves(tmp_path, RULES), tmp_path) == {
        "photo.jpg": "Images/photo (1).jpg"
    }