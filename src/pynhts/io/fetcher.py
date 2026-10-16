"""Verified download, offline registration and caching of raw NHTS files.

Every file is accepted only if its SHA-256 matches the pinned registry. This matters because
the official server returns HTTP 200 with an HTML page for files that do not exist.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import zipfile
from pathlib import Path

import platformdirs

from pynhts.io.registry import Archive, Member, load_registry

CACHE_ENV = "PYNHTS_CACHE_DIR"
_CHUNK = 1 << 20


class NHTSIntegrityError(ValueError):
    """A file's SHA-256 does not match the pinned registry."""


def cache_dir(cache: str | os.PathLike[str] | None = None) -> Path:
    """Return the cache root: argument, else ``$PYNHTS_CACHE_DIR``, else the user cache dir."""
    if cache is not None:
        return Path(cache)
    env = os.environ.get(CACHE_ENV)
    return Path(env) if env else Path(platformdirs.user_cache_dir("pynhts"))


def raw_dir(wave: int = 2017, cache: str | os.PathLike[str] | None = None) -> Path:
    """Directory that holds the verified raw CSV files of ``wave``."""
    return cache_dir(cache) / str(wave) / "raw"


def sha256_file(path: Path) -> str:
    """Return the hex SHA-256 of a file, read in 1 MiB chunks."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(_CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def _stamp(path: Path) -> Path:
    return path.with_name(path.name + ".verified.json")


def _write_stamp(path: Path, member: Member) -> None:
    st = path.stat()
    _stamp(path).write_text(
        json.dumps({"sha256": member.sha256, "size": st.st_size, "mtime_ns": st.st_mtime_ns})
    )


def _is_verified(path: Path, member: Member) -> bool:
    """True if ``path`` is the pinned file. Re-hashes only when size or mtime changed."""
    if not path.is_file() or path.stat().st_size != member.size:
        return False
    st = path.stat()
    stamp = _stamp(path)
    if stamp.is_file():
        try:
            rec = json.loads(stamp.read_text())
            if (
                rec["sha256"] == member.sha256
                and rec["size"] == st.st_size
                and rec["mtime_ns"] == st.st_mtime_ns
            ):
                return True
        except (KeyError, ValueError):
            pass
    if sha256_file(path) != member.sha256:
        return False
    _write_stamp(path, member)
    return True


def fetch(
    wave: int = 2017,
    groups: tuple[str, ...] = ("core",),
    *,
    cache: str | os.PathLike[str] | None = None,
    offline: bool = False,
    keep_archives: bool = False,
    progressbar: bool = False,
    names: tuple[str, ...] | None = None,
) -> dict[str, Path]:
    """Make the raw files of ``groups`` available in the cache and return their paths.

    Args:
        wave: Survey year (only 2017 in Phase 1).
        groups: ``"core"`` (household, person, trip, vehicle) and/or ``"replicates"``
            (98 jackknife replicate weights; large).
        cache: Cache root override.
        offline: Never touch the network; raise if a file is missing.
        keep_archives: Keep the downloaded zip files after extraction.
        progressbar: Show a download progress bar.
        names: Restrict to these member file names (e.g. ``("hhwgt.csv",)``).

    Returns:
        Mapping from member file name (e.g. ``"trippub.csv"``) to its verified local path.

    Raises:
        FileNotFoundError: offline and a file is missing.
        NHTSIntegrityError: a downloaded or extracted file fails its SHA-256 check.
    """
    reg = load_registry(wave)
    out_dir = raw_dir(wave, cache)
    out_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, Path] = {}
    missing: dict[str, list[Member]] = {}
    for m in reg.members_in(groups):
        if names is not None and m.name not in names:
            continue
        path = out_dir / m.name
        if _is_verified(path, m):
            result[m.name] = path
        else:
            missing.setdefault(m.archive, []).append(m)
    if missing and offline:
        listed = ", ".join(sorted(m.name for ms in missing.values() for m in ms))
        raise FileNotFoundError(
            f"offline mode and these NHTS {wave} files are not in {out_dir}: {listed}. "
            "Run fetch() online once, or adopt local copies with register_local()."
        )
    for archive_name, members in missing.items():
        result.update(
            _download_and_extract(
                reg.archives[archive_name], members, out_dir, keep_archives, progressbar
            )
        )
    return result


def _download_and_extract(
    archive: Archive, members: list[Member], out_dir: Path, keep: bool, progressbar: bool
) -> dict[str, Path]:
    import pooch

    dl_dir = out_dir / "_downloads"
    zpath = Path(
        pooch.retrieve(
            url=archive.url,
            known_hash=f"sha256:{archive.sha256}",
            fname=archive.name,
            path=dl_dir,
            progressbar=progressbar,
        )
    )
    done: dict[str, Path] = {}
    with zipfile.ZipFile(zpath) as zf:
        for m in members:
            tmp = out_dir / (m.name + ".part")
            with zf.open(m.name) as src, open(tmp, "wb") as dst:
                shutil.copyfileobj(src, dst, _CHUNK)
            if sha256_file(tmp) != m.sha256:
                tmp.unlink()
                raise NHTSIntegrityError(f"{m.name} extracted from {archive.name} failed SHA-256")
            final = out_dir / m.name
            os.replace(tmp, final)
            _write_stamp(final, m)
            done[m.name] = final
    if not keep:
        zpath.unlink(missing_ok=True)
        try:
            dl_dir.rmdir()
        except OSError:
            pass
    return done


def register_local(
    source: str | os.PathLike[str],
    wave: int = 2017,
    *,
    cache: str | os.PathLike[str] | None = None,
    groups: tuple[str, ...] = ("core", "replicates"),
    link: bool = False,
) -> dict[str, Path]:
    """Adopt NHTS CSV files you already have, after proving they are the official ones.

    Args:
        source: Directory containing some of the registry's CSV files.
        wave: Survey year.
        cache: Cache root override.
        groups: Which registry groups to look for in ``source``.
        link: Hard-link instead of copying (same volume only; falls back to copying).

    Returns:
        Mapping from member name to the cache path of each adopted file.

    Raises:
        FileNotFoundError: ``source`` is not a directory or contains no registry file.
        NHTSIntegrityError: a present file does not match the pinned SHA-256.
    """
    src_dir = Path(source)
    if not src_dir.is_dir():
        raise FileNotFoundError(f"{src_dir} is not a directory")
    reg = load_registry(wave)
    out_dir = raw_dir(wave, cache)
    out_dir.mkdir(parents=True, exist_ok=True)
    adopted: dict[str, Path] = {}
    for m in reg.members_in(groups):
        src = src_dir / m.name
        if not src.is_file():
            continue
        if src.stat().st_size != m.size or sha256_file(src) != m.sha256:
            raise NHTSIntegrityError(
                f"{src} is not the official NHTS {wave} file {m.name} (size/SHA-256 mismatch)"
            )
        dest = out_dir / m.name
        if not _is_verified(dest, m):
            _place(src, dest, link)
            _write_stamp(dest, m)
        adopted[m.name] = dest
    if not adopted:
        raise FileNotFoundError(f"none of the NHTS {wave} files were found in {src_dir}")
    return adopted


def _place(src: Path, dest: Path, link: bool) -> None:
    tmp = dest.with_name(dest.name + ".part")
    tmp.unlink(missing_ok=True)
    if link:
        try:
            os.link(src, tmp)
        except OSError:
            shutil.copy2(src, tmp)
    else:
        shutil.copy2(src, tmp)
    os.replace(tmp, dest)
