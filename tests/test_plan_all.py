from pathlib import Path

from organizer import build_plan, find_empties, load_rules, protected_reason

RULES = load_rules(Path(__file__).parent.parent / "rules.json")


def test_plan_covers_several_folders(tmp_path):
    a, b = tmp_path / "Downloads", tmp_path / "Desktop"
    a.mkdir(); b.mkdir()
    (a / "photo.jpg").write_text("x")
    (b / "notes.pdf").write_text("x")
    plan = build_plan([a, b], RULES, clean_empty=False)
    assert {m.source.name for m in plan.moves} == {"photo.jpg", "notes.pdf"}
    assert plan.empties == []


def test_empty_file_is_removed_not_moved_when_cleaning(tmp_path):
    (tmp_path / "blank.txt").touch()
    plan = build_plan([tmp_path], RULES, clean_empty=True)
    assert plan.moves == []
    assert [p.name for p in plan.empties] == ["blank.txt"]


def test_empty_file_is_sorted_when_cleaning_is_off(tmp_path):
    (tmp_path / "blank.txt").touch()
    plan = build_plan([tmp_path], RULES, clean_empty=False)
    assert [m.source.name for m in plan.moves] == ["blank.txt"]


def test_project_folder_ticked_directly_is_not_cleaned(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "empty_dir").mkdir()
    assert find_empties(tmp_path) == []


def test_drive_root_is_protected():
    assert protected_reason(Path(Path.home().anchor)) is not None


def test_home_folder_is_protected():
    assert protected_reason(Path.home()) is not None


# Fixed paths, not tmp_path: on Windows, pytest's temp folders live inside
# AppData, which would make these tests pass or fail for the wrong reason.
def test_system_folders_are_protected():
    assert protected_reason(Path("/data/Program Files/App")) is not None
    assert protected_reason(Path("/data/AppData/Local")) is not None


def test_normal_folder_is_allowed():
    assert protected_reason(Path("/data/Downloads")) is None