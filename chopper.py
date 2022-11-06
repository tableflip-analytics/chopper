# Copyright (c): 2022, Table Flip Analytics LLC
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import argparse
import csv
import os
import random
import re

from dataclasses import dataclass
from itertools import cycle
from pathlib import Path
from typing import Any


## [CG] Putting this up here since there's not really 1 place to put it: I
##      might spend some time using things like filepath.open and
##      filepath.rename instead of open and os.*. Admittedly there's not a ton
##      of value that comes from doing this, it's just a little more consistent
##      with using pathlib.Path everywhere you can.


## [CG] Oooh fahncy, love it
@dataclass
class Config:
    encoding: str
    delimiter: str
    output_dir: Path
    is_original: bool = True


def parse_args() -> dict[str, Any]:
    parser = argparse.ArgumentParser(
        description=(
            "Get into the CHOPPER so you can Create Hoardes Of Punier Pieces "
            "Evading RAM."
        )
    )
    ## [CG] You could consider letting the user use the shell here, so instead
    ##      of `./chopper.py my_files/ -x csv` you'd invoke something like
    ##      `./chopper.py $(find my_files -name '*.csv')` (you'd accomplish
    ##      this just by adding `nargs="*"` to this argument). It's maybe a
    ##      little less convenient, but it's more flexible (better for power
    ##      users) and would trim a little complexity out of your program.
    parser.add_argument(
        "input_path",
        type=Path,
        help=(
            "Input file or directory. If a directory is specified, CHOPPER will treat "
            "all files in the directory (including subdirectories) as a single file "
            "for splitting and shuffling purposes."
        ),
    )
    parser.add_argument(
        "output_directory",
        type=Path,
        help=(
            "An empty/nonexistent folder is highly recommended, as CHOPPER may "
            "overwrite files."
        ),
    )
    parser.add_argument(
        "-x",
        "--extension",
        help=(
            "File extension to search for if input_path is a directory. Specifying "
            "the extension is highly recommended to avoid accidental inclusion of "
            "files."
        ),
        type=str,
        required=False,
        default="*",
    )

    ## [CG] I'd probably set the default here to 'UTF-8'; Windows people can
    ##      ponder their poor choices. But, dunno your target audience here.
    ##      But, I also think the default is always None? You can probably just
    #       leave it off; idk though.
    parser.add_argument("-e", "--encoding", type=str, required=False, default=None)
    parser.add_argument(
        "-d",
        "--delimiter",
        help="Delimiter to use when parsing the input file. Default ','.",
        type=str,
        required=False,
        default=",",
    )
    parser.add_argument(
        "-p",
        "--prefix",
        type=str,
        help="String prepended to each output file",
        required=False,
    )
    actions = parser.add_argument_group()
    actions.add_argument(
        "-s",
        "--shuffles",
        help=(
            "Perform N shuffles. Outputs one set of chopped files per shuffle. "
            "WARNING: In the worst case scenario (when only splitting by row count "
            "and not any column), setting this flag requires loading the entire input "
            "file to memory. When the columns argument is used, CHOPPER will perform "
            "shuffles after splitting by those columns to keep memory use as low as "
            "possible."
        ),
        type=int,
        required=False,
        default=0,
    )

    ## [CG] You can also use `nargs="*"` here to let people invoke with
    ##      "-c first last" instead of "-c first,last", and then you don't even
    ##      need to `split` into `col_list` later.
    actions.add_argument(
        "-c",
        "--columns",
        type=str,
        help="Comma separated list of field names to split by.",
        required=False,
        default="",
    )
    row_group = actions.add_mutually_exclusive_group()
    row_group.add_argument(
        "-r",
        "--rows",
        help="Maximum number of rows per file.",
        type=int,
        required=False,
        default=0,
    )
    row_group.add_argument(
        "-q",
        "--equal",
        help=(
            "Split file into X files of approximately equal row counts. When used in "
            "conjunction with the --columns argument, this will split each subgroup "
            "into X files."
        ),
        type=int,
        required=False,
        default=0,
    )

    ## [CG] I had never used `vars` with an argument before, which is super
    ##      cool! I've found like, `args.input_path` a little more parsimonious
    ##      than args["input_path"] though, but chalk this up to personal
    ##      preference.
    args = vars(parser.parse_args())

    if not args["input_path"].exists():
        parser.error(
            "Invalid input_path. Please specify an existing file or directory."
        )

    if not args["output_directory"].exists():
        os.makedirs(args["output_directory"], exist_ok=True)

    ## [CG] Man it's wild to me that argparse doesn't have a way to say an
    ##      argument group must have a value, but yeah, next best thing. Also
    ##      wow I did not know dict keys supported `&`; will use!
    actions = ["columns", "rows", "equal", "shuffles"]
    if not args.keys() & actions:
        parser.error(
            "You must specify at least one action (columns, rows, equal, shuffles)."
        )

    return args


