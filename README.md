# Customer Match Translator

A simple command line program to translate a CSV containing customer contact information to Google's [Customer Match](https://support.google.com/google-ads/answer/7659867) data format. Written using Python 3. Has options to allow for hashing of the data before exporting it to a CSV.

## Usage

Install package:

```sh
pip install customer-match-tool
```

Run the program on a CSV file:

```sh
./customer-match.py ./file.csv          # Linux/macOS
python3 ./customer-match.py ./file.csv  # All other OS
```

## File Requirements

The CSV file _must_ have field types that map to these required Google fields:

- First Name
- Last Name
- Phone
- Email
- Country
- Zip

If a field type is not automatically picked up but exists in the CSV, you can add it to the [translations dictionary](#translations).

## Options

| Option              | Description                                                                                                                                                                                                              | Default      |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------ |
| -o, --output (path) | Specify a path for the resulting CSV file.                                                                                                                                                                               | `result.csv` |
| --hash              | Flag to hash every element in the file using [sha256](https://en.wikipedia.org/wiki/SHA-2)                                                                                                                               |              |
| --help              | Display the help message.                                                                                                                                                                                                |              |
| --format            | Flag to format the resulting CSV as it would be formatted before hashing. Will lowercase all strings, strip them of whitespace, convert the country column to ISO2 format, and convert the phone number to E.164 format. |              |

## Translations

The program will automatically match snake case field types to their Google alternatives. For example, if a field name in the header of your CSV file is `first_name`, it will match against the Google field `First Name`.

To add manual translations, edit the translation dictionary located in `constants.py`:

```python
# constants.py
HEADER_TRANSLATIONS = {
    "email1": "Email",
    "phone1": "Phone",
    "person_country": "Country",
    "custom_email_field_name": "Email",
}
```

Be sure that the translated value is a valid field type. The valid field types are below:

- First Name
- Last Name
- Phone
- Email
- Country
- Zip
- Mobile Device ID
