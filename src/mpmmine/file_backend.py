from pathlib import Path
from typing import override, Generator

from mpmmine.backend import Backend


class FileBackend(Backend):
    """
    A backend that offers access to the MPMMine dataset laid directly on the file system. This backend is useful when
    working with a clone of the MPMMine repository, and in environments where requirements of other backends are not
    satisfied.

    The artifact access times depend directly on the performance of the underlying file system and hard drive. The use
    of this backend is discouraged on disks with high latencies, e.g., HDD drives, network drives, and on file systems
    with known performance issues with handling large sets of small files.

    On the other hand, this backend imposes negligible CPU and RAM overhead.
    """
    root: Path

    def __init__(self, root: Path):
        """
        Initializes the file system backend.
        :param root: The path to the root directory of the MPMMine dataset.
        """
        if not root.exists():
            raise FileNotFoundError(f"Path {root} does not exist!")

        super().__init__(root.name)
        self.root = root

    @override
    def read(self, filename: str | None = None) -> str:
        path = self.root
        if filename is not None:
            path = path / filename
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    @override
    def sub(self, filename: str) -> FileBackend:
        return FileBackend(self.root / filename)

    @override
    def glob(self, pattern: str) -> Generator[FileBackend, None, None]:
        return (FileBackend(p) for p in self.root.glob(pattern))

    @override
    @staticmethod
    def matches(path: Path) -> bool:
        return path.is_dir() and (path / "problems").exists()
