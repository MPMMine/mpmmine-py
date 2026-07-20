import bisect
import fnmatch
import io
from pathlib import Path
from typing import Union, Optional, override, List, Generator

from py7zr import Py7zIO, WriterFactory, SevenZipFile, py7zr

from mpmmine.backend import Backend


class MemoryIO(Py7zIO):
    """In-memory IO stream for py7zr extraction."""

    def __init__(self):
        self.buffer = io.BytesIO()
        self._size = 0

    def write(self, data: Union[bytes, bytearray]) -> int:
        length = self.buffer.write(data)
        self._size += length
        return length

    def read(self, size: Optional[int] = None) -> bytes:
        return self.buffer.read(size)

    def seek(self, offset: int, whence: int = 0) -> int:
        return self.buffer.seek(offset, whence)

    def flush(self) -> None:
        self.buffer.flush()

    def size(self) -> int:
        return self._size

    def getvalue(self) -> bytes:
        return self.buffer.getvalue()


class MemoryFactory(WriterFactory):
    """Factory creating MemoryIO instances for in-memory extraction."""

    def __init__(self):
        self.files: dict[str, MemoryIO] = {}

    @override
    def create(self, filename: str) -> Py7zIO:
        io_obj = MemoryIO()
        self.files[filename] = io_obj
        return io_obj


class SevenZipBackend(Backend):
    archive_path: Path
    _inner_path: str
    _archive: SevenZipFile
    _entries: List[str]

    def __init__(
            self,
            archive_path: Path,
            inner_path: str = "",
            _shared_archive: Optional[SevenZipFile] = None,
            _shared_entries: Optional[List[str]] = None
    ):
        if not archive_path.exists():
            raise FileNotFoundError(f"Path {archive_path} does not exist.")

        self.archive_path = archive_path
        self._inner_path = inner_path.strip("/")
        name = self._inner_path.split("/")[-1] if self._inner_path else archive_path.name
        super().__init__(name)

        if _shared_archive is not None and _shared_entries is not None:
            self._archive = _shared_archive
            self._entries = _shared_entries
        else:
            self._archive = SevenZipFile(str(self.archive_path), mode='r')
            self._entries = [
                name for name in self._archive.getnames()
                if "/." not in name and not name.startswith(".")
            ]
            self._entries.sort()

        if self._inner_path:
            self._verify_path(self._inner_path, exact_match_only=False)

    def _verify_path(self, path: str, exact_match_only: bool) -> None:
        """Verifies if path exists as an exact match or a directory prefix."""
        idx = bisect.bisect_left(self._entries, path)

        is_exact = idx < len(self._entries) and self._entries[idx] == path
        is_dir_prefix = (not exact_match_only) and idx < len(self._entries) and self._entries[idx].startswith(
            path + "/")

        if not (is_exact or is_dir_prefix):
            raise FileNotFoundError(f"Path '{path}' not found in archive.")

    def _get_full_path(self, filename: Optional[str]) -> str:
        if not filename:
            return self._inner_path
        return f"{self._inner_path}/{filename}".strip("/")

    @override
    def read(self, filename: Optional[str] = None) -> str:
        """Reads file content to memory and returns it as a UTF-8 string."""
        target_path = self._get_full_path(filename)

        self._verify_path(target_path, exact_match_only=True)

        try:
            self._archive.reset()
            factory = MemoryFactory()

            # Extract target file specifically into the MemoryFactory instance
            self._archive.extract(targets=[target_path], factory=factory)

            if target_path not in factory.files:
                raise FileNotFoundError(f"File {target_path} could not be extracted.")

            return factory.files[target_path].getvalue().decode("utf-8")
        except Exception as e:
            raise IOError(f"Failed to read file {target_path}: {e}")

    @override
    def sub(self, filename: str) -> 'SevenZipBackend':
        new_path = self._get_full_path(filename)
        return SevenZipBackend(
            self.archive_path,
            inner_path=new_path,
            _shared_archive=self._archive,
            _shared_entries=self._entries
        )

    @override
    def glob(self, pattern: str) -> Generator['SevenZipBackend', None, None]:
        search_pattern = self._get_full_path(pattern)

        prefix_parts = search_pattern.split('*')[0].split('?')[0].rsplit('/', 1)
        prefix = prefix_parts[0] + '/' if len(prefix_parts) > 1 else ''
        prefix = prefix.lstrip("/")

        start_idx = bisect.bisect_left(self._entries, prefix)
        end_idx = bisect.bisect_left(self._entries, prefix + "~", lo=start_idx)

        for name in self._entries[start_idx:end_idx]:
            if "/" in name[len(prefix):-1]:
                continue
            if fnmatch.fnmatch(name, search_pattern):
                yield SevenZipBackend(
                    self.archive_path,
                    inner_path=name,
                    _shared_archive=self._archive,
                    _shared_entries=self._entries
                )

    @override
    @staticmethod
    def matches(path: Path) -> bool:
        return path.is_file() and py7zr.is_7zfile(path)
