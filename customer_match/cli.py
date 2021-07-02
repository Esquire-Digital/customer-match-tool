#!/usr/bin/python3
import os
import click
import sys
import csv
import time
import pandas as pd
import country_converter as coco
import hashlib
import phonenumbers
from tqdm import tqdm
from uszipcode import SearchEngine

HEADER_TRANSLATIONS = {
    "email1": "Email",
    "phone1": "Phone",
    "person_country": "Country",
}

REQUIRED_HEADERS = {"First Name", "Last Name", "Phone", "Email", "Country", "Zip"}
OPTIONAL_HEADERS = set()  # TODO: Add optional headers that can be uploaded.

# All headers that can be in a Customer Match CSV.
ALL_HEADERS = REQUIRED_HEADERS.union(OPTIONAL_HEADERS)
DO_NOT_HASH = {"Country", "Zip"}

# ANSI codes to color/format terminal prints.
ANSI = {
    "YELLOW": "\u001b[33m",
    "RED": "\u001b[31m",
    "CYAN": "\u001b[36m",
    "BOLD": "\u001b[1m",
    "RESET": "\u001b[0m",
}


class Error(ValueError):
    """Base class for other custom exceptions"""

    pass


class FormatError(Error):
    """Raised when a file is not in the correct format."""

    pass


class NoZipError(FormatError):
    """Raised when a zip code is not found in a spreadsheet. Sometimes recoverable."""

    pass


# ==========================
# Formatted console prints
# ==========================


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
        file = open(filepath, encoding="utf8")
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
        ignore_zip (bool): Flag to ignore the zip code column, and not throw an error if it is missing.

    Raises:
        ValueError: If not all required headers can be found

    Returns:
        dict: A map from the field name that was found in the CSV to Google's field name.
                eg: "first_name": "First Name"
    """
    field_map = {}
    found_headers = []
    with open(filepath, "r", encoding="utf8") as file:
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


def parse_location_fields(filepath: str) -> dict:
    """Parse a header of a CSV file to get the country and city.

    Args:
        filepath (str): Path to the CSV file

    Raises:
        FormatError: If the city, country or both columns cannot be found.

    Returns:
        dict: A map from the field name that was found in the CSV to the standardized name.
                eg: "person_city": "City"
    """
    WANTED_FIELDS = {"state", "city"}
    found_translations = []
    field_map = {}
    with open(filepath, "r", encoding="utf8") as file:
        reader = csv.DictReader(file)
        field_names = reader.fieldnames

        for field in field_names:
            # Salesql CSVs prefix state and city by person_.
            field = field.lower()
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
    """Produces a sha256 hash of an element of data.

    Args:
        element (any): The data to be hashed

    Returns:
        str: The sha256 hash hex digest
    """
    element = str(element).encode("utf-8")
    return hashlib.sha256(element).hexdigest()


def hash_series(series: pd.Series):
    """Hashes a series, usually represnting columns in a CSV.

    Args:
        series (pd.Series): [description]

    Returns:
        [type]: [description]
    """
    # If the name of the series is a field
    # that shouldn't be hashed (eg: Zip), don't hash it.
    if series.name in DO_NOT_HASH:
        return series
    else:
        return series.map(hash_element)


def hash_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Hashes all elements in a Pandas dataframe.

    Args:
        dataframe (pd.DataFrame): The dataframe to be hashed

    Returns:
        pd.DataFrame: The dataframe with all elements hashed
    """
    notify(f"Hashing {dataframe.size} elements...")
    start = time.time()
    dataframe = dataframe.apply(hash_series, axis=0)
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
        dtype=str,
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


def get_zip(row: pd.Series, search: SearchEngine) -> str:
    """Get the zip code for a row in a dataframe with the city and state.

    Args:
        row (pd.Series): A series containing a city and state field.
        search (SearchEngine): The search engine object to lookup the zipcode.

    Returns:
        str: The zipcode if found. None otherwise.
    """
    try:
        if row.count() == 2:
            res = search.by_city_and_state(city=row["city"], state=row["state"])
            return res[0].zipcode
        else:
            warn(f"NaN detected for {row['city']}, {row['state']}.")
            return ""
    except (AttributeError, IndexError):
        warn(f"Zip lookup for {row['city']}, {row['state']} failed.")
        return ""


def get_zips(dataframe: pd.DataFrame) -> pd.Series:
    """Gets the zips for a dataframe with city and state columns.

    Args:
        dataframe (pd.DataFrame): The dataframe, must have city and state columns.

    Returns:
        pd.Series: A series of zip codes correlating to the zips for each city and state.
    """
    search = SearchEngine()
    tqdm.pandas(desc="Getting zipcodes")
    zips = dataframe.progress_apply(lambda row: get_zip(row, search), axis=1)
    zips = zips.rename("Zip")
    return zips


