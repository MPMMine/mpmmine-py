from pathlib import Path
from typing import Generator


class Backend:
    name: str

    def __init__(self, name: str):
        self.name = name

    def read(self, filename: str | None = None) -> str:
        """Reads file content and returns it as a UTF-8 string."""
        raise NotImplementedError

    def sub(self, filename: str) -> Backend:
        raise NotImplementedError

    def glob(self, pattern: str) -> Generator[Backend, None, None]:
        raise NotImplementedError

    @staticmethod
    def matches(path: Path) -> bool:
        raise NotImplementedError
