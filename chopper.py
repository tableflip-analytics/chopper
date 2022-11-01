import argparse
import csv
import os
import re

from itertools import repeat
from multiprocessing import Pool
from random import shuffle


def parse_args() -> dict:
    parser = argparse.ArgumentParser(
        description="Get into the CHOPPER so you can Create Hundreds Of Petite Pieces Easily...Really."
    )
    parser.add_argument(
        "input_file",
        type=str,
        help="Absolute or relative path of file to chop.",
    )
    parser.add_argument(
        "output_directory",
        type=str,
        help="Absolute or relative path of folder to output to. An empty/nonexistent folder is highly recommended, as CHOPPER may overwrite files.",
    )
    parser.add_argument("-e", "--encoding", type=str, required=False, default=None)
    parser.add_argument(
        "-p",
        "--prefix",
        type=str,
        help="String prepended to each output file",
        required=False,
        default="",
    )
    parser.add_argument("-c", "--columns", type=str, help="Comma separated list of field names to split by.", required=False, default="")
    parser.add_argument("-r", "--rows", help="Maximum number of rows per file.", type=int, required=False, default=0)
    parser.add_argument(
        "-s",
        "--shuffle",
        action="store_true",
        help="WARNING: In the worst case scenario (when only splitting by row count and not any column), setting this flag requires loading the entire input file to memory. When the columns argument is used, CHOPPER will perform shuffles after splitting by those columns to keep memory use as low as possible.",
    )
    parser.add_argument(
        "-d",
        "--delimiter",
        help="Delimiter to use when parsing the input file. Default ','.",
        type=str,
        required=False,
        default=","
    )

    return vars(parser.parse_args())


def get_csv_dialect(file: str, encoding) -> csv.Dialect:
    with open(file, "r", encoding=encoding) as f:
        return csv.Sniffer().sniff(f.read(4096))


def shuffle_csv(filepath: str, encoding: str) -> None:
    with open(filepath, 'r', encoding=encoding) as fin:
        rows = fin.readlines()
    with open(f"{filepath}_shuff", "w", encoding=encoding) as fout:
        fout.write(rows[0])
        data = rows[1:]
        shuffle(data)
        fout.writelines(data)
    
    os.remove(filepath)
    os.rename(f"{filepath}_shuff", filepath)

    return filepath


def clean_filename(filename: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", filename)


def split_by_columns(filepath: str, col_list: list, rows: int, encoding: str, delimiter: str, output_directory: str, prefix: str, shuffle: bool) -> list[str]:

    with open(filepath, "r", encoding=encoding) as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        files = {}

        for row in reader:
            filepath = os.path.join(output_directory, prefix + clean_filename("_".join([row[col] for col in col_list])))

            if filepath in files:
                writer = files[filepath]["writer"]
            else:
                fout = open(filepath, "w", encoding=encoding)
                writer = csv.DictWriter(fout, delimiter=delimiter, fieldnames=reader.fieldnames)
                # writer = csv.DictWriter(fout, dialect=dialect, fieldnames=reader.fieldnames)
                writer.writeheader()
                files.update({filepath: {"fout": fout, "writer": writer}})
            
            writer.writerow(row)
        
        for file in files.values():
            file["fout"].close()
        
        return list(files.keys())


def split_by_rows(filepath: str, encoding: str, rows: int) -> list[str]:

    with open(filepath, "r", encoding=encoding) as f:
        headers = f.readline()
        filenum = 0
        files = {}

        for i, row in enumerate(f):
            if i % rows == 0:
                filenum += 1
                filename = f"{filepath}_{filenum}"
                fout = open(filename, "w", encoding=encoding)
                fout.write(headers)
                files.update({filename: fout})

            fout.write(row)

        for file in files.values():
            file.close()
    
    os.remove(filepath)
    return list(files.keys())
    

def main() -> None:
    kwargs = parse_args()
    input_file = kwargs["input_file"]
    output_directory = kwargs["output_directory"]
    columns = kwargs["columns"]
    rows = kwargs["rows"]
    encoding = kwargs["encoding"]
    prefix = kwargs["prefix"]
    shuffle = kwargs["shuffle"]
    delimiter = kwargs["delimiter"]


    files = [input_file]
    os.makedirs(output_directory, exist_ok=True)

    if columns:
        col_list = columns.split(",")
        files = split_by_columns(input_file, col_list, rows, encoding, output_directory, prefix, shuffle)

    if shuffle:
        with Pool() as pool:
            pool.starmap(shuffle_csv, zip(files, repeat(encoding)))

    if rows > 0:
        row_files = []
        for file in files:
            row_files.extend(split_by_rows(file, encoding, rows))

        files = row_files


    for file in files:
        if file.endswith(".csv"):
            continue
        os.rename(file, f"{file}.csv")

if __name__ == "__main__":
    main()