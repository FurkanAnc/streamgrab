from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from streamgrab.core import store, updater
from streamgrab.core.errors import explain
from streamgrab.core.playlist import parse_ranges, safe_folder_name
from streamgrab.core.probe import _normalize
from streamgrab.engines.loader import load_engine


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1-3", {1, 2, 3}),
        ("2, 5", {2, 5}),
        ("8-", {8, 9, 10}),
        ("-2", {1, 2}),
        ("9-50", {9, 10}),
        ("", set()),
    ],
)
def test_parse_ranges(text, expected):
    assert parse_ranges(text, 10) == expected


@pytest.mark.parametrize("text", ["abc", "5-2", "-", "1--2"])
def test_parse_ranges_rejects_garbage(text):
    with pytest.raises(ValueError):
        parse_ranges(text, 10)


def test_safe_folder_name():
    assert safe_folder_name('A/B: "C"?') == "A B C"
    assert safe_folder_name("  isim...  ") == "isim"
    assert safe_folder_name("CON") == "Oynatma listesi"
    assert safe_folder_name("???") == "Oynatma listesi"
    assert len(safe_folder_name("x" * 300)) == 100


@pytest.mark.parametrize(
    ("raw", "retryable"),
    [
        ("[youtube] x: Private video. Sign in", False),
        ("Requested format is not available", False),
        ("HTTP Error 429: Too Many Requests", True),
        ("unable to download video data: <urlopen error timed out>", True),
        ("garip yeni bir hata", True),
    ],
)
def test_explain_retryable(raw, retryable):
    assert explain(raw).retryable is retryable


def test_explain_keeps_unknown_text():
    assert explain("garip yeni bir hata").message == "garip yeni bir hata"


def test_normalize_single_video():
    info = _normalize({"_type": "video", "id": "v1", "title": "T", "formats": []}, "http://x")
    assert not info.is_playlist
    assert info.id == "v1"


def test_normalize_playlist_marks_hidden_and_skips_bad_entries():
    data = {
        "_type": "playlist",
        "title": "L",
        "extractor_key": "YoutubeTab",
        "entries": [
            {"id": "a", "url": "https://y/a", "title": "A", "ie_key": "Youtube", "duration": 90},
            {"id": "b", "url": "https://y/b", "title": None, "ie_key": "Youtube"},
            {"id": "c", "url": "https://y/c", "title": "[Private video]", "ie_key": "Youtube"},
            None,
            {"id": "d", "url": "not-a-url", "title": "D"},
        ],
    }
    info = _normalize(data, "http://x")
    assert info.is_playlist
    assert [e.id for e in info.entries] == ["a", "b", "c"]
    assert [e.available for e in info.entries] == [True, False, False]
    assert [e.index for e in info.entries] == [1, 2, 3]
    assert info.entries[0].duration == 90
    assert info.entries[0].extractor == "Youtube"


def test_normalize_channel_flattens_tabs_and_dedupes():
    data = {
        "_type": "playlist",
        "title": "Kanal",
        "entries": [
            {
                "_type": "playlist",
                "title": "Videos",
                "extractor_key": "YoutubeTab",
                "entries": [{"id": "a", "url": "https://y/a", "title": "A", "ie_key": "Youtube"}],
            },
            {
                "_type": "playlist",
                "title": "Shorts",
                "entries": [
                    {"id": "a", "url": "https://y/a", "title": "A", "ie_key": "Youtube"},
                    {"id": "s", "url": "https://y/s", "title": "S", "ie_key": "Youtube"},
                ],
            },
        ],
    }
    assert [e.id for e in _normalize(data, "http://x").entries] == ["a", "s"]


def test_archive_key_matches_ytdlp_format():
    assert store.archive_key("Youtube", "abc") == "youtube abc"


def test_store_tolerates_corrupt_files():
    from streamgrab.paths import history_file, queue_file

    queue_file().write_text("{bozuk", encoding="utf-8")
    assert store.load_queue() == []

    history_file().write_text('{"title": "a"}\nbozuk\n{"title": "b"}\n', encoding="utf-8")
    assert [r["title"] for r in store.load_history()] == ["b", "a"]
    store.clear_history()
    assert store.load_history() == []


def test_expected_hash_formats():
    digest = "a" * 64
    other = "b" * 64
    sums = f"{other}  other.zip\n{digest}  wanted.zip\n"
    assert updater.expected_hash(sums, "wanted.zip") == digest
    assert updater.expected_hash(f"{digest} *wanted.zip\n{other} *x\n", "wanted.zip") == digest
    assert updater.expected_hash(f"Hash: {digest}\n", "wanted.zip") == digest
    with pytest.raises(updater.UpdateError):
        updater.expected_hash(sums, "yok.zip")


def test_verify_deletes_tampered_file(tmp_path: Path):
    target = tmp_path / "tool.exe"
    target.write_bytes(b"sahte")
    with pytest.raises(updater.UpdateError):
        updater._verify(hashlib.sha256(b"sahte").hexdigest(), "0" * 64, target)
    assert not target.exists()


def test_engine_commands_are_data_driven():
    engine = load_engine("yt-dlp")
    playlist = engine.probe_command("http://x")
    single = engine.probe_command("http://x", single=True)
    assert "--flat-playlist" in playlist and "--no-playlist" not in playlist
    assert "--no-playlist" in single and "--flat-playlist" not in single

    download = engine.download_command(
        "http://x", "C:/o", "b", archive_file="C:/a.txt", filename_prefix="007 - "
    )
    assert download[download.index("--download-archive") + 1] == "C:/a.txt"
    assert download[download.index("-o") + 1].startswith("007 - %(title)")


def test_format_sort_is_passed_only_when_set():
    engine = load_engine("yt-dlp")
    sorted_command = engine.download_command("http://x", "C:/o", "b", format_sort="res:1080,tbr")
    assert sorted_command[sorted_command.index("-S") + 1] == "res:1080,tbr"
    assert "-S" not in engine.download_command("http://x", "C:/o", "b")


def test_engine_spec_is_valid_json():
    path = Path(__file__).parent.parent / "streamgrab" / "engines" / "yt-dlp.json"
    assert json.loads(path.read_text(encoding="utf-8"))["id"] == "yt-dlp"
