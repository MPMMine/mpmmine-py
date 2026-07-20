import zipfile
from pathlib import Path
from typing import Optional, override, Generator

from mpmmine.backend import Backend


class ZipBackend(Backend):
    def __init__(self, archive_path: Optional[Path] = None, inner_path: str = "", _path: Optional[zipfile.Path] = None):
        if _path:
            self._root = _path
        elif archive_path:
            self._root = zipfile.Path(zipfile.ZipFile(archive_path), at=inner_path)
        else:
            raise ValueError("Either archive_path or _path must be provided.")

        # noinspection PyTypeChecker
        super().__init__(self._root.name or self._root.root.filename)

    @override
    def read(self, filename: Optional[str] = None) -> str:
        """Reads file content from the archive."""
        target = self._root.joinpath(filename) if filename else self._root

        return target.read_text(encoding="utf-8")

    @override
    def sub(self, filename: str) -> ZipBackend:
        return ZipBackend(_path=self._root.joinpath(filename))

    @override
    def glob(self, pattern: str) -> Generator[ZipBackend, None, None]:
        for path in self._root.glob(pattern):
            yield ZipBackend(_path=path)

    @override
    @staticmethod
    def matches(path: Path) -> bool:
        return path.is_file() and zipfile.is_zipfile(path)
