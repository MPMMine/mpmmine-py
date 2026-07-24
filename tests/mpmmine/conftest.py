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
SQLITE_ZSTD_PATH = BASE_PATH / "MPMMine-zstd-v0.1.0.20260722-beta-level9-topleveldict.sqlite"


@pytest.fixture(params=(paths := [
    BASE_PATH,
    SQLITE_PLAIN_PATH,
    SQLITE_ZSTD_PATH,
]), ids=[str(p) for p in paths], scope="package")
def mpmmine(request):
    """
    Fixture that initializes MPMMine with either FileBackend or ArchiveBackend.
    """

    return MPMMine(request.param)
