#!/usr/bin/python3
import os
import click
import sys
import csv
import time
import pandas as pd
import hashlib
from translations import HEADERS as HEADER_TRANSLATIONS


VALID_HEADERS = ("First Name", "Last Name", "Phone", "Email", "Country", "Zip")


ANSI = {
    "YELLOW": "\u001b[33m",
    "RED": "\u001b[31m",
    "BOLD": "\u001b[1m",
    "RESET": "\u001b[0m",
}


def check_path(filename: str):
    path = os.path.dirname(filename)
    if path.strip() and not os.path.exists(path):
        raise ValueError(f"The path {path} does not exist.")


def check_file(filename: str) -> csv.Dialect:
    # Check that the file exists, and is a file.
    basename = os.path.basename(filename)
    if not os.path.exists(filename):
        raise ValueError(f"The path {filename} does not exist.")
    if not os.path.isfile(filename):
        raise ValueError(f"{basename} is not a file.")

    # Try to open the file and verify it can be read as a CSV.
    try:
        file = open(filename)
        dialect = csv.Sniffer().sniff(file.read(100000))
        file.seek(0)
        file.close()
        return dialect
    except csv.Error as e:
        print(e)
        print("here")
        raise ValueError(
            f"Could not get a CSV dialect for file {basename}. Is it a CSV file? Is it maybe too large?"
        )


def parse_headers(filename: str) -> dict:
    field_map = {}
    with open(filename, "r") as file:
        reader = csv.DictReader(file)
        field_names = reader.fieldnames

        # For each field in the header column, try to translate
        # them to a header recognized by Google.
        for field in field_names:
            field = field.strip()
            header = None
            # Check if there is a direct translation first:
            if field in HEADER_TRANSLATIONS:
                header = HEADER_TRANSLATIONS[field]
            # Otherwise attempt to translate snake case:
            elif (translated_field := field.replace("_", " ").title()) in VALID_HEADERS:
                header = translated_field

            # If we have not found this header yet, add it to the map.
            # Otherwise, if we have found the header already, warn the user.
            if header is not None and header not in field_map:
                click.echo(f"Detected header name '{header}' as '{field}' in CSV file.")
                field_map[header] = field
            elif header in field_map:
                click.echo(
                    f"{ANSI['BOLD'] + ANSI['YELLOW']}WARNING:{ANSI['RESET']} Duplicate header name '{header}' was extracted as '{field}'. Keeping column with header '{field_map[header]}'."
                )
    return field_map


def hash_element(element: any):
    element = str(element).encode("utf-8")
    return hashlib.sha256(element).hexdigest()


def hash_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    print(f"Hashing {dataframe.size} elements...")
    start = time.time()
    dataframe = dataframe.applymap(hash_element)
    print(
        f"Finished hashing {dataframe.size} elements in {time.time() - start} seconds."
    )
    return dataframe


def translate_csv(filename: str, dialect: csv.Dialect) -> pd.DataFrame:
    file = pd.read_csv(
        filename,
        warn_bad_lines=False,
        error_bad_lines=False,
        sep=dialect.delimiter,
        low_memory=False,
    )
    # Parse the headers into a field_map.
    field_map = parse_headers(filename)
    if not field_map:
        raise ValueError(
            "CSV file did not have any recognizable headers. Cannot translate."
        )

    # Keep only the columns that have matching headers.
    file = file[field_map.values()]
    # Reverse the map to rename columns to Google's expectation.
    file = file.rename(columns={v: k for k, v in field_map.items()})
    return file


def save_csv(dataframe: pd.DataFrame, output: str):
    dataframe.to_csv(output, index=False, encoding="utf-8")
    print(f"Succesfully saved Customer Match data file to {os.path.abspath(output)}.")


@click.command(
    help="Generates a Google Ads Customer Match compliant CSV file from a (potentially large) CSV file in another format."
)
@click.option("-o", "--output", default="result.csv", help="Path to output file.")
@click.option(
    "--hash/--no-hash",
    "do_hash",
    default=False,
    help="Whether or not to SHA256 hash the contents of each cell.",
)
@click.option(
    "--upload/--no-upload",
    default=False,
    help="Whether or not to upload to Google Adwords automatically. Requires environment variable setup.",
)
@click.argument("filename")
def generate(filename: str, output: str, do_hash: bool, upload: bool):
    try:
        check_path(output)
        dialect = check_file(filename)
        file = translate_csv(filename, dialect)
        if do_hash:
            file = hash_dataframe(file)
        save_csv(file, output)
        return 0
    except ValueError as e:
        sys.exit(f"{ANSI['BOLD'] + ANSI['RED']}ERROR:{ANSI['RESET']} {e}")


if __name__ == "__main__":
    generate()