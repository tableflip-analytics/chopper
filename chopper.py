import argparse
import csv
import glob
import os
import random
import re

from itertools import cycle
from typing import Any


def parse_args() -> dict[str, Any]:
    parser = argparse.ArgumentParser(
        description="Get into the CHOPPER so you can Create Hoardes Of Punier Pieces Evading RAM."
    )
    parser.add_argument(
        "input_path",
        type=str,
        help="Input file or directory. If a directory is specified, CHOPPER will treat all files in the directory (including subdirectories) as a single file for splitting and shuffling purposes.",
    )
    parser.add_argument(
        "output_directory",
        type=str,
        help="An empty/nonexistent folder is highly recommended, as CHOPPER may overwrite files.",
    )
    parser.add_argument(
        "-x",
        "--extension",
        help="File extension to search for if input_path is a directory. Specifying the extension is highly recommended to avoid accidental inclusion of files.",
        type=str,
        required=False,
        default="*",
    )
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
        help="Perform N shuffles. Outputs one set of chopped files per shuffle. WARNING: In the worst case scenario (when only splitting by row count and not any column), setting this flag requires loading the entire input file to memory. When the columns argument is used, CHOPPER will perform shuffles after splitting by those columns to keep memory use as low as possible.",
        type=int,
        required=False,
        default=0,
    )
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
        help="Split file into X files of approximately equal row counts. When used in conjunction with the --columns argument, this will split each subgroup into X files.",
        type=int,
        required=False,
        default=0,
    )

    args = vars(parser.parse_args())

    actions = ["columns", "rows", "equal", "shuffles"]
    if not args.keys() & actions:
        parser.error(
            "You must specify at least one action argument (columns, rows, equal, shuffles)"
        )

    return args


def get_filename(filepath: str):
    return os.path.split(filepath)[1].split(".")[0]


def shuffle_file(
    filepath: str, encoding: str, shuffles: int, to_tmp: bool, output_dir: str
) -> list[str]:

    """Creates N copies of the provided file with the headers intact and data lines shuffled.

    Args:
        filepath (str): The path of the file to shuffle.
        encoding (str): Encoding to use for file read and write operations.
        shuffles (int): Number of shuffles to perform. Outputs one file per shuffle.
        to_tmp (bool): True implies the input file is the original file and should not be deleted.
        output_dir (str): Destination directory.

    Returns:
        list[str]: List of shuffled intermediate files.
    """

    files = []
    with open(filepath, "r", encoding=encoding) as fin:
        rows = fin.readlines()

    filename = get_filename(filepath)
    out_path = os.path.join(output_dir, filename)

    headers = rows[0]
    data = rows[1:]

    for i in range(shuffles):
        random.shuffle(data)

        # For aesthetics. If only one set of files, no need to specify which shuffle.
        if shuffles > 1:
            new_outpath = f"{out_path}_shuffle{i+1}"

        with open(new_outpath, "w", encoding=encoding) as fout:
            fout.write(headers)
            fout.writelines(data)

        files.append(new_outpath)

    if not to_tmp:
        os.remove(filepath)
    return files


def clean_filename(string: str) -> str:
    """Generates a guaranteed valid filename from an arbitrary string using fairly aggressive regex.

    Args:
        string (str): The string to clean.

    Returns:
        str: The cleaned filename.
    """
    return re.sub(r"[^a-zA-Z0-9_]", "_", string)


def split_by_columns(
    filepath: str,
    col_list: list[str],
    encoding: str,
    delimiter: str,
    to_tmp: bool,
    output_dir: str,
) -> list[str]:
    """Create one file per unique combination of values in the specified columns in the input file.

    Args:
        filepath (str): The path of the file to split.
        col_list (list): List of columns to split by. Must match values in header row exactly.
        encoding (str): Encoding to use for file read and write operations.
        delimiter (str): Delimiter to use for file read and write operations.
        to_tmp (bool): True implies the input file is the original file and should not be deleted.
        output_dir (str): Destination directory.

    Returns:
        list[str]: List of split intermediate files.
    """

    with open(filepath, "r", encoding=encoding) as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        files = {}

        for row in reader:
            out_path = os.path.join(
                output_dir,
                clean_filename("_".join([row[col] for col in col_list])),
            )  # File named based on values of split columns.

            if out_path in files:
                writer = files[out_path]["writer"]
            else:  # Initialize file for new value combination and add to dict.
                fout = open(out_path, "w", encoding=encoding, newline="")
                writer = csv.DictWriter(
                    fout, delimiter=delimiter, fieldnames=reader.fieldnames
                )
                writer.writeheader()
                files.update({out_path: {"fout": fout, "writer": writer}})

            writer.writerow(row)

    for file in files.values():
        file["fout"].close()

    if not to_tmp:
        os.remove(filepath)

    return list(files.keys())


def split_by_equal(
    filepath: str, encoding: str, equal: int, to_tmp: bool, output_dir: str
) -> list[str]:
    """Creates N files of approximately (+/- 1) equal size.

    Args:
        filepath (str): The path of the file to split.
        encoding (str): Encoding to use for file read and write operations.
        equal (int): Number of files to split into.
        to_tmp (bool): True implies the input file is the original file and should not be deleted.
        output_dir (str): Destination directory.

    Returns:
        list[str]: List of split intermediate files.
    """

    filename = get_filename(filepath)

    with open(filepath, "r", encoding=encoding) as fin:
        files = [os.path.join(output_dir, f"{filename}_{i+1}") for i in range(equal)]
        fouts = [open(f, "w", encoding=encoding) for f in files]
        fout_cycle = cycle(fouts)

        for i, row in enumerate(fin):
            if i == 0:
                for fout in fouts:
                    fout.write(row)  # Write headers
                continue

            next(fout_cycle).write(row)

    for fout in fouts:
        fout.close()

    if not to_tmp:
        os.remove(filepath)

    return files


def split_by_rows(
    filepath: str, encoding: str, rows: int, to_tmp: bool, output_dir: str
) -> list[str]:
    """Splits the input file into files of at most N rows.

    Args:
        filepath (str): The path of the file to split.
        encoding (str): Encoding to use for file read and write operations.
        rows (int): Max rows per file.
        to_tmp (bool): True implies the input file is the original file and should not be deleted.
        output_dir (str): Destination directory.

    Returns:
        list[str]: List of split intermediate files.
    """

    with open(filepath, "r", encoding=encoding) as f:
        filename = get_filename(filepath)
        headers = ""
        filenum = 0
        files = []
        fouts = []

        for i, row in enumerate(f):
            if i == 0:
                headers = row
                continue

            # Initialize new file.
            if (i - 1) % rows == 0:
                filenum += 1
                tmp_file = os.path.join(output_dir, f"{filename}_{filenum}")
                files.append(tmp_file)
                fout = open(tmp_file, "w", encoding=encoding)
                fouts.append(fout)
                fout.write(headers)

            fout.write(row)

    for fout in fouts:
        fout.close()

    if not to_tmp:
        os.remove(filepath)

    return files


def combine_files(in_files: list[str], encoding: str, output_dir: str) -> list[str]:
    """Combines multiple files into one.

    Args:
        in_files (list[str]): List of files to combine.
        to_tmp (bool): True implies the input file is the original file and should not be deleted.
        output_dir (str): Destination directory.

    Returns:
        str: Path of the combined file.
    """

    combined_fp = os.path.join(output_dir, "combined")
    with open(combined_fp, "w", encoding=encoding) as fout:
        for i, f in enumerate(in_files):
            with open(f, "r") as fin:
                if i > 0:  # Skip the header row, except for the first file.
                    next(fin)
                for line in fin:
                    fout.write(line)

    return combined_fp


def main() -> None:
    kwargs = parse_args()
    input_path = os.path.join(os.getcwd(), kwargs["input_path"])
    output_dir = os.path.join(os.getcwd(), kwargs["output_directory"])
    extension = kwargs["extension"]
    columns = kwargs["columns"]
    rows = kwargs["rows"]
    encoding = kwargs["encoding"]
    prefix = kwargs["prefix"]
    shuffles = kwargs["shuffles"]
    delimiter = kwargs["delimiter"]
    equal = kwargs["equal"]

    # Indicates that we're still operating on the original files and therefore should
    # not delete it after creating the next set of intermediate files.
    to_tmp = True

    files = []
    ext = ".csv"
    if os.path.isdir(input_path):
        in_files = glob.glob(input_path + f"/**/*.{extension}", recursive=True)

        # Use the extension of the first matching file. Useful when extension is not specified.
        ext = os.path.splitext(in_files[0])[1]

        files = [combine_files(in_files, encoding, output_dir)]
        to_tmp = False
    else:
        ext = os.path.splitext(input_path)[1]
        files.append(input_path)

    # Split by columns first to avoid full file shuffle if possible.
    if columns:
        col_list = columns.split(",")
        new_files = []
        for file in files:
            new_files.extend(
                split_by_columns(
                    file, col_list, encoding, delimiter, to_tmp, output_dir
                )
            )

        files = new_files
        to_tmp = False

    # Shuffling must be done before by-row chops for proper randomization.
    if shuffles:
        new_files = []
        for file in files:
            new_files.extend(shuffle_file(file, encoding, shuffles, to_tmp, output_dir))

        files = new_files
        to_tmp = False

    if rows:
        new_files = []
        for file in files:
            new_files.extend(split_by_rows(file, encoding, rows, to_tmp, output_dir))

        files = new_files
        to_tmp = False

    if equal:
        new_files = []
        for file in files:
            new_files.extend(split_by_equal(file, encoding, equal, to_tmp, output_dir))

        files = new_files
        to_tmp = False

    for file in files:
        newfile = file
        if prefix:
            head, tail = os.path.split(file)
            filename = f"{prefix}_{tail}"
            newfile = os.path.join(head, filename)

        os.rename(file, f"{newfile}.{ext}")


if __name__ == "__main__":
    main()
