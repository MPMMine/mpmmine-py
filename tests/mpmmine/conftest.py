from pathlib import Path

import pytest

from mpmmine.dataset import MPMMine

# Define the backend path based on the requirement
BASE_PATH = Path("~/Projects/MPMMine/MPMMine").expanduser()
SEVEN_ZIP_ARCHIVE_PATH = BASE_PATH / "MPMMine-20260716-lzma2-mx5-mfb273-md128k-ms128k-slp-sse-ssp.7z"
ZIP_ARCHIVE_PATH = BASE_PATH / "MPMMine-20260716-tzip-mx9-m0Deflatefb258pass15.zip"
SQLITE_PLAIN_PATH = BASE_PATH / "MPMMine-plain.sqlite"
SQLITE_ZLIB_PATH = BASE_PATH / "MPMMine-zlib.sqlite"
SQLITE_LZMA_PATH = BASE_PATH / "MPMMine-lzma.sqlite"
SQLITE_LZMA_NOCHECK_PATH = BASE_PATH / "MPMMine-lzma-nocheck.sqlite"
SQLITE_LZMA_NOCHECK_0e_PATH = BASE_PATH / "MPMMine-lzma-nocheck-0e.sqlite"
SQLITE_LZMA_NOCHECK_1e_PATH = BASE_PATH / "MPMMine-lzma-nocheck-1e.sqlite"
SQLITE_ZSTD_PATH = BASE_PATH / "MPMMine-zstd.sqlite"
SQLITE_ZSTD8_DICT1024_PATH = BASE_PATH / "MPMMine-zstd8-dict1024.sqlite"
SQLITE_ZSTD8_DICT2048_PATH = BASE_PATH / "MPMMine-zstd8-dict2048.sqlite"
SQLITE_ZSTD10_DICT1024_PATH = BASE_PATH / "MPMMine-zstd10-dict1024.sqlite"
SQLITE_ZSTD10_DICT2048_PATH = BASE_PATH / "MPMMine-zstd10-dict2048.sqlite"
SQLITE_ZSTD12_DICT4096_PATH = BASE_PATH / "MPMMine-zstd12-dict4096.sqlite"
SQLITE_ZSTD14_DICT8192_PATH = BASE_PATH / "MPMMine-zstd14-dict8192.sqlite"
SQLITE_ZSTD14_DICTAVG_PATH = BASE_PATH / "MPMMine-zstd14-dictavg.sqlite"


@pytest.fixture(params=(paths := [
    BASE_PATH,
    SQLITE_PLAIN_PATH,
    SQLITE_ZSTD_PATH,
    SQLITE_ZSTD8_DICT1024_PATH,
    SQLITE_ZSTD8_DICT2048_PATH,
    SQLITE_ZSTD10_DICT1024_PATH,
    SQLITE_ZSTD10_DICT2048_PATH,
    SQLITE_ZSTD12_DICT4096_PATH,
    SQLITE_ZSTD14_DICT8192_PATH,
    SQLITE_ZSTD14_DICTAVG_PATH,
]), ids=[str(p) for p in paths], scope="package")
def mpmmine(request):
    """
    Fixture that initializes MPMMine with either FileBackend or ArchiveBackend.
    """

    return MPMMine(request.param)
