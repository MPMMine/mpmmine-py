from pathlib import Path
from typing import Generator


class Backend:
    """
    This class serves as an interface for all backends implementing access to the MPMMine dataset.
    """
    name: str

    def __init__(self, name: str):
        """
        Initializes the backend.
        :param name: The name of the current "file" in the MPMMine dataset.
        """
        self.name = name

    def read(self, filename: str | None = None) -> str:
        """
        Reads file content and returns it as a UTF-8 string.
        :param filename: if None than it reads file `self.name`; otherwise it reads the `filename` within the `self.name` directory.
        :raises FileNotFoundError: if `filename` does not exist.
        """
        raise NotImplementedError

    def sub(self, filename: str) -> Backend:
        """
        Opens subdirectory of the given file name and returns a new view on it.
        :param filename: Directory name.
        :return:
        :raises FileNotFoundError: If the given file does not exist.
        """
        raise NotImplementedError

    def glob(self, pattern: str) -> Generator[Backend, None, None]:
        """
        Looks for files matching the given glob pattern.
        See [https://en.wikipedia.org/wiki/Glob_(programming)] for the details of glob pattern.
        :param pattern:
        :return: The generator of all files matching the given glob pattern.
        """
        raise NotImplementedError

    @staticmethod
    def matches(path: Path) -> bool:
        """
        Checks if this backend handles the file/directory represented by the given path.
        :param path: Path to the MPMMine dataset.
        :return: True if this backend handles the file/directory represented by the given path; False otherwise.
        """
        raise NotImplementedError