## [CG] I see why you're reading the whole file into memory in shuffle_file,
##      but something else you could do is scan for newlines and shuffle their
##      their byte positions (example below). This is definitely slower, but
##      probably not by much with your OS buffering your I/O, and you won't
##      need to allocate a buffer the size of the file in order to shuffle it.
##
##      Sadly it's a lot more convoluted than your method. May not be worth it.
def shuffle_file2(filepath: Path, shuffles: int, config: Config) -> list[Path]:
    with open(filepath, "r", encoding=config.encoding) as fin:
        pos = 0
        line_indices = []
        while chunk := fin.read(32768):
            line_indices.extend([
                pos + m.end() for m in re.finditer(r'\n', chunk)
            ])
            pos += len(chunk)

        for i in range(shuffles):
            random.shuffle(line_indices)

            new_outpath = config.output_dir / f"{filepath.stem}_shuffle{i+1}"

            with open(new_outpath, "w", encoding=config.encoding) as fout:
                for li in line_indices:
                    fin.seek(li)
                    fout.write(fin.readline())

            files.append(new_outpath)

    if not config.is_original:
        os.remove(filepath)

    if shuffles == 1:
        os.rename(new_outpath, filepath)

    return files


def shuffle_file(filepath: Path, shuffles: int, config: Config) -> list[str]:

    """Creates N copies of the provided file with the headers intact and data lines
    shuffled.

        Args:
            filepath (Path): The path of the file to shuffle.
            shuffles (int): Number of shuffles to perform. Outputs one file per shuffle.
            config (Config): Config object created from CLI arguments.

        Returns:
            list[Path]: List of shuffled intermediate files.
    """

    files = []
    with open(filepath, "r", encoding=config.encoding) as fin:
        rows = fin.readlines()

    headers = rows[0]
    data = rows[1:]

    for i in range(shuffles):
        random.shuffle(data)
        new_outpath = config.output_dir / f"{filepath.stem}_shuffle{i+1}"

        with open(new_outpath, "w", encoding=config.encoding) as fout:
            fout.write(headers)
            fout.writelines(data)

        files.append(new_outpath)

    if not config.is_original:
        os.remove(filepath)

    # For aesthetics. If only one set of files, no need to specify which shuffle.
    if shuffles == 1:
        os.rename(new_outpath, filepath)
    return files


def clean_filename(string: str) -> str:
    """Generates a guaranteed valid filename from an arbitrary string using fairly
    aggressive regex.

        Args:
            string (str): The string to clean.

        Returns:
            str: The cleaned filename.
    """
    return re.sub(r"\W", "_", string)


def split_by_columns(filepath: Path, col_list: list[str], config: Config) -> list[Path]:
    """Create one file per unique combination of values in the specified columns in
    the input file.

        Args:
            filepath (Path): The path of the file to split.
            col_list (list): List of columns to split by. Must match values in header row exactly.
            config (Config): Config object created from CLI arguments.

        Returns:
            list[Path]: List of split intermediate files.
    """

    with open(filepath, "r", encoding=config.encoding) as f:
        reader = csv.DictReader(f, delimiter=config.delimiter)
        files = {}

        for row in reader:
            # File named based on values of split columns.
            out_path = config.output_dir / clean_filename(
                "__".join([f"{col}_{row[col]}" for col in col_list])
            )

            if out_path in files:
                writer = files[out_path]["writer"]
            else:  # Initialize file for new value combination and add to dict.
                fout = open(out_path, "w", encoding=config.encoding, newline="")
                writer = csv.DictWriter(
                    fout, delimiter=config.delimiter, fieldnames=reader.fieldnames
                )
                writer.writeheader()
                files.update({out_path: {"fout": fout, "writer": writer}})

            writer.writerow(row)

    for file in files.values():
        file["fout"].close()

    if not config.is_original:
        os.remove(filepath)

    return list(files.keys())


def split_by_equal(filepath: Path, equal: int, config: Config) -> list[Path]:
    """Creates N files of approximately (+/- 1) equal size.

    Args:
        filepath (Path): The path of the file to split.
        equal (int): Number of files to split into.
        config (Config): Config object created from CLI arguments.

    Returns:
        list[Path]: List of split intermediate files.
    """

    with open(filepath, "r", encoding=config.encoding) as fin:
        files = [config.output_dir / f"{filepath.stem}_{i+1}" for i in range(equal)]
        fouts = [open(f, "w", encoding=config.encoding) for f in files]
        fout_cycle = cycle(fouts)

        for i, row in enumerate(fin):
            if i == 0:
                for fout in fouts:
                    fout.write(row)  # Write headers
                continue

            next(fout_cycle).write(row)

    for fout in fouts:
        fout.close()

    if not config.is_original:
        os.remove(filepath)

    return files


