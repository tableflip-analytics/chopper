# Copyright (c): 2022, Table Flip Analytics LLC
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import argparse
import csv
import random
import re
import mmap

from io import TextIOWrapper
from itertools import chain, cycle
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Get into the CHOPPER so you can Create Hoards Of Punier Pieces, Evading RAM."
            "Evading RAM."
        )
    )
    parser.add_argument(
        "-i",
        "--input_paths",
        nargs="*",
        type=Path,
        required=True,
        help=(
            "Input file or directory. If a directory is specified, CHOPPER will treat "
            "all files in the directory (including subdirectories) as a single file "
            "for splitting and shuffling purposes."
        ),
    )
    parser.add_argument(
        "-o",
        "--output_directory",
        type=Path,
        required=True,
        help=(
            "An empty/nonexistent folder is highly recommended, as CHOPPER may "
            "overwrite files."
        ),
    )
    parser.add_argument(
        "-x",
        "--extension",
        help=(
            "File extension to search for if any input_paths are directories. "
            "Specifying the extension is highly recommended to avoid accidental "
            "inclusion of files."
        ),
        type=str,
        required=False,
        default="*",
    )
    parser.add_argument(
        "-e",
        "--encoding",
        help=(
            "Defaults to the system's default encoding, which is nearly always utf-8."
            "See https://docs.python.org/3.11/library/codecs.html#standard-encodings "
            "for additional options."
        ),
        type=str,
        required=False,
    )
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
        help="String prepended to each output file.",
        required=False,
    )
    actions = parser.add_argument_group()
    actions.add_argument(
        "-s",
        "--shuffles",
        help=("Perform N shuffles. Outputs one set of chopped files per shuffle."),
        type=int,
        required=False,
        default=0,
    )
    actions.add_argument(
        "-c",
        "--columns",
        nargs="*",
        type=str,
        help="Field names to split by.",
        required=False,
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

    config = parser.parse_args()

    for path in config.input_paths:
        if not path.exists():
            parser.error(
                "Invalid input_paths. Please specify existing file(s) and/or directory (directories)."
            )

    if not config.output_directory.exists():
        config.output_directory.mkdir(exist_ok=True)

    actions = {"columns", "rows", "equal", "shuffles"}
    if len(set(config.__dict__.keys()).intersection(actions)) == 0:
        parser.error(
            "You must specify at least one action (columns, rows, equal, shuffles)."
        )

    return config


def get_offsets(file: TextIOWrapper) -> list[int]:
    pos = 0
    row_offsets = []

    for line in file:
        pos += len(line)
        row_offsets.append(pos)

    return row_offsets


def shuffle_files(
    filepath: Path, shuffles: int, config: argparse.Namespace
) -> list[str]:

    """Creates N copies of the provided file with the headers intact and data lines
    shuffled.

        Args:
            filepath (Path): The path of the file to shuffle.
            shuffles (int): Number of shuffles to perform. Outputs one file per shuffle.
            config (Namespace): Namespace object created from CLI arguments.

        Returns:
            list[Path]: List of shuffled intermediate files.
    """

    files = []

    with filepath.open("r", encoding=config.encoding, newline="") as fin_obj:
        offsets = get_offsets(fin_obj)

        with mmap.mmap(fin_obj.fileno(), length=0, access=mmap.ACCESS_READ) as fin:
            if hasattr(mmap.mmap, "madvise"):
                fin.madvise(mmap.madvise(mmap.MADV_RANDOM))
                
            fin.seek(0)
            headers = fin.readline()

            for i in range(shuffles):
                random.shuffle(offsets)
                new_outpath = config.output_directory / f"{filepath.stem}_shuffle{i+1}"

                with new_outpath.open("wb", encoding=config.encoding) as fout:
                    fout.write(headers)
                    for pos in offsets:
                        fin.seek(pos)
                        fout.write(fin.readline())

                files.append(new_outpath)

    if filepath.absolute().parents[0] == config.output_directory.absolute():
        filepath.unlink()

    # For aesthetics. If only one set of files, no need to specify which shuffle.
    if shuffles == 1:
        fname = config.output_directory / filepath.stem
        new_outpath.rename(fname)
        files[0] = fname
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


def split_by_columns(
    filepath: Path, columns: list[str], config: argparse.Namespace
) -> list[Path]:
    """Create one file per unique combination of values in the specified columns in
    the input file.

        Args:
            filepath (Path): The path of the file to split.
            columns (list[str]): List of columns to split by. Must match values in header row exactly.
            config (argpase.Namespace): Namespace object created from CLI arguments.

        Returns:
            list[Path]: List of split intermediate files.
    """

    with filepath.open("r", encoding=config.encoding, newline="") as f:
        reader = csv.DictReader(f, delimiter=config.delimiter)
        files = {}

        for row in reader:
            # File named based on values of split columns.
            out_path = config.output_directory / clean_filename(
                "__".join([f"{col}_{row[col]}" for col in columns])
            )

            if out_path in files:
                writer = files[out_path]["writer"]
            else:  # Initialize file for new value combination and add to dict.
                fout = out_path.open("w", encoding=config.encoding, newline="")
                writer = csv.DictWriter(
                    fout, delimiter=config.delimiter, fieldnames=reader.fieldnames
                )
                writer.writeheader()
                files.update({out_path: {"fout": fout, "writer": writer}})

            writer.writerow(row)

    for file in files.values():
        file["fout"].close()

    if filepath.absolute().parents[0] == config.output_directory.absolute():
        filepath.unlink()

    return list(files.keys())


def split_by_equal(
    filepath: Path, equal: int, config: argparse.Namespace
) -> list[Path]:
    """Creates N files of approximately (+/- 1) equal size.

    Args:
        filepath (Path): The path of the file to split.
        equal (int): Number of files to split into.
        config (argparse.Namespace): Namespace object created from CLI arguments.

    Returns:
        list[Path]: List of split intermediate files.
    """

    with filepath.open("r", encoding=config.encoding, newline="") as fin:
        files = [
            config.output_directory / f"{filepath.stem}_{i+1}" for i in range(equal)
        ]
        fouts = [f.open("w", encoding=config.encoding, newline="") for f in files]
        fout_cycle = cycle(fouts)

        for i, row in enumerate(fin):
            if i == 0:
                for fout in fouts:
                    fout.write(row)  # Write headers
                continue

            next(fout_cycle).write(row)

    for fout in fouts:
        fout.close()

    if filepath.absolute().parents[0] == config.output_directory.absolute():
        filepath.unlink()

    return files


def split_by_rows(filepath: Path, rows: int, config: argparse.Namespace) -> list[Path]:
    """Splits the input file into files of at most N rows.

    Args:
        filepath (Path): The path of the file to split.
        rows (int): Max rows per file.
        config (argparse.Namespace): Namespace object created from CLI arguments.

    Returns:
        list[Path]: List of split intermediate files.
    """

    with filepath.open("r", encoding=config.encoding, newline="") as f:
        headers = next(f)
        filenum = 0
        files = []
        fouts = []
        for i, row in enumerate(f):

            # Initialize new file.
            if i % rows == 0:
                filenum += 1
                tmp_file = config.output_directory / f"{filepath.stem}_{filenum}"
                files.append(tmp_file)
                fout = tmp_file.open("w", encoding=config.encoding, newline="")
                fouts.append(fout)
                fout.write(headers)

            fout.write(row)

    for fout in fouts:
        fout.close()

    if filepath.absolute().parents[0] == config.output_directory.absolute():
        filepath.unlink()

    return files


def combine_files(in_files: list[Path], config: argparse.Namespace) -> Path:
    """Combines multiple files into one.

    Args:
        in_files (list[Path]): List of files to combine.
        config (argparse.Namespace): Namespace object created from CLI arguments.

    Returns:
        Path: Path of the combined file.
    """

    if len(in_files) == 1:
        return in_files[0]

    combined_fp = config.output_directory / "combined"
    with combined_fp.open("w", encoding=config.encoding, newline="") as fout:
        for i, f in enumerate(in_files):
            with f.open("r", encoding=config.encoding, newline="") as fin:
                if i > 0:  # Skip the header row, except for the first file.
                    fin.readline()
                for line in fin:
                    fout.write(line)
    return combined_fp


def main() -> None:
    config = parse_args()

    files = []
    output_ext = ".csv"  # Default. Overridden below based on actual files.

    if len(config.input_paths) == 1 and config.input_paths[0].is_file():
        output_ext = config.input_paths[0].suffix
        files.append(config.input_paths[0])
    else:
        combine_me = []
        for file in config.input_paths:
            if file.is_dir():
                # "*" is the default extension for wildcarding.
                in_files = list(file.glob(f"**/*.{config.extension}"))

                # Use the extension of the first matching file. Useful when extension is not specified.
                output_ext = in_files[0].suffix
                combine_me.extend(in_files)
            else:
                # If input is a file, use that file's extension for outputs.
                output_ext = file.suffix
                combine_me.append(file)
        if len(combine_me) == 1:
            files.append(combine_me[0])
        else:
            files.append(combine_files(combine_me, config))

    # Split by columns first to avoid full file shuffle if possible.
    if config.columns:
        files = list(
            chain.from_iterable(
                [split_by_columns(file, config.columns, config) for file in files]
            )
        )

    # Shuffling must be done before by-row chops for proper randomization.
    if config.shuffles:
        files = list(
            chain.from_iterable(
                [shuffle_files(file, config.shuffles, config) for file in files]
            )
        )

    if config.rows:
        files = list(
            chain.from_iterable(
                [split_by_rows(file, config.rows, config) for file in files]
            )
        )

    if config.equal:
        files = list(
            chain.from_iterable(
                [split_by_equal(file, config.equal, config) for file in files]
            )
        )

    for file in files:
        newfile = file
        if config.prefix:
            newfile = config.output_directory / f"{config.prefix}_{file.stem}"

        file.rename(f"{newfile}{output_ext}")


main()
