"""Unit tests for pynhts.io.fetch using tiny synthetic files and a fake downloader."""

from __future__ import annotations

import hashlib
import shutil
import zipfile
from pathlib import Path

import pytest

from pynhts.io import fetcher as fetch_mod
from pynhts.io.registry import Archive, Member, Registry, load_registry

FILES = {"hhpub.csv": b"HOUSEID\n1\n2\n", "trippub.csv": b"HOUSEID,PERSONID\n1,01\n"}


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _fake_registry(zip_bytes: bytes) -> Registry:
    return Registry(
        wave=2017,
        citation="fake",
        archives={
            "csv.zip": Archive("csv.zip", "https://example.invalid/csv.zip",
                               _sha(zip_bytes), len(zip_bytes))
        },
        members={
            n: Member(n, "csv.zip", "core", _sha(b), len(b), None) for n, b in FILES.items()
        },
        documentation={},
    )


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    zpath = tmp_path / "served" / "csv.zip"
    zpath.parent.mkdir()
    with zipfile.ZipFile(zpath, "w") as zf:
        for n, b in FILES.items():
            zf.writestr(n, b)
    reg = _fake_registry(zpath.read_bytes())
    monkeypatch.setattr(fetch_mod, "load_registry", lambda wave: reg)
    calls: list[str] = []

    def fake_retrieve(url, known_hash, fname, path, progressbar=False):
        calls.append(url)
        assert known_hash == f"sha256:{reg.archives['csv.zip'].sha256}"
        Path(path).mkdir(parents=True, exist_ok=True)
        dest = Path(path) / fname
        shutil.copy(zpath, dest)
        return str(dest)

    import pooch

    monkeypatch.setattr(pooch, "retrieve", fake_retrieve)
    return {"cache": tmp_path / "cache", "calls": calls, "reg": reg, "tmp": tmp_path}


def test_fetch_downloads_verifies_and_is_idempotent(env):
    out = fetch_mod.fetch(2017, cache=env["cache"])
    assert set(out) == set(FILES)
    for n, p in out.items():
        assert p.read_bytes() == FILES[n]
    assert len(env["calls"]) == 1
    fetch_mod.fetch(2017, cache=env["cache"])
    assert len(env["calls"]) == 1  # second call used the verified cache


def test_fetch_removes_archive_by_default(env):
    fetch_mod.fetch(2017, cache=env["cache"])
    assert not (fetch_mod.raw_dir(2017, env["cache"]) / "_downloads").exists()


def test_fetch_offline_raises_when_missing(env):
    with pytest.raises(FileNotFoundError, match="offline"):
        fetch_mod.fetch(2017, cache=env["cache"], offline=True)
    assert env["calls"] == []


def test_fetch_offline_works_after_online(env):
    fetch_mod.fetch(2017, cache=env["cache"])
    out = fetch_mod.fetch(2017, cache=env["cache"], offline=True)
    assert set(out) == set(FILES)


def test_fetch_redownloads_corrupted_cache_file(env):
    out = fetch_mod.fetch(2017, cache=env["cache"])
    out["hhpub.csv"].write_bytes(b"corrupted!")
    out2 = fetch_mod.fetch(2017, cache=env["cache"])
    assert out2["hhpub.csv"].read_bytes() == FILES["hhpub.csv"]
    assert len(env["calls"]) == 2


def test_fetch_rejects_member_with_wrong_hash(env, monkeypatch):
    bad = Member("hhpub.csv", "csv.zip", "core", "0" * 64, len(FILES["hhpub.csv"]), None)
    reg = env["reg"]
    reg2 = Registry(2017, "fake", reg.archives, {**reg.members, "hhpub.csv": bad}, {})
    monkeypatch.setattr(fetch_mod, "load_registry", lambda wave: reg2)
    with pytest.raises(fetch_mod.NHTSIntegrityError):
        fetch_mod.fetch(2017, cache=env["cache"])


def test_register_local_adopts_matching_files(env):
    src = env["tmp"] / "mine"
    src.mkdir()
    for n, b in FILES.items():
        (src / n).write_bytes(b)
    adopted = fetch_mod.register_local(src, cache=env["cache"], groups=("core",))
    assert set(adopted) == set(FILES)
    assert env["calls"] == []
    out = fetch_mod.fetch(2017, cache=env["cache"], offline=True)
    assert set(out) == set(FILES)


def test_register_local_rejects_wrong_file(env):
    src = env["tmp"] / "mine"
    src.mkdir()
    (src / "hhpub.csv").write_bytes(b"<html>soft 404</html>")
    with pytest.raises(fetch_mod.NHTSIntegrityError):
        fetch_mod.register_local(src, cache=env["cache"], groups=("core",))
    assert not (fetch_mod.raw_dir(2017, env["cache"]) / "hhpub.csv").exists()


def test_register_local_empty_dir(env):
    src = env["tmp"] / "empty"
    src.mkdir()
    with pytest.raises(FileNotFoundError):
        fetch_mod.register_local(src, cache=env["cache"], groups=("core",))


def test_cache_dir_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv(fetch_mod.CACHE_ENV, str(tmp_path / "x"))
    assert fetch_mod.cache_dir() == tmp_path / "x"
    assert fetch_mod.cache_dir(tmp_path / "y") == tmp_path / "y"


def test_real_registry_is_complete_and_well_formed():
    reg = load_registry(2017)
    core = {m.name for m in reg.members_in(("core",))}
    assert core == {"hhpub.csv", "perpub.csv", "trippub.csv", "vehpub.csv"}
    assert {m.name for m in reg.members_in(("replicates",))} == {"hhwgt.csv", "perwgt.csv"}
    for m in reg.members.values():
        assert len(m.sha256) == 64 and m.archive in reg.archives
    assert reg.members["trippub.csv"].rows == 923572


def test_unsupported_wave():
    with pytest.raises(ValueError, match="not supported"):
        load_registry(1995)
