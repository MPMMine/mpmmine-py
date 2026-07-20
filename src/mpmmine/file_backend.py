from pathlib import Path
from typing import override, Generator

from mpmmine.backend import Backend


class FileBackend(Backend):
    root: Path

    def __init__(self, root: Path):
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
