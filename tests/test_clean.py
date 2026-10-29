import os
from pathlib import Path

from organizer import apply_moves, clean_empties, find_empties, load_rules, plan_moves, undo_last_run

RULES = load_rules(Path(__file__).parent.parent / "rules.json")


class FakeRecycleBin:
    """Stands in for send2trash so tests never touch the real Recycle Bin."""

    def __init__(self):
        self.items = []

    def __call__(self, path: str):
        self.items.append(path)
        p = Path(path)
        p.rmdir() if p.is_dir() else p.unlink()


def names(paths, root):
    return [p.relative_to(root).as_posix() for p in paths]


def test_finds_empty_files_and_folders(tmp_path):
    (tmp_path / "empty.txt").touch()
    (tmp_path / "full.txt").write_text("hi")
    (tmp_path / "New folder").mkdir()
    assert sorted(names(find_empties(tmp_path), tmp_path)) == ["New folder", "empty.txt"]


def test_nested_empty_folders_listed_children_first(tmp_path):
    (tmp_path / "a" / "b").mkdir(parents=True)
    assert names(find_empties(tmp_path), tmp_path) == ["a/b", "a"]


def test_folder_with_a_real_file_is_kept(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "empty.txt").touch()
    (tmp_path / "a" / "real.txt").write_text("data")
    assert names(find_empties(tmp_path), tmp_path) == ["a/empty.txt"]


def test_root_folder_is_never_listed(tmp_path):
    assert find_empties(tmp_path) == []


def test_intentional_empty_files_are_kept(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").touch()
    (tmp_path / ".gitkeep").touch()
    assert find_empties(tmp_path) == []


def test_project_folders_are_not_looked_inside(tmp_path):
    project = tmp_path / "labellint"
    (project / ".git").mkdir(parents=True)
    (project / "empty.txt").touch()
    (project / "empty_dir").mkdir()
    assert find_empties(tmp_path) == []


def test_hidden_items_are_kept(tmp_path):
    (tmp_path / ".config").mkdir()
    assert find_empties(tmp_path) == []


def test_links_are_never_followed_or_removed(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "keep.txt").write_text("data")
    os.symlink(target, tmp_path / "link", target_is_directory=True)
    assert "link" not in names(find_empties(tmp_path), tmp_path)


def test_clean_removes_and_logs(tmp_path):
    (tmp_path / "empty.txt").touch()
    (tmp_path / "a" / "b").mkdir(parents=True)
    bin = FakeRecycleBin()
    log = tmp_path / "logs" / "run.json"

    result = clean_empties(find_empties(tmp_path), log, trash=bin)

    assert result.done == 3 and result.failed == []
    assert not (tmp_path / "a").exists() and not (tmp_path / "empty.txt").exists()
    assert len(bin.items) == 3


def test_clean_skips_item_that_got_content_after_preview(tmp_path):
    (tmp_path / "empty.txt").touch()
    empties = find_empties(tmp_path)
    (tmp_path / "empty.txt").write_text("now it has data")

    result = clean_empties(empties, tmp_path / "log.json", trash=FakeRecycleBin())

    assert result.done == 0 and len(result.failed) == 1
    assert (tmp_path / "empty.txt").read_text() == "now it has data"


def test_one_undo_reverses_moves_and_cleaning(tmp_path):
    (tmp_path / "photo.jpg").write_text("pic")
    (tmp_path / "empty.txt").touch()
    (tmp_path / "Old" / "Older").mkdir(parents=True)
    log = tmp_path / "logs" / "run.json"

    apply_moves(plan_moves(tmp_path, RULES), log)
    clean_empties(find_empties(tmp_path), log, trash=FakeRecycleBin())
    assert not (tmp_path / "Old").exists()

    result = undo_last_run(log)

    assert result.failed == []
    assert (tmp_path / "photo.jpg").read_text() == "pic"
    assert not (tmp_path / "Images").exists()
    assert (tmp_path / "empty.txt").exists()
    assert (tmp_path / "Old" / "Older").is_dir()
    assert not log.exists()