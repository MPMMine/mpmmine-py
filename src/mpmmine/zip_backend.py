import zipfile
from pathlib import Path
from typing import Optional, override, Generator

from mpmmine.backend import Backend


class ZipBackend(Backend):
    """
    A backend that offers access to the MPMMine dataset held within a ZIP archive.

    Initially, it reads the archive index to extract and cache the list of files. This typically lasts less than 30
    seconds and causes constant memory overhead of a few gigabytes. Then, lookup, file structure traversals, decompression
    and extraction are performed on the fly.

    The performance of this backend depends on the parameters of the ZIP archive, i.e., on the compression algorithm
    and its parameters. In preliminary experiments, the Deflate and ZSTD algorithms offer the least decompression
    overhead. Deflate compression is recommended, as it is the most widely supported compression method for ZIP. Setting
    it with maximum compression level of 9, fast bytes of 258, and 15 passes leads to the best compression level, with a
    little increase of the decompression overhead, compared to the defaults.

    Note that the set of supported compression algorithms is limited by the `zipfile` package. In particular, Deflate64
    is not supported.

    Overall, this backend suffers from significant latencies and memory overhead, offering in exchange a decent
    compression level.
    """

    def __init__(
            self,
            archive_path: Optional[Path] = None,
            _inner_path: str = "",
            _path: Optional[zipfile.Path] = None
    ):
        if _path:
            self._root = _path
        elif archive_path:
            self._root = zipfile.Path(zipfile.ZipFile(archive_path), at=_inner_path)
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
