# Customer Match Translator

A simple command line program to translate a CSV containing customer contact information to Google's [Customer Match](https://support.google.com/google-ads/answer/7659867) data format. Written using Python 3. Has options to allow for hashing of the data before exporting it to a CSV.

## Usage

Install package:

```sh
pip install customer-match-tool
```

Translate a CSV file for plain-text upload to `result.csv`:

```sh
customer-match-translator mycontacts.csv
```

Translate a CSV file for plain-text upload to custom destination:

```sh
customer-match-translator mycontacts.csv --output ~/output.csv
```

Translate a CSV file and hash the contents:

```sh
customer-match-translator --hash mycontacts.csv
```

## File Requirements

The CSV file _must_ have the following fields for the translator to work:

- `First Name`
- `Last Name`
- `Phone`
- `Email`
- `Country`
- `Zip` (optional if [inferring](#inferring-zip-codes))

The CSV file can have any number of extra fields. They will not be evaluated, and will not show up in the final output.

## Inferring Zip Codes

While a Zip field is required for Google, you may not always have access to the customer's zipcode. If you have access to the customer's state and city, the program can try to infer the zipcode. If the CSV has a `state` and `city` column, run the translator as you would normally:

```sh
customer-match-translator mycontacts.csv
```

The CLI will prompt you, asking you if you would like to try to infer the zipcodes.

```console
WARNING: A zip code column could not be found in the CSV file. If there is a state and city column, the zip codes may be able to be automatically detected. This may take hours, depending on your file size.
Would you like to try to detect zip codes? [y/N]: y
```

Inferring zipcodes can take a _very_ long time. It may be best to split your contact files into smaller chunks, in case anything goes wrong or times out.

The console will warn you if a zipcode cannot be looked up. It is important to note that there can be many zipcodes in one city, and the program will pick one at random if there exist more than one.

## Examples

All examples will use a small CSV with only two entries called `mycontacts.csv`:

| first_name | last_name | email              | state      | city        | country       | phone           | notes              |
| ---------- | --------- | ------------------ | ---------- | ----------- | ------------- | --------------- | ------------------ |
| Dorothy    | Gale      | dgale@emerald.city | New Jersey | Hoboken     | United States | +1 555-362-2520 | Loves her dog Toto |
| John       | Doe       | jdoe@hotmail.com   | NJ         | Jersey City | United States | +1 555-894-2405 | Doesn't talk much  |

You can also find this file in `examples/mycontacts.csv`.

### Plaintext Translation

By default, the formatter will strip all columns not needed by Google and format country names or codes in [ISO2](https://en.wikipedia.org/wiki/ISO_2) format.

It will also attempt to translate snake case to the Google alternative. For example, `first_name` would be picked up as `First Name`, and translated accordingly.

Command:

```sh
customer-match-translator mycontacts.csv
```

Output (`examples/plaintext-translation.csv`):

| First Name | Last Name | Email              | State      | City        | Country       | Phone           |
| ---------- | --------- | ------------------ | ---------- | ----------- | ------------- | --------------- |
| Dorothy    | Gale      | dgale@emerald.city | New Jersey | Hoboken     | United States | +1 555-362-2520 |
| John       | Doe       | jdoe@hotmail.com   | NJ         | Jersey City | United States | +1 555-894-2405 |

## Options

| Option              | Description                                                                                                                                                                                                              | Default      |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------ |
| -o, --output (path) | Specify a path for the resulting CSV file.                                                                                                                                                                               | `result.csv` |
| --hash              | Flag to hash every element in the file using [sha256](https://en.wikipedia.org/wiki/SHA-2)                                                                                                                               |              |
| --help              | Display the help message.                                                                                                                                                                                                |              |
| --format            | Flag to format the resulting CSV as it would be formatted before hashing. Will lowercase all strings, strip them of whitespace, convert the country column to ISO2 format, and convert the phone number to E.164 format. |              |
