# Customer Match Translator

A simple command line program to translate a CSV containing customer contact information to Google's required [Customer Match](https://support.google.com/google-ads/answer/7659867) data format. Written using Python 3. Has options to allow for hashing of the data before exporting it to a CSV.

## Usage

1. Clone repository:

```sh
git clone https://github.com/Esquire-Digital/customer-match-tool.git
cd customer-match-tool
```

2. Install required packages:

```sh
pip install -r requirements.txt
```

3. Allow execution of the file (Linux/macOS only)

```sh
chmod +x customer-match.py
```

4. Run the program on a CSV file:

```sh
./customer-match.py ./file.csv          # Linux/macOS
python3 ./customer-match.py ./file.csv  # All other OS
```

## Options

| Option              | Description                                                                                | Default      |
| ------------------- | ------------------------------------------------------------------------------------------ | ------------ |
| -o, --output (path) | Specify a path for the resulting CSV file.                                                 | `result.csv` |
| --hash              | Flag to hash every element in the file using [sha256](https://en.wikipedia.org/wiki/SHA-2) |              |
| --help              | Display the help message.                                                                  |              |
