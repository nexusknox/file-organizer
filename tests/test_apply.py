from pathlib import Path

from organizer import apply_moves, load_rules, plan_moves, undo_last_run, Move

RULES = load_rules(Path(__file__).parent.parent / "rules.json")


def make_files(folder: Path, *names: str) -> None:
    for name in names:
        (folder / name).write_text(f"content of {name}")


def organize(folder: Path, log: Path):
    return apply_moves(plan_moves(folder, RULES), log)


def test_files_are_moved_into_category_folders(tmp_path):
    make_files(tmp_path, "photo.jpg", "report.pdf")
    result = organize(tmp_path, tmp_path / "log.json")

    assert result.done == 2 and result.failed == []
    assert (tmp_path / "Images" / "photo.jpg").read_text() == "content of photo.jpg"
    assert (tmp_path / "Documents" / "report.pdf").exists()
    assert not (tmp_path / "photo.jpg").exists()


def test_log_is_written(tmp_path):
    make_files(tmp_path, "photo.jpg")
    log = tmp_path / "logs" / "last_run.json"
    organize(tmp_path, log)
    assert log.exists()


def test_never_overwrites_a_file_that_appeared_after_planning(tmp_path):
    make_files(tmp_path, "photo.jpg")
    moves = plan_moves(tmp_path, RULES)

    (tmp_path / "Images").mkdir()
    (tmp_path / "Images" / "photo.jpg").write_text("precious")

    result = apply_moves(moves, tmp_path / "log.json")
    assert result.done == 0 and len(result.failed) == 1
    assert (tmp_path / "Images" / "photo.jpg").read_text() == "precious"
    assert (tmp_path / "photo.jpg").exists()


def test_one_failure_does_not_stop_the_rest(tmp_path):
    make_files(tmp_path, "good.jpg")
    moves = [
        Move(tmp_path / "missing.jpg", tmp_path / "Images" / "missing.jpg"),
        Move(tmp_path / "good.jpg", tmp_path / "Images" / "good.jpg"),
    ]
    result = apply_moves(moves, tmp_path / "log.json")
    assert result.done == 1 and len(result.failed) == 1
    assert (tmp_path / "Images" / "good.jpg").exists()


def test_undo_puts_everything_back_and_removes_new_folders(tmp_path):
    make_files(tmp_path, "photo.jpg", "report.pdf")
    log = tmp_path / "log.json"
    organize(tmp_path, log)

    result = undo_last_run(log)

    assert result.done == 2 and result.failed == []
    assert (tmp_path / "photo.jpg").read_text() == "content of photo.jpg"
    assert (tmp_path / "report.pdf").exists()
    assert not (tmp_path / "Images").exists()
    assert not (tmp_path / "Documents").exists()
    assert not log.exists()


def test_undo_keeps_folders_that_already_existed(tmp_path):
    (tmp_path / "Images").mkdir()
    make_files(tmp_path / "Images", "old.jpg")
    make_files(tmp_path, "new.jpg")
    log = tmp_path / "log.json"
    organize(tmp_path, log)

    undo_last_run(log)

    assert (tmp_path / "Images" / "old.jpg").exists()
    assert (tmp_path / "new.jpg").exists()


def test_undo_keeps_a_created_folder_if_user_added_files(tmp_path):
    make_files(tmp_path, "photo.jpg")
    log = tmp_path / "log.json"
    organize(tmp_path, log)
    make_files(tmp_path / "Images", "added_later.jpg")

    undo_last_run(log)

    assert (tmp_path / "photo.jpg").exists()
    assert (tmp_path / "Images" / "added_later.jpg").exists()


def test_undo_never_overwrites(tmp_path):
    make_files(tmp_path, "photo.jpg")
    log = tmp_path / "log.json"
    organize(tmp_path, log)
    (tmp_path / "photo.jpg").write_text("new file, same name")

    result = undo_last_run(log)

    assert result.done == 0 and len(result.failed) == 1
    assert (tmp_path / "photo.jpg").read_text() == "new file, same name"
    assert (tmp_path / "Images" / "photo.jpg").exists()


def test_undo_with_nothing_to_undo_gives_a_friendly_message(tmp_path):
    result = undo_last_run(tmp_path / "log.json")
    assert result.failed == ["There's nothing to undo yet."]


def test_undo_can_be_retried_after_a_blocked_file(tmp_path):
    make_files(tmp_path, "photo.jpg")
    log = tmp_path / "log.json"
    organize(tmp_path, log)
    blocker = tmp_path / "photo.jpg"
    blocker.write_text("in the way")

    undo_last_run(log)
    assert log.exists()  # still remembers the file it couldn't restore

    blocker.unlink()
    result = undo_last_run(log)
    assert result.done == 1
    assert (tmp_path / "photo.jpg").read_text() == "content of photo.jpg"
    assert not log.exists()