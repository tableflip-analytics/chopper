import argparse
import os
import pandas as pd


def get_equal_sizes(x: int, n: int) -> list[int]:

    sizes = []

    if x < n:
        sizes.append(x)

    elif x % n == 0:
        sizes = [x // n for i in range(n)]

    else:
        zp = n - (x % n)
        pp = x // n
        for i in range(n):
            if i >= zp:
                sizes.append(pp + 1)
            else:
                sizes.append(pp)
    return sizes


def get_limited_sizes(x: int, max_size: int) -> list[int]:
    sizes = [max_size for _ in range(int(x / max_size))]

    if x % max_size != 0:
        sizes.append(x % max_size)

    return sizes


def combine_csvs(folder: str) -> pd.DataFrame:
    return pd.concat([pd.read_csv(f"{folder}/{f}") for f in os.listdir(folder)])


def chunk_df(df: pd.DataFrame, sizes: list[int], output_path: str) -> None:
    row = 0
    for i, size in enumerate(sizes):
        df[row : row + size].to_csv(f"{output_path}_list{i+1}.csv", index=False)
        row += size

    return


def shuffle_df(
    df: pd.DataFrame, output_path: str, shuffles: int, chunks: int, max_size: int
) -> None:
    for i in range(shuffles):
        new_path = f"{output_path}_shuffle{i+1}"
        df = df.sample(frac=1)
        if chunks == 1 and not max_size:
            df.to_csv(f"{new_path}.csv", index=False)
        elif max_size:
            sizes = get_limited_sizes(len(df), max_size)
            chunk_df(df, sizes, new_path)
        else:
            sizes = get_equal_sizes(len(df), chunks)
            chunk_df(df, sizes, new_path)


def main(args):
    df = combine_csvs(args["input_folder"])
    output_path = f'{args["output_folder"]}/{args["output_prefix"]}'

    if not args["shuffles"]:
        chunk_df(df, args["chunks"], output_path)

    else:
        shuffle_df(df, output_path, args["shuffles"], args["chunks"], args["max_size"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Welcome to the shuffler.")
    parser.add_argument("input_folder", type=str, metavar="I")
    parser.add_argument(
        "-o", "--output_folder", type=str, metavar="O", required=False, default="./outputs"
    )
    parser.add_argument(
        "-s", "--shuffles", type=int, help="Number of shuffles to perform.", required=False, default=0
    )
    parser.add_argument(
        "-c",
        "--chunks",
        type=int,
        required=False,
        default=1,
        help="Number of equal chunks to create. Cannot be used with MAX_SIZE.",
    )
    parser.add_argument(
        "-m",
        "--max_size",
        type=int,
        required=False,
        default=0,
        help="Maximum number of records to include per file. Cannot be used with CHUNKS.",
    )
    parser.add_argument(
        "-p",
        "--output-prefix",
        type=str,
        help="String to use for file output. Format: {prefix}_shuffle{x}_list{y}.csv",
        default="data",
    )

    args = vars(parser.parse_args())
    main(args)
