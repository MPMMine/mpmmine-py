import argparse
import compression
import logging
import lzma
import re
import sqlite3
import sys
import zlib
from _lzma import CHECK_NONE
from _zstd import ZstdDict
from pathlib import Path
from typing import override, Optional, Generator, Callable, Literal

import colorlog

from mpmmine.backend import Backend


class SQLiteBackend(Backend):
    """
    A backend that offers access to the MPMMine dataset held within an SQLite database with optional compression of
    file contents.

    It offers O(log(n)) file access times, where n is the total number of files within the dataset. It is 5-10x faster
    than the direct file system access using `FileBackend`, with a little memory overhead. The optional compression
    involves either `zstd`, `zlib`, or `lzma` algorithms, where `zstd` is recommended due to the fastest decompression
    and compression level better than offered by `zlib` and similar to `lzma`.

    To build an SQLite database from a clone of MPMMine repository run
    ```shell
    python3 -m mpmmine.sqlite_backend -t -c zstd /path/to/MPMMine_dataset MPMMine-zstd.sqlite
    ```
    where `-t` stands for truncate (overwrite) of an existing database; without `-t` the contents will be appended;
    `-c` enables compression, and the following keyword picks the algorithm out of `zstd`, `zlib`, or `lzma`.

    For `zlib` and `lzma`, it compresses independently each file. This is equivalent to a non-solid (i.e., regular)
    archive. For `zstd`, it first trains a dictionary of common patterns on a (large) sample of all files and stores
    the trained dictionary in the `config` table at key `zstd_dict`. Next, it compresses independently each file, seeding
    the compressor with this dictionary. The decompression requires seeding the decompressor with this dictionary too.

    """

    _conn: sqlite3.Connection = None
    _parent: Optional[int] = None
    _parent_path: Path
    _decompressor: Callable

    # see _create_schema() for schema

    def __init__(self,
                 db_file_or_connection: Path | sqlite3.Connection,
                 _parent: Optional[int] = None,
                 _parent_path: Path = Path(""),
                 _decompressor: Optional[Callable] = None
                 ) -> None:
        """
        Initializes new instance of SQLiteBackend.
        :param db_file_or_connection: Either a path to the database file, or an existing SQLite3 connection.
        :param _parent: Primary key of the parent directory within the archive.
        :param _parent_path: Path to the parent directory within the archive.
        :param _decompressor: Decompressor for file contents.
        """
        if isinstance(db_file_or_connection, sqlite3.Connection):
            self._conn = db_file_or_connection
        else:
            self._conn = SQLiteBackend._connect(db_file_or_connection)

        super().__init__(_parent_path.name)
        self._parent = _parent
        self._parent_path = _parent_path
        self._exists()

        if _decompressor is not None:
            self._decompressor = _decompressor
        else:
            compressor = self._conn.execute("SELECT value FROM config WHERE key='compressor'").fetchone()[0]
            match compressor:
                case "zlib":
                    self._decompressor = lambda x: zlib.decompress(x)
                case "lzma":
                    self._decompressor = lambda x: lzma.decompress(x)
                case "zstd":
                    dict_bytes = self._conn.execute("SELECT value FROM config WHERE key='zstd_dict'").fetchone()[0]
                    zstd_dict = ZstdDict(dict_bytes)
                    self._decompressor = lambda x: compression.zstd.decompress(x, zstd_dict=zstd_dict)
                case _:
                    self._decompressor = lambda x: x

    @override
    def sub(self, path: str) -> Backend:
        id, name = self._exists(path)
        return SQLiteBackend(self._conn, id, self._parent_path / name, self._decompressor)

    def _exists(self, name: Optional[str] = None) -> tuple[int | None, str]:
        if self._parent is None and name is None:
            return None, ""

        if name is None:
            cursor = self._conn.execute(
                "SELECT id, name FROM files WHERE id=:parent LIMIT 1",
                {"parent": self._parent}
            )
        else:
            cursor = self._conn.execute(
                "SELECT id, name FROM files WHERE parent IS :parent AND name=:name LIMIT 1",
                {"parent": self._parent, "name": name}
            )
        row = cursor.fetchone()
        if not bool(row):
            raise FileNotFoundError(f"Path {self._parent_path / (name if name else "")} does not exist.")
        return row[0], row[1]

    @override
    def read(self, filename: str | None = None) -> str:
        if filename is None:
            cursor = self._conn.execute(
                "SELECT content FROM files WHERE id = :parent LIMIT 1",
                {"parent": self._parent}
            )
        else:
            cursor = self._conn.execute(
                "SELECT content FROM files WHERE parent IS :parent AND name = :name LIMIT 1",
                {"parent": self._parent, "name": filename}
            )

        content = cursor.fetchone()
        if content is None:
            raise FileNotFoundError(f"Path {self._parent_path / (filename if filename else "")} does not exist.")
        return self._decompressor(content[0]).decode("utf-8")

    @override
    def glob(self, pattern: str) -> Generator[Backend, None, None]:
        cursor = self._conn.execute(
            "SELECT id, name FROM files WHERE parent IS :parent and name GLOB :pattern",
            {"parent": self._parent, "pattern": pattern}
        )

        for row in cursor:
            yield SQLiteBackend(self._conn, row[0], self._parent_path / row[1], self._decompressor)

    def __del__(self):
        if self._conn is not None and sys.getrefcount(self._conn) <= 2:
            self._conn.close()

    @override
    @staticmethod
    def matches(path: Path) -> bool:
        return path.is_file() and path.suffix == ".sqlite"

    @staticmethod
    def _create_schema(_conn: sqlite3.Connection, index: bool = False):
        _conn.execute("""
                      CREATE TABLE IF NOT EXISTS config
                      (
                          key   TEXT NOT NULL PRIMARY KEY,
                          value TEXT -- NOTE: no STRICT option, so BLOB is accepted
                      ) WITHOUT ROWID
                      """)
        _conn.execute("""
                      CREATE TABLE IF NOT EXISTS files
                      (
                          id      INTEGER PRIMARY KEY AUTOINCREMENT,
                          parent INTEGER REFERENCES files (id) ON DELETE CASCADE ON UPDATE CASCADE,
                          name    TEXT NOT NULL,
                          content BLOB
                      ) STRICT
                      """)
        if index:
            _conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS files_parent_name ON files(parent, name)")

    _valid_dirs = re.compile(
        r"^(?:problems|P\d{3}.*|models|M\d{3}.*|instances|I\d{3}.*|descriptions|solutions|non solutions|docs)$")
    _valid_files = re.compile(r"^(?:[^.]+\.(?:dzn|mzn|(?:\w{1,3}\.)?md|json)|LICENSE|VERSION|ACKNOWLEDGMENTS.md)$")

    @staticmethod
    def _connect(file: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(file)
        conn.execute("PRAGMA synchronous = 0")
        conn.execute("PRAGMA foreign_keys = 1")
        conn.execute("PRAGMA journal_mode = TRUNCATE")
        conn.execute("PRAGMA page_size = %d" % (1 << 16))
        conn.execute("PRAGMA temp_store = MEMORY")
        conn.autocommit = False
        return conn

    @staticmethod
    def _add_file(
            conn: sqlite3.Connection,
            file: Path,
            parent_id: Optional[int] = None,
            compressor: Callable = lambda x: x,
            override_content: Optional[bytes] = None,
    ) -> int:
        logging.debug(f"Adding file {file}...")

        if override_content is not None:
            content = override_content
        elif file.is_file():
            content = compressor(file.read_bytes())
        else:
            content = None

        cursor = conn.execute(
            "INSERT INTO files(parent, name, content) VALUES(:parent, :name, :content) RETURNING id",
            {
                "parent": parent_id,
                "name": file.name,
                "content": content
            })
        return cursor.fetchone()[0]  # primary key

    @staticmethod
    def _train_zstd_dict(files: list[Path], dict_size: int = 512 * 1024) -> ZstdDict:
        only_files = [f for f in files if f.is_file() and (s := f.stat().st_size) >= 8 and s <= 16384]
        sum_size = sum(f.stat().st_size for f in only_files)
        modulo = max(int((sum_size / dict_size) / 128), 1)  # sample should be 100x larger than dict_size
        sample = [f.read_bytes() for i, f in enumerate(only_files) if i % modulo == 0]
        return compression.zstd.train_dict(sample, dict_size)

    @staticmethod
    def _get_file_list(path: Path) -> list[Path]:
        out = []
        for dirpath, dirnames, filenames in path.walk(top_down=True, follow_symlinks=False):
            for dir in sorted(dirnames):  # copy dirnames, as we modify the original collection below
                if not SQLiteBackend._valid_dirs.fullmatch(dir):
                    logging.warning(f"Skipping {dirpath / dir}...")
                    dirnames.remove(dir)
                    continue
                out.append(dirpath / dir)

            files_to_process = sorted(f for f in filenames if SQLiteBackend._valid_files.fullmatch(f))
            for file in files_to_process:
                out.append(dirpath / file)
        return out

    @staticmethod
    def load(
            mpmmine_path: Path,
            sqlite_path: Path,
            truncate: bool = False,
            compress: Literal["zlib", "lzma", "zstd"] | None = None,
    ):
        files = SQLiteBackend._get_file_list(mpmmine_path)

        if truncate:
            logging.warning(f"Deleting {sqlite_path} if exists...")
            sqlite_path.unlink(missing_ok=True)

        with SQLiteBackend._connect(sqlite_path) as conn:
            SQLiteBackend._create_schema(conn, index=False)

            if compress is not None:
                logging.info(f"Configuring compressor {compress}...")

            conn.execute(
                "INSERT OR REPLACE INTO config (key, value) VALUES (:key, :value)",
                {"key": "compressor", "value": compress}
            )

            match compress:
                case "zlib":
                    compressor = lambda x: zlib.compress(x, level=9)
                case "lzma":
                    compressor = lambda x: lzma.compress(x, check=CHECK_NONE)
                case "zstd":
                    zstd_dict = SQLiteBackend._train_zstd_dict(files)
                    conn.execute(
                        "INSERT OR REPLACE INTO config (key, value) VALUES (:key, :value)",
                        {"key": "zstd_dict", "value": zstd_dict.dict_content}
                    )
                    compressor = lambda x: compression.zstd.compress(x, level=22, zstd_dict=zstd_dict)
                case _:
                    compressor = lambda x: x

            logging.info("Adding files...")
            parents: dict[str, int] = {}  # key: dir name, value: int primary key
            for path in files:
                logging.debug(f"Adding {path}...")

                parent_id = parents.get(str(path.parent), None)
                if path.is_dir():
                    parents[str(path)] = SQLiteBackend._add_file(conn, path, parent_id, compressor)
                elif path.is_file():
                    SQLiteBackend._add_file(conn, path, parent_id, compressor)

            logging.info("Indexing...")
            SQLiteBackend._create_schema(conn, index=True)
            conn.execute("ANALYZE")
            conn.commit()

            logging.info("Done.")


def _configure_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(colorlog.ColoredFormatter(log_colors={
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'bold_red',
    }))
    logging.basicConfig(level=logging.INFO, handlers=[handler])


if __name__ == '__main__':
    _configure_logging()

    parser = argparse.ArgumentParser(
        prog='SQLiteBackend',
        description='Loads MPMMine files into SQLite database.'
    )
    parser.add_argument("mpmmine_path", type=Path, help="Path to MPMMine repository.")
    parser.add_argument("sqlite_path", type=Path, help="Path to SQLite database to fill in.")
    parser.add_argument("-t", "--truncate", help="Truncate SQLite database if exists", action="store_true")
    parser.add_argument("-c", "--compress", help="Compress data", choices=["zstd", "zlib", "lzma"])

    args = parser.parse_args()
    SQLiteBackend.load(
        mpmmine_path=args.mpmmine_path.expanduser().resolve(),
        sqlite_path=args.sqlite_path.expanduser().resolve(),
        truncate=args.truncate,
        compress=args.compress
    )
