from __future__ import annotations

import pytest

from pynhts import __version__, cli
from pynhts.io import fetcher


def test_version_and_help(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(["--version"])
    assert e.value.code == 0 and __version__ in capsys.readouterr().out
    with pytest.raises(SystemExit):
        cli.main([])  # a command is required


def test_info_on_empty_cache(tmp_path, capsys):
    assert cli.main(["--cache", str(tmp_path), "info"]) == 0
    out = capsys.readouterr().out
    assert "trippub.csv" in out and "absent" in out and "not built" in out
    assert "923572" not in out  # no data needed for info


def test_register_rejects_foreign_files(tmp_path, capsys):
    src = tmp_path / "mine"
    src.mkdir()
    (src / "hhpub.csv").write_text("not the real file")
    with pytest.raises(fetcher.NHTSIntegrityError):
        cli.main(["--cache", str(tmp_path / "c"), "register", str(src)])


def test_fetch_offline_without_data_fails_clearly(tmp_path):
    with pytest.raises(FileNotFoundError, match="offline"):
        cli.main(["--cache", str(tmp_path), "fetch", "--offline"])
