import argparse
import compression
import functools
import logging
import lzma
import re
import sqlite3
import sys
import zlib
from _zstd import ZstdDict
from pathlib import Path
from typing import override, Optional, Generator, Callable, Literal

import colorlog
from py7zr import CHECK_NONE

from mpmmine.backend import Backend


class SQLiteBackend(Backend):
    _conn: sqlite3.Connection = None
    _parent: Optional[int] = None
    _parent_path: Path
    _decompressor: Callable

    # see _create_schema() for schema

    def __init__(self,
                 file: Path | sqlite3.Connection,
                 _parent: Optional[int] = None,
                 _parent_path: Path = Path(""),
                 _decompressor: Optional[Callable] = None
                 ) -> None:
        if isinstance(file, sqlite3.Connection):
            self._conn = file
        else:
            self._conn = SQLiteBackend._connect(file)

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
                    self._decompressor = lambda x, d: zlib.decompress(x)
                case "lzma":
                    self._decompressor = lambda x, d: lzma.decompress(x)
                case "zstd":
                    self._decompressor = lambda x, d: compression.zstd.decompress(x, zstd_dict=d)
                case _:
                    self._decompressor = lambda x, d: x

    @override
    def sub(self, path: str) -> Backend:
        id, name = self._exists(path)
        return SQLiteBackend(self._conn, id, self._parent_path / name)

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

    @staticmethod
    @functools.lru_cache(maxsize=2048)
    def _get_zstd_dict(_bytes: Optional[bytes]) -> Optional[ZstdDict]:
        if _bytes is None:
            return None
        return ZstdDict(_bytes)

    @override
    def read(self, filename: str | None = None) -> str:
        if filename is None:
            cursor = self._conn.execute(
                """SELECT f1.content, f2.content AS zstd_dict
                   FROM files f1
                            LEFT JOIN files f2 ON f1.parent = f2.parent AND f2.name = '.zstd-dict'
                   WHERE f1.id = :parent
                   LIMIT 1""",
                {"parent": self._parent}
            )
        else:
            cursor = self._conn.execute(
                """SELECT f1.content, f2.content AS zstd_dict
                   FROM files f1
                            LEFT JOIN files f2 ON f1.parent = f2.parent AND f2.name = '.zstd-dict'
                   WHERE f1.parent IS :parent
                     AND f1.name = :name
                   LIMIT 1""",
                {"parent": self._parent, "name": filename}
            )

        content = cursor.fetchone()
        if content is None:
            raise FileNotFoundError(f"Path {self._parent_path / (filename if filename else "")} does not exist.")
        return self._decompressor(content[0], SQLiteBackend._get_zstd_dict(content[1])).decode("utf-8")

    @override
    def glob(self, pattern: str) -> Generator[Backend, None, None]:
        cursor = self._conn.execute(
            "SELECT id, name FROM files WHERE parent IS :parent and name GLOB :pattern",
            {"parent": self._parent, "pattern": pattern}
        )

        for row in cursor:
            yield SQLiteBackend(self._conn, row[0], self._parent_path / row[1])

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
                          value TEXT
                      ) STRICT
                      """)
        _conn.execute("""
                      CREATE TABLE IF NOT EXISTS files
                      (
                          id      INTEGER PRIMARY KEY AUTOINCREMENT,
                          parent  INTEGER REFERENCES files (id) ON DELETE SET NULL ON UPDATE CASCADE,
                          name    TEXT NOT NULL,
                          content BLOB
                      ) STRICT
                      """)
        if index:
            _conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS files_parent_name ON files(parent, name)")

    _valid_dirs = re.compile(
        r"^(?:problems|P\d{3}.*|models|M\d{3}.*|instances|I\d{3}.*|descriptions|solutions|non solutions|docs)$")
    _valid_files = re.compile(r"^(?:[^.]+\.(?:dzn|mzn|(?:\w{1,3}\.)?md|json)|LICENSE)$")

    @staticmethod
    def _connect(file: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(file)
        conn.execute("PRAGMA synchronous = 0")
        conn.execute("PRAGMA foreign_keys = 1")
        conn.execute("PRAGMA journal_mode = TRUNCATE")
        # conn.execute("PRAGMA page_size = %d" % (1 << 14))
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
    def load(
            mpmmine_path: Path,
            sqlite_path: Path,
            truncate: bool = False,
            compress: Literal["zlib", "lzma", "zstd"] | None = None,
    ):
        if truncate:
            logging.warning(f"Deleting {sqlite_path}...")
            sqlite_path.unlink(missing_ok=True)

        with SQLiteBackend._connect(sqlite_path) as conn:
            SQLiteBackend._create_schema(conn, index=False)

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
                    compressor = lambda x: compression.zstd.compress(x, level=8)
                case _:
                    compressor = lambda x: x

            parents: dict[str, int] = {}  # key: dir name, value: int primary key

            for dirpath, dirnames, filenames in mpmmine_path.walk(top_down=True, follow_symlinks=False):
                logging.info(f"Processing {dirpath}...")
                parent_id = parents.get(str(dirpath), None)
                for dir in sorted(dirnames):  # copy dirnames, as we modify the original collection below
                    if not SQLiteBackend._valid_dirs.fullmatch(dir):
                        logging.warning(f"Skipping {dirpath / dir}...")
                        dirnames.remove(dir)
                        continue
                    path = dirpath / dir
                    parents[str(path)] = SQLiteBackend._add_file(conn, path, parent_id, compressor)

                files_to_process = sorted(f for f in filenames if SQLiteBackend._valid_files.fullmatch(f))
                zstd_dict = None
                actual_compressor = compressor
                if compress == "zstd":
                    train_data = [(dirpath / file).read_bytes() for file in files_to_process]
                    train_size = sum(len(d) for d in train_data)
                    if len(train_data) >= 10 and train_size >= 5 * 512:
                        # the average file size bound to the range of 512B..16KB
                        dict_size = min(max(train_size // len(train_data), 512), 16384)
                        zstd_dict = compression.zstd.train_dict(train_data, dict_size)
                        SQLiteBackend._add_file(
                            conn,
                            dirpath / ".zstd-dict",
                            parent_id,
                            lambda x: x,
                            override_content=zstd_dict.dict_content
                        )
                        actual_compressor = lambda x: compression.zstd.compress(x, level=14, zstd_dict=zstd_dict)

                for file in files_to_process:
                    path = dirpath / file
                    SQLiteBackend._add_file(conn, path, parent_id, actual_compressor)

            SQLiteBackend._create_schema(conn, index=True)
            conn.execute("PRAGMA optimize")
            conn.commit()


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
