import bisect
import fnmatch
import io
from pathlib import Path
from typing import Union, Optional, override, List, Generator

from py7zr import Py7zIO, WriterFactory, SevenZipFile, py7zr

from mpmmine.backend import Backend


class _MemoryIO(Py7zIO):
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


class _MemoryFactory(WriterFactory):
    """Factory creating MemoryIO instances for in-memory extraction."""

    def __init__(self):
        self.files: dict[str, _MemoryIO] = {}

    @override
    def create(self, filename: str) -> Py7zIO:
        io_obj = _MemoryIO()
        self.files[filename] = io_obj
        return io_obj


class SevenZipBackend(Backend):
    """
    A backend that offers access to the MPMMine dataset held within a 7z archive.

    Initially, it reads the archive index to extract and cache the list of files. This typically lasts 30-60 seconds
    and causes constant memory overhead of a few gigabytes. Then, lookup, file structure traversals, decompression
    and extraction are performed on the fly.

    The implementation relies on the optional `py7zr` package, which is not installed by default with mpmmine-py.

    The performance of this backend depends on the parameters of the 7z archive. It is recommended to use this backend
    with non-solid (i.e., regular) archives. The use with a solid archive is discouraged, as free file access requires
    decompressing the entire block containing a file. For large blocks of several gigabytes, typically employed by solid
    archives, this imposes the overhead of the decompression of gigabytes of data in order to read just a few kilobytes
    of a specific file. Even for small blocks of, e.g., 1MB, it still turns out to be inefficient.

    The performance also relies on the compression algorithm and its parameters. In preliminary experiments, the LZMA2
    algorithm offers the least decompression overhead.

    Overall, this backend suffers from the largest latencies and memory overhead, offering in exchange the best
    compression level and so the smallest dataset archive.
    """
    archive_path: Path
    _inner_path: str
    _archive: SevenZipFile
    _entries: List[str]

    def __init__(
            self,
            archive_path: Path,
            _inner_path: str = "",
            _shared_archive: Optional[SevenZipFile] = None,
            _shared_entries: Optional[List[str]] = None
    ):
        if not archive_path.exists():
            raise FileNotFoundError(f"Path {archive_path} does not exist.")

        self.archive_path = archive_path
        self._inner_path = _inner_path.strip("/")
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
        target_path = self._get_full_path(filename)

        self._verify_path(target_path, exact_match_only=True)

        try:
            self._archive.reset()
            factory = _MemoryFactory()

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
            _inner_path=new_path,
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
                    _inner_path=name,
                    _shared_archive=self._archive,
                    _shared_entries=self._entries
                )

    @override
    @staticmethod
    def matches(path: Path) -> bool:
        return path.is_file() and py7zr.is_7zfile(path)
