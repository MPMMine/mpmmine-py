from io import TextIOWrapper
from pathlib import Path
from typing import Generator


class FileBackend:
    root: Path
    name: str

    def __init__(self, root: Path):
        if not root.exists():
            raise FileNotFoundError(f"Path {root} does not exist!")

        self.root = root
        self.name = root.name

    def open(self, filename: str | None = None) -> TextIOWrapper:
        """Opens file stream with the given path. Use the result of this function in the
        `with` statement."""
        if filename is None:
            return open(self.root, "r", encoding="utf-8")
        return open(self.root / filename, "r", encoding="utf-8")

    def sub(self, filename: str) -> FileBackend:
        return FileBackend(self.root / filename)

    def glob(self, pattern: str) -> Generator[FileBackend, None, None]:
        return (FileBackend(p) for p in self.root.glob(pattern))
