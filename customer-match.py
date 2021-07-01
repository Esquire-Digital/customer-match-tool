#!/usr/bin/python3
import os
from typing import Iterable
import click
import sys
import csv
import time
import pandas as pd
import hashlib
from tqdm import tqdm
from uszipcode import SearchEngine
from constants import ANSI, ALL_HEADERS, REQUIRED_HEADERS, HEADER_TRANSLATIONS


class Error(ValueError):
    """Base class for other custom exceptions"""

    pass


class FormatError(Error):
    """Raised when a file is not in the correct format."""

    pass


class NoZipError(FormatError):
    """Raised when a zip code is not found in a spreadsheet. Sometimes recoverable."""

    pass


def warn(message: str):
    tqdm.write(f"{ANSI['BOLD'] + ANSI['YELLOW']}WARNING:{ANSI['RESET']} {message}")


def notify(message: str):
    tqdm.write(f"{ANSI['BOLD'] + ANSI['CYAN']}INFO:{ANSI['RESET']} {message}")


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
        raise ValueError(
            f"Could not get a CSV dialect for file {basename}. Is it a CSV file? Is it maybe too large?"
        )


def parse_google_fields(filepath: str, ignore_zip: bool = False) -> dict:
    """Parse the header of the CSV to get the Google field names.

    Args:
        filepath (str): Path to the CSV file.

    Raises:
        ValueError: If not all required headers can be found

    Returns:
        dict: A map from Google's field name to the field name that was found in the CSV.
                eg: "First Name": "first_name"
    """
    field_map = {}
    found_headers = []
    with open(filepath, "r") as file:
        reader = csv.DictReader(file)
        field_names = reader.fieldnames

        # For each field in the header column, try to translate
        # them to a header recognized by Google.
        for field in field_names:
            header = None
            # Check if there is a direct translation first:
            if field in HEADER_TRANSLATIONS:
                header = HEADER_TRANSLATIONS[field]
            # Otherwise attempt to translate snake case:
            elif (translated_field := field.replace("_", " ").title()) in ALL_HEADERS:
                header = translated_field

            # If we have not found this header yet, add it to the map.
            # Otherwise, if we have found the header already, warn the user.
            if header is not None and header not in found_headers:
                notify(f"Detected header name '{header}' as '{field}' in CSV file")
                field_map[field] = header
                found_headers.append(header)
            elif header in found_headers:
                warn(
                    f"Duplicate header name '{header}' was extracted as '{field}'. Keeping column with header '{field_map[header]}'"
                )
    # Check if we have all required headers.
    # All required headers are found if the required headers set is a subset of the headers found.
    if not REQUIRED_HEADERS.issubset(field_map.values()):
        missing_headers = REQUIRED_HEADERS.difference(field_map.values())
        if len(missing_headers) == 1 and list(missing_headers)[0] == "Zip":
            if not ignore_zip:
                raise NoZipError(field_map)
        else:
            raise FormatError(
                f"Not all required headers found. Missing: {', '.join(missing_headers)}"
            )
    return field_map


def parse_location_fields(filepath: str):
    WANTED_FIELDS = {"state", "city"}
    found_translations = []
    field_map = {}
    with open(filepath, "r") as file:
        reader = csv.DictReader(file)
        field_names = reader.fieldnames

        for field in field_names:
            # Salesql CSVs prefix state and city by person_.
            salesql_field = field.replace("person_", "")
            possible_fields = {field, salesql_field}
            if found_set := WANTED_FIELDS.intersection(possible_fields):
                translation = list(found_set)[0]
                notify(f"Detected header name '{translation}' as '{field}' in CSV file")
                found_translations.append(translation)
                field_map[field] = translation

    if not WANTED_FIELDS.issubset(field_map.values()):
        missing_fields = WANTED_FIELDS.difference(field_map.values())
        raise FormatError(
            f"Could not find state and city columns. Missing: {', '.join(missing_fields)}"
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
    notify(f"Hashing {dataframe.size} elements...")
    start = time.time()
    dataframe = dataframe.applymap(hash_element)
    notify(
        f"Finished hashing {dataframe.size} elements in {time.time() - start} seconds."
    )
    return dataframe


def get_dataframe(filepath: str) -> pd.DataFrame:
    """Gets a dataframe for a given CSV file.

    Args:
        filepath (str): Path to the CSV file.

    Returns:
        pd.DataFrame: [description]
    """
    dialect = check_csv(filepath)
    return pd.read_csv(
        filepath,
        warn_bad_lines=False,
        error_bad_lines=False,
        sep=dialect.delimiter,
        low_memory=False,
    )


def translate_dataframe(dataframe: pd.DataFrame, field_map: dict) -> pd.DataFrame:
    """Translates a CSV file to use Google's desired field names in the header.
        Any columns with field names that are not recognized by the Customer Match
        specification are removed.

    Args:
        dataframe (pd.DataFrame): The DataFrame of the CSV file.

    Returns:
        pd.DataFrame: The pandas dataframe that was translated.
                        Can be exported to a CSV with the save_csv function.
    """
    # Parse the headers into a field_map.
    # Keep only the columns that have matching headers.
    dataframe = dataframe[field_map.keys()]
    # Reverse the map to rename columns to Google's expectation.
    dataframe = dataframe.rename(columns=field_map)
    return dataframe


def save_csv(dataframe: pd.DataFrame, output: str):
    """Saves a dataframe to a CSV file.

    Args:
        dataframe (pd.DataFrame): The dataframe to be saved
        output (str): The filepath to be saved to
    """
    dataframe.to_csv(output, index=False, encoding="utf-8")
    notify(f"Succesfully saved Customer Match data file to {os.path.abspath(output)}.")


def get_zip(row: pd.Series, search: SearchEngine) -> pd.Series:
    try:
        if row["city"] and row["state"]:
            res = search.by_city_and_state(city=row["city"], state=row["state"])
            return res[0].zipcode
        else:
            return ""
    except (AttributeError, IndexError):
        warn(f"Zip lookup for {row['city']}, {row['state']} failed")
        return ""


def get_zips(dataframe: pd.DataFrame) -> pd.DataFrame:
    search = SearchEngine()
    tqdm.pandas(desc="Getting zipcodes")
    return dataframe.progress_apply(lambda row: get_zip(row, search), axis=1)


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
        file = None
        # Attempt to translate to Google's standard.
        try:
            check_path(output)
            file = get_dataframe(filepath)
            field_map = parse_google_fields(filepath)
            file = translate_dataframe(file, field_map)
        # If the no zip is found, it is possible to lookup zip
        # codes. Ask the user if they want to try.
        except NoZipError:
            warn(
                "A zip code column could not be found in the CSV file. If there is a state and city column, the zip codes may be able to be automatically detected."
            )
            if click.confirm("Would you like to try to detect zip codes?"):
                field_map = parse_location_fields(filepath)
                states_and_cities = translate_dataframe(file, field_map)
                zip_codes = get_zips(states_and_cities)
                field_map = parse_google_fields(filepath, ignore_zip=True)
                translated = translate_dataframe(file, field_map)
                file = pd.concat([translated, zip_codes], axis=1)
            else:
                sys.exit()
        if do_hash:
            file = hash_dataframe(file)
        save_csv(file, output)
        return 0
    except ValueError as e:
        sys.exit(f"{ANSI['BOLD'] + ANSI['RED']}ERROR:{ANSI['RESET']} {e}")


if __name__ == "__main__":
    generate()