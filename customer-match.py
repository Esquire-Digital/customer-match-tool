#!/usr/bin/python3
import os
import click
import sys
import csv
import time
import pandas as pd
import hashlib
from constants import ANSI, ALL_HEADERS, REQUIRED_HEADERS, HEADER_TRANSLATIONS


def check_path(filepath: str):
    """Checks that the path to a file exists. To check if a path to the file and the file itself exists,
        use check_csv

    Args:
        filepath (str): The path to the file

    Raises:
        ValueError: If the path to the file does not exist
    """
    path = os.path.dirname(filepath)
    if path.strip() and not os.path.exists(path):
        raise ValueError(f"The path {path} does not exist.")


def check_csv(filepath: str) -> csv.Dialect:
    """Runs checks on a CSV file, such as whether it exists and if it can be parsed, and returns
        its dialect object

    Args:
        filepath (str): Path to the CSV file

    Raises:
        ValueError: If the path does not exist, or the file cannot be read as a CSV

    Returns:
        csv.Dialect: Parsed CSV dialect from the file
    """
    # Check that the file exists, and is a file.
    basename = os.path.basename(filepath)
    if not os.path.exists(filepath):
        raise ValueError(f"The path {filepath} does not exist.")
    if not os.path.isfile(filepath):
        raise ValueError(f"{basename} is not a file.")

    # Try to open the file and verify it can be read as a CSV.
    try:
        file = open(filepath)
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


def parse_fields(filepath: str) -> dict:
    """Parse the header of the CSV to get the field names.

    Args:
        filepath (str): Path to the CSV file.

    Raises:
        ValueError: If not all required headers can be found

    Returns:
        dict: A map from Google's field name to the field name that was found in the CSV.
                eg: "First Name": "first_name"
    """
    field_map = {}
    with open(filepath, "r") as file:
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
            elif (translated_field := field.replace("_", " ").title()) in ALL_HEADERS:
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
    # Check if we have all required headers.
    # All required headers are found if the required headers set is a subset of the headers found.
    if not REQUIRED_HEADERS.issubset(field_map.keys()):
        raise ValueError(
            f"Not all required headers found. Missing: {', '.join(REQUIRED_HEADERS.difference(field_map.keys()))}"
        )
    return field_map


def hash_element(element: any) -> str:
    """Produces a sha256 hash.

    Args:
        element (any): The data to be hashed

    Returns:
        str: The sha256 hash hex digest
    """
    element = str(element).encode("utf-8")
    return hashlib.sha256(element).hexdigest()


def hash_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Hashes all elements in a Pandas dataframe.

    Args:
        dataframe (pd.DataFrame): The dataframe to be hashed

    Returns:
        pd.DataFrame: The dataframe with all elements hashed
    """
    print(f"Hashing {dataframe.size} elements...")
    start = time.time()
    dataframe = dataframe.applymap(hash_element)
    print(
        f"Finished hashing {dataframe.size} elements in {time.time() - start} seconds."
    )
    return dataframe


def translate_csv(filepath: str, dialect: csv.Dialect) -> pd.DataFrame:
    """Translates a CSV file to use Google's desired field names in the header.
        Any columns with field names that are not recognized by the Customer Match
        specification are removed.

    Args:
        filepath (str): The path to the CSV file
        dialect (csv.Dialect): The dialect object for the CSV file. Needed to know the delimiter of the file.

    Returns:
        pd.DataFrame: The pandas dataframe that was translated.
                        Can be exported to a CSV with the save_csv function.
    """
    file = pd.read_csv(
        filepath,
        warn_bad_lines=False,
        error_bad_lines=False,
        sep=dialect.delimiter,
        low_memory=False,
    )
    # Parse the headers into a field_map.
    field_map = parse_fields(filepath)
    # Keep only the columns that have matching headers.
    file = file[field_map.values()]
    # Reverse the map to rename columns to Google's expectation.
    file = file.rename(columns={v: k for k, v in field_map.items()})
    return file


def save_csv(dataframe: pd.DataFrame, output: str):
    """Saves a dataframe to a CSV file.

    Args:
        dataframe (pd.DataFrame): The dataframe to be saved
        output (str): The filepath to be saved to
    """
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
@click.argument("filepath")
def generate(filepath: str, output: str, do_hash: bool, upload: bool):
    try:
        check_path(output)
        dialect = check_csv(filepath)
        file = translate_csv(filepath, dialect)
        if do_hash:
            file = hash_dataframe(file)
        save_csv(file, output)
        return 0
    except ValueError as e:
        sys.exit(f"{ANSI['BOLD'] + ANSI['RED']}ERROR:{ANSI['RESET']} {e}")


if __name__ == "__main__":
    generate()