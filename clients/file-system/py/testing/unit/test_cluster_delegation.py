"""Unit tests for ``Cluster`` delegation to a stub engine."""

from __future__ import annotations

from pathlib import Path

from returns.result import Success

from file_system.cluster import Cluster
from file_system.core.types import BytesResult, TextResult, UnitResult
from file_system.domain.enums import TextEncoding
from file_system.io.engine import FileEngine


class _RecordingEngine(FileEngine):
    """Minimal engine that records calls without touching the filesystem."""

    def __init__(self) -> None:
        self.read_bytes_paths: list[Path] = []
        self.write_bytes_calls: list[tuple[Path, bytes]] = []
        self.read_text_calls: list[tuple[Path, TextEncoding]] = []
        self.write_text_calls: list[tuple[Path, str, TextEncoding]] = []

    def read_bytes(self, path: Path) -> BytesResult:
        self.read_bytes_paths.append(path)
        return Success(b"stub-bytes")

    def write_bytes(self, path: Path, data: bytes) -> UnitResult:
        self.write_bytes_calls.append((path, data))
        return Success(None)

    def read_text(self, path: Path, encoding: TextEncoding) -> TextResult:
        self.read_text_calls.append((path, encoding))
        return Success("stub-text")

    def write_text(self, path: Path, text: str, encoding: TextEncoding) -> UnitResult:
        self.write_text_calls.append((path, text, encoding))
        return Success(None)


def test_cluster_delegates_read_bytes_to_engine() -> None:
    engine = _RecordingEngine()
    cluster = Cluster(engine=engine)
    outcome = cluster.read_bytes("data/file.bin")
    assert isinstance(outcome, Success)
    assert outcome.unwrap() == b"stub-bytes"
    assert engine.read_bytes_paths == [Path("data/file.bin")]


def test_cluster_delegates_write_bytes_to_engine() -> None:
    engine = _RecordingEngine()
    cluster = Cluster(engine=engine)
    outcome = cluster.write_bytes("out.bin", b"\x01")
    assert isinstance(outcome, Success)
    assert engine.write_bytes_calls == [(Path("out.bin"), b"\x01")]


def test_cluster_delegates_text_operations_to_engine() -> None:
    engine = _RecordingEngine()
    cluster = Cluster(engine=engine)
    assert isinstance(cluster.read_text("in.txt", TextEncoding.LATIN1), Success)
    assert isinstance(cluster.write_text("out.txt", "hi", TextEncoding.UTF16), Success)
    assert engine.read_text_calls == [(Path("in.txt"), TextEncoding.LATIN1)]
    assert engine.write_text_calls == [(Path("out.txt"), "hi", TextEncoding.UTF16)]
