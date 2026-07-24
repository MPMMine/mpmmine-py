![image](https://github.com/MPMMine/MPMMine/raw/main/docs/assets/banner.png)

# mpmmine-py: A Python package for accessing the MPMMine dataset

The mpmmine library provides a Python API for the [MPMMine](https://github.com/MPMMine/MPMMine) benchmark dataset.
By leveraging native Python structures, it simplifies script development and facilitates seamless integration of the
dataset into larger Python projects.
MPMMine is a standardized dataset of benchmark problems for Mathematical
Programming model mining problems. For the details on the dataset, see the corresponding
[repository](https://github.com/MPMMine/MPMMine).

## Getting started

### Installation

To use MPMMine, you need two components: `mpmmine` package from `PyPI` and the actual
[dataset](https://github.com/MPMMine/MPMMine). To install `mpmmine` just run standard package installation, e.g., for
`pip`:

```shell
pip install mpmmine
```

Download the dataset from the [releases section](https://github.com/MPMMine/MPMMine/releases) of the official
repository. We recommend using the SQLite-backed version, as it offers lower latency than direct file-system access
while providing a highly-compressed representation.

### Usage

```python
from mpmmine.dataset import MPMMine
from pathlib import Path

mpmmine = MPMMine(Path("~/path/to/MPMMine-zstd.sqlite").expanduser())

print("Available benchmarks and their statistics: ")
for problem in mpmmine.problems:
    for model in problem.models:
        for instance in model.instances:
            print(f"{instance.full_id}: {len(list(instance.solutions))} solutions, and " +
                  f"{len(list(instance.non_solutions))} non-solutions")

print("A reference MiniZinc model for benchmark P016M001:")
model = mpmmine["MPMMine-P016M001"]
print(model.mzn)  # read MiniZinc code

print("Here's the problem description in natural text:")
print(model.get_description("D001").markdown)  # read Markdown

print("Here's another description read using full artifact id:")
print(mpmmine["MPMMine-P016M001D002"].markdown)  # read Markdown

print("Here's I001 instance (model parameters):")
print(model.get_instance("I001").dzn)  # read MiniZinc data 

print("Here's some solutions (variable values):")
for i, solution in enumerate(mpmmine["MPMMine-P016M001I001"].solutions):
    if i >= 3:
        break
    print(f"% {solution.full_id}:\n{solution.dzn}")

print("... and non-solutions:")
for i, non_solution in enumerate(mpmmine["MPMMine-P016M001I001"].non_solutions):
    if i >= 3:
        break
    print(f"% {non_solution.full_id}:\n{non_solution.dzn}")
```

## Backends

mpmmine-py comes with several backends enabling accessing the MPMMine dataset directly from the file system
(`FileBackend`), from an SQLite database (`SQLiteBackend`), and from ZIP (`ZipBackend`) and 7z (`SevenZipBackend`)
archives. The SQLite backend offers the smallest access latencies, about 5-10x less than the direct file system access,
approximately 25-35x less memory overhead than the ZIP and 7z backends, and approximately 5x less total file size than
for files stored directly on the disk. The below sections describe the details of each backend. Note that
`MPMMine` class constructor automatically picks the appropriate backend based on the path provided as the argument.

### File system backend

A backend that offers access to the MPMMine dataset laid directly on the file system. This backend is useful when
working with a clone of the MPMMine repository, and in environments where requirements of other backends are not
satisfied.

The artifact access times depend directly on the performance of the underlying file system and hard drive. The use
of this backend is discouraged on disks with high latencies, e.g., HDD drives, network drives, and on file systems
with known performance issues with handling large sets of small files.

On the other hand, this backend imposes negligible CPU and RAM overhead.

To initialize mpmmine-py with file system backend just provide path to the MPMMine directory:

```python
from mpmmine.dataset import MPMMine
from pathlib import Path

mpmmine = MPMMine(Path("~/path/to/MPMMine").expanduser())
```

### SQLite backend

A backend that offers access to the MPMMine dataset held within an SQLite database with optional compression of
file contents.

It offers O(log(n)) file access times, where n is the total number of files within the dataset. It is 5-10x faster
than the direct file system access using `FileBackend`, with a little memory overhead. The optional compression
involves either `zstd`, `zlib`, or `lzma` algorithms, where `zstd` is recommended due to the fastest decompression
and compression level better than offered by `zlib` and similar to `lzma`.

To run mpmmine-py with SQLite backend, initialize it with the path to the SQLite archive:

```python
from mpmmine.dataset import MPMMine
from pathlib import Path

mpmmine = MPMMine(Path("~/path/to/MPMMine-zstd.sqlite").expanduser())
```

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

The database schema is as follows:

```sqlite
CREATE TABLE IF NOT EXISTS config
(
    key   TEXT NOT NULL PRIMARY KEY,
    value TEXT -- NOTE: no STRICT option, so BLOB is accepted
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS files
(
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    parent  INTEGER REFERENCES files (id) ON DELETE CASCADE ON UPDATE CASCADE,
    name    TEXT NOT NULL,
    content BLOB
) STRICT
CREATE UNIQUE INDEX IF NOT EXISTS files_parent_name ON files (parent, name);
```

Where `config` table stores records necessary to configure the backend. Currently, it holds key`compressor` that attains
a value out of `zstd`, `zlib`, `lzma`, or `NULL` depending on the compression used, and key `zstd_dict` containing the
dictionary used for compression using `zstd`.
Table `files` consists of all files and directories within the MPMMine dataset. Column `id` is a unique primary key of
the database record; Column `parent` holds the reference to the parent directory, if any; Column `name` is the file
name; Column `content` holds file contents; it is `NULL` for directories. The `files_parent_name` index facilitates
O(log(n)) retrieval of files.

### ZIP backend

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

To initialize mpmmine-py with ZIP backend just provide path to the MPMMine ZIP archive:

```python
from mpmmine.dataset import MPMMine
from pathlib import Path

mpmmine = MPMMine(Path("~/path/to/MPMMine.zip").expanduser())
```

To build the ZIP archive, use any ZIP-capable compressor.

### 7z backend

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

To initialize mpmmine-py with 7z backend just provide path to the MPMMine 7z archive:

```python
from mpmmine.dataset import MPMMine
from pathlib import Path

mpmmine = MPMMine(Path("~/path/to/MPMMine.7z").expanduser())
```

To build the 7z archive, use any 7z-capable compressor.

## Development

### Building and publishing

To build a package run:

```shell
python3 -m build
```

To publish the package in PyPI run:

```shell
python3 -m twine upload --skip-existing dist/*
```

Note that it requires an access token to the PyPI repository to be configured first.