def convert_to_iso(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Converts a dataframe's Country column to ISO2 format (United States => US)

    Args:
        dataframe (pd.DataFrame): A dataframe with a Country column.

    Returns:
        pd.DataFrame: The dataframe with the Country column in ISO2 format.
    """
    notify(f"Converting {len(dataframe.index)} countries to ISO2 format...")
    start = time.time()
    iso2_names = coco.convert(names=dataframe["Country"], to="ISO2", not_found=None)
    dataframe["Country"] = pd.Series(iso2_names)
    notify(
        f"Finished converting countries to ISO2 format in {time.time() - start} seconds."
    )
    return dataframe


def normalize_series(column: pd.Series) -> pd.Series:
    """Formats a series (usually a column) of strings to be all lowercase and without whitespace.

    Args:
        column (pd.Series): The series of strings to be normalized

    Returns:
        pd.Series: The same series, with normalized strings.
    """

    def format(el: str) -> str:
        el = el.strip()
        el = el.lower()
        return el

    return column.map(format)


def get_e164(row: pd.Series) -> str:
    """Takes a series containing a Phone and Country column and returns the
        phone number in E.164 format.


    Args:
        row (pd.Series): A series containing at least a Phone and Country column.

    Returns:
        str: The phone number in E.164 format, if it could be formatted.
                None otherwise.
    """
    if row.count() == 2:
        try:
            number = phonenumbers.parse(row["Phone"], row["Country"])
            return phonenumbers.format_number(
                number, phonenumbers.PhoneNumberFormat.E164
            )
        except phonenumbers.NumberParseException:
            warn(
                f"Can't parse phone number {row['Phone']} for country {row['Country']}. It is not recognized as a valid number."
            )
            return None
    else:
        # warn(
        #     f"Can't convert phone number {row['Phone']} for country {row['Country']} due to missing data."
        # )
        return None


def convert_to_e164(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Converts a dataframe's Phone column to E.164. Requires a Country column.

    Args:
        dataframe (pd.DataFrame): A dataframe with a Phone and Country column

    Returns:
        pd.DataFrame: The same dataframe with the Phone column reformatted to E.164.
    """
    tqdm.pandas(desc="Converting phone numbers to E.164 format")
    numbers = dataframe[["Country", "Phone"]].progress_apply(get_e164, axis=1)
    dataframe["Phone"] = numbers
    return dataframe


def format_for_hashing(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Performs formatting on a dataframe necessary for accurate hashing.
        Will convert the Country column to ISO, normalize all strings, and convert
        the phone number column to E.164 format.

    Args:
        dataframe (pd.DataFrame): A dataframe to be formatted

    Returns:
        pd.DataFrame: The same dataframe formatted. May have many NaN values!
    """
    notify("Formatting file for hashing...")
    dataframe = dataframe.apply(normalize_series, axis=0)
    dataframe = convert_to_iso(dataframe)
    dataframe = convert_to_e164(dataframe)
    notify("Done formatting file.")
    return dataframe


def prune(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Drops any rows in a dataframe that contain NaN, and prints
        how many rows were affected.

    Args:
        dataframe (pd.DataFrame): Dataframe to be pruned

    Returns:
        pd.DataFrame: Same dataframe without rows that have NaN.
    """
    total_rows = len(dataframe.index)
    notify(f"Removing rows with empty values...")
    dataframe = dataframe.dropna()
    pruned_rows = len(dataframe.index)
    notify(f"Removed {total_rows - pruned_rows} rows with empty values.")
    return dataframe


@click.command(
    help="Generates a Google Ads Customer Match compliant CSV file from a (potentially large) CSV file in another format."
)
@click.option("-o", "--output", default="result.csv", help="Path to output file.")
@click.option(
    "--hash",
    "do_hash",
    help="SHA256 hash each element in the resulting CSV.",
    is_flag=True,
)
@click.option(
    "--ignore-empty",
    help="Don't remove rows with empty elements.",
    is_flag=True,
)
@click.option(
    "--format",
    help="Format the document as it would before hashing with E.164 phone numbers and lowercase names. Will remove a significant amount of rows.",
    is_flag=True,
)
@click.argument("filepath")
def main(
    filepath: str, output: str, do_hash: bool, ignore_empty: bool, format: bool
):
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
                "A zip code column could not be found in the CSV file. If there is a state and city column, the zip codes may be able to be automatically detected. This may take hours, depending on your file size."
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

        if not ignore_empty:
            file = prune(file)

        # Format the file for hashing if we are going to hash.
        # Country codes are converted to ISO as a step in hashing, so
        # we only have to convert if we are not hashing.
        if do_hash or format:
            file = format_for_hashing(file)
        else:
            file = convert_to_iso(file)

        # Check again for empty values, if phone numbers can't be formatted
        # or ISO formats can't be found.
        if not ignore_empty:
            file = prune(file)

        # Hashing must be the last step, or else NaN will be hashed.
        if do_hash:
            file = hash_dataframe(file)

        save_csv(file, output)
        return 0
    except ValueError as e:
        sys.exit(f"{ANSI['BOLD'] + ANSI['RED']}ERROR:{ANSI['RESET']} {e}")


if __name__ == "__main__":
    main()