import argparse
import csv
import glob
import os
import random
import re
import shutil
import tempfile

from itertools import cycle
from typing import Any

TMP_DIR = tempfile.TemporaryDirectory()


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


def shuffle_file(
    filepath: str, encoding: str, shuffles: int, to_tmp: bool
) -> list[str]:
    files = []
    with open(filepath, "r", encoding=encoding) as fin:
        rows = fin.readlines()

    filename = os.path.split(filepath)[1].split(".")[0]
    out_path = os.path.join(TMP_DIR.name, filename)

    headers = rows[0]
    data = rows[1:]

    for i in range(shuffles):
        random.shuffle(data)

        if shuffles > 1:
            new_outpath = f"{out_path}_shuffle{i+1}"

        with open(new_outpath, "w", encoding=encoding) as fout:
            fout.write(headers)
            fout.writelines(data)

        files.append(new_outpath)

    if not to_tmp:
        os.remove(filepath)

    return files


def clean_filepath(filename: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", filename)


def split_by_columns(
    filepath: str, col_list: list, encoding: str, delimiter: str, to_tmp: bool
) -> list[str]:

    with open(filepath, "r", encoding=encoding) as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        files = {}

        for row in reader:
            out_path = os.path.join(
                TMP_DIR.name,
                clean_filepath("_".join([row[col] for col in col_list])),
            )

            if out_path in files:
                writer = files[out_path]["writer"]
            else:
                fout = open(out_path, "w", encoding=encoding, newline='')
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


def split_by_equal(filepath: str, encoding: str, equal: int, to_tmp: bool) -> list[str]:

    with open(filepath, "r", encoding=encoding) as fin:
        files = [os.path.join(TMP_DIR.name, f"{filepath}_{i+1}") for i in range(equal)]
        fouts = [open(f, "w", encoding=encoding) for f in files]
        fout_cycle = cycle(fouts)

        for i, row in enumerate(fin):
            if i == 0:
                for fout in fouts:
                    fout.write(row) # Write headers
                continue

            next(fout_cycle).write(row)

    for fout in fouts:
        fout.close()

    if not to_tmp:
        os.remove(filepath)

    return files


def split_by_rows(filepath: str, encoding: str, rows: int, to_tmp: bool) -> list[str]:

    with open(filepath, "r", encoding=encoding) as f:
        headers = ""
        filenum = 0
        files = []
        fouts = []

        for i, row in enumerate(f):
            if i == 0:
                headers = row
                continue

            if (i - 1) % rows == 0:
                filenum += 1
                tmp_file = os.path.join(TMP_DIR.name, f"{filepath}_{filenum}")
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


def main() -> None:
    kwargs = parse_args()
    input_path = os.path.join(os.getcwd(), kwargs["input_path"])
    output_directory = os.path.join(os.getcwd(), kwargs["output_directory"])
    columns = kwargs["columns"]
    rows = kwargs["rows"]
    encoding = kwargs["encoding"]
    prefix = kwargs["prefix"]
    shuffles = kwargs["shuffles"]
    delimiter = kwargs["delimiter"]
    equal = kwargs["equal"]
    to_tmp = True

    files = []
    if os.path.isdir(input_path):
        in_files = glob.glob(input_path + "/**/*.*", recursive=True)
        combined_fp = os.path.join(TMP_DIR.name, "combined")
        with open(combined_fp, "w", encoding=encoding) as fout:
            for i, f in in_files:
                with open(f, "r") as fin:
                    if i > 0:
                        next(fin)
                    for line in fin:
                        fout.write(line)
        files.append(combined_fp)
        to_tmp = False
    else:
        files.append(input_path)

    if columns:
        col_list = columns.split(",")
        new_files = []
        for file in files:
            new_files.extend(split_by_columns(file, col_list, encoding, delimiter, to_tmp))

        files = new_files
        to_tmp = False

    if shuffles:
        new_files = []
        for file in files:
            new_files.extend(shuffle_file(file, encoding, shuffles, to_tmp))

        files = new_files
        to_tmp = False

    if rows:
        new_files = []
        for file in files:
            new_files.extend(split_by_rows(file, encoding, rows, to_tmp))

        files = new_files
        to_tmp = False

    if equal:
        new_files = []
        for file in files:
            new_files.extend(split_by_equal(file, encoding, equal, to_tmp))

        files = new_files
        to_tmp = False

    for file in files:
        if prefix:
            head, tail = os.path.split(file)
            filename = f"{prefix}_{tail}"
            newfile = os.path.join(head, filename)
        os.rename(file, f"{newfile}.csv")

    shutil.copytree(TMP_DIR.name, output_directory, dirs_exist_ok=True)
    TMP_DIR.cleanup()


if __name__ == "__main__":
    main()