def split_by_rows(filepath: Path, rows: int, config: Config) -> list[Path]:
    """Splits the input file into files of at most N rows.

    Args:
        filepath (Path): The path of the file to split.
        rows (int): Max rows per file.
        config (Config): Config object created from CLI arguments.

    Returns:
        list[Path]: List of split intermediate files.
    """

    with open(filepath, "r", encoding=config.encoding) as f:
        headers = ""
        filenum = 0
        files = []
        fouts = []

        ## [CG] Dunno how the math works out here, but you could use next(f)
        ##      to get the headers (which I didn't know you could do on a file
        ##      object; I thought you had to do like `lines = iter(f)` first)

        for i, row in enumerate(f):
            if i == 0:
                headers = row
                continue

            # Initialize new file.
            if (i - 1) % rows == 0:
                filenum += 1
                tmp_file = config.output_dir / f"{filepath.stem}_{filenum}"
                files.append(tmp_file)
                fout = open(tmp_file, "w", encoding=config.encoding)
                fouts.append(fout)
                fout.write(headers)

            fout.write(row)

    for fout in fouts:
        fout.close()

    if not config.is_original:
        os.remove(filepath)

    return files


def combine_files(in_files: list[Path], config: Config) -> Path:
    """Combines multiple files into one.

    Args:
        in_files (list[Path]): List of files to combine.
        config (Config): Config object created from CLI arguments.

    Returns:
        Path: Path of the combined file.
    """

    if len(in_files) == 1:
        return in_files[0]

    combined_fp = config.output_dir / "combined"
    with open(combined_fp, "w", encoding=config.encoding) as fout:
        for i, f in enumerate(in_files):
            with open(f, "r") as fin:
                if i > 0:  # Skip the header row, except for the first file.
                    next(fin)
                for line in fin:
                    fout.write(line)

    return combined_fp


def main() -> None:
    args = parse_args()
    input_path: Path = args["input_path"]
    output_dir: Path = args["output_directory"]
    extension: str = args["extension"]
    columns: str = args["columns"]
    rows: int = args["rows"]
    encoding: str = args["encoding"]
    prefix: str = args["prefix"]
    shuffles: int = args["shuffles"]
    delimiter: str = args["delimiter"]
    equal: int = args["equal"]

    config = Config(encoding, delimiter, output_dir)

    files = []
    output_ext = ".csv"  # Default. Overridden below based on actual files.

    if input_path.is_dir():
        # "*" is the default extension for wildcarding.
        in_files = list(input_path.glob(f"**/*.{extension}"))

        # Use the extension of the first matching file. Useful when extension is not specified.
        output_ext = in_files[0].suffix

        files = [combine_files(in_files, config)]
        config.is_original = False
    else:
        # If input is a file, use that file's extension for outputs.
        output_ext = input_path.suffix
        files.append(input_path)

    # Split by columns first to avoid full file shuffle if possible.
    if columns:
        col_list = columns.split(",")
        ## [CG] To save a few lines you could do:
        ##      files = [split_by_columns(f, col_list, config) for f in files]
        new_files = []
        for file in files:
            new_files.extend(split_by_columns(file, col_list, config))

        files = new_files
        config.is_original = False

    # Shuffling must be done before by-row chops for proper randomization.
    if shuffles:
        new_files = []
        for file in files:
            new_files.extend(shuffle_file(file, shuffles, config))

        files = new_files
        config.is_original = False

    if rows:
        new_files = []
        for file in files:
            new_files.extend(split_by_rows(file, rows, config))

        files = new_files
        config.is_original = False

    if equal:
        new_files = []
        for file in files:
            new_files.extend(split_by_equal(file, equal, config))

        files = new_files
        config.is_original = False

    for file in files:
        newfile = file
        if prefix:
            newfile = output_dir / f"{prefix}_{file.stem}"

        os.rename(file, f"{newfile}{output_ext}")

## [CG] You can just do `main()` here; this test is for checking if this is
##      the "main" script invoked, which is usually used for testing frameworks
##      where you have some library code in a file, but if you run `python` on
##      that file it'll run the tests (or you're using `multiprocessing`, but
##      God help you in that case).

if __name__ == "__main__":
    main()
