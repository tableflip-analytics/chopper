# CHOPPER
Create Hoards Of Punier Pieces, Evading RAM.

CHOPPER allows you to split large CSVs into multiple smaller CSVs in several different ways.

## Features
1. Limiting each output file to a certain number of records (`--rows`).
2. Creating N output files of approximately equal size (`--equal`).
3. Breaking up the input file based on column values in one or more columns (`--columns`).
4. Various combinations of the above (note: #1 and #2 cannot be used together).

In addition to the features described above, CHOPPER can also combine multiple like files together prior to splitting. It can also randomize the input file (or combined file) (`--shuffles`).

## Compatibility
Tested with Python 3.11, but may work with other versions.

## Installation
Just clone the repo and get started. CHOPPER has no dependencies outside the standard Python library.

## Usage

```
usage: chopper.py [-h] -i [INPUT_PATHS ...] -o OUTPUT_DIRECTORY [-x EXTENSION]
[-e ENCODING] [-d DELIMITER] [-p PREFIX] [-s SHUFFLES] [-c [COLUMNS ...]]
[-r ROWS | -q EQUAL]

Get into the CHOPPER so you can Create Hoards Of Punier Pieces, Evading RAM.Evading RAM.

options:
  -h, --help
show this help message and exit

  -i [INPUT_PATHS ...], --input_paths [INPUT_PATHS ...]
Input file or directory. If a directory is specified, CHOPPER will treat all files in
the directory (including subdirectories) as a single file for splitting and shuffling
purposes.

  -o OUTPUT_DIRECTORY, --output_directory OUTPUT_DIRECTORY
An empty/nonexistent folder is highly recommended, as CHOPPER may overwrite files.

  -x EXTENSION, --extension EXTENSION
File extension to search for if any input_paths are directories. Specifying the
extension is highly recommended to avoid accidental inclusion of files.

  -e ENCODING, --encoding ENCODING
Defaults to the system's default encoding, which is nearly always utf-8. See
https://docs.python.org/3.11/library/codecs.html#standard-encodings for additional
options.

  -d DELIMITER, --delimiter DELIMITER
Delimiter to use when parsing the input file. Default ','.

  -p PREFIX, --prefix PREFIX
String prepended to each output file

  -s SHUFFLES, --shuffles SHUFFLES
Perform N shuffles. Outputs one set of chopped files per shuffle.

  -c [COLUMNS ...], --columns [COLUMNS ...]
Field names to split by.

  -r ROWS, --rows ROWS
Maximum number of rows per file.

  -q EQUAL, --equal EQUAL
Split file into X files of approximately equal row counts. When used in conjunction
with the --columns argument, this will split each subgroup into X files.

## Avoiding high memory usage
CHOPPER was designed with very large files in mind, so avoids loading the entire file to memory where possible. The only situation where this is impossible is where randomization is used (`--shuffles`) _without_ splitting by column values (`--columns`). When splitting by columns, randomization will be performed on the split files, some or all of which may still be quite large, so use the randomization feature with caution whether or not you split by column values.

## TODO
1. Refactor to skip combining multiple input files when not shuffling, since it is not necessary and potentially expensive.
2. Use multiprocessing to perform post-column operations in parallel.

## Authors
CHOPPER was created by [Joshua Matfess](https://github.com/jsmatfess) of [Table Flip Analytics](https://table-flip.net).

Special thanks to [Peter Stein](https://github.com/pjstein) and [Charlie Gunyon](https://github.com/camgunz) for early feedback.

## License
GNU General Public License v3.0 or later.
See [COPYING](https://github.com/tableflip-analytics/chopper/blob/main/COPYING) to see the full text.