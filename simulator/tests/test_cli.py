from tl_simulator.cli import main


def test_generate_into_empty_folder(tmp_path):
    out = tmp_path / "out"
    assert main(["generate", "--nights", "1", "--out", str(out)]) == 0
    assert (out / "night-01" / "results.xml").is_file()


def test_refuses_non_empty_folder_without_force(tmp_path):
    keep = tmp_path / "keep.txt"
    keep.write_text("do not delete")
    assert main(["generate", "--nights", "1", "--out", str(tmp_path)]) == 1
    assert keep.exists()


def test_force_replaces_non_empty_folder(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "stale.txt").write_text("old")
    assert main(["generate", "--nights", "1", "--out", str(out), "--force"]) == 0
    assert not (out / "stale.txt").exists()
    assert (out / "night-01").is_dir()


def test_rejects_zero_nights(tmp_path):
    assert main(["generate", "--nights", "0", "--out", str(tmp_path / "out")]) == 2
    assert not (tmp_path / "out").exists()
