HEADER_TRANSLATIONS = {
    "email1": "Email",
    "phone1": "Phone",
    "person_country": "Country",
}

REQUIRED_HEADERS = {"First Name", "Last Name", "Phone", "Email", "Country", "Zip"}
OPTIONAL_HEADERS = set()  # TODO: Add optional headers that can be uploaded.

# All headers that can be in a Customer Match CSV.
ALL_HEADERS = REQUIRED_HEADERS.union(OPTIONAL_HEADERS)

# ANSI codes to color/format terminal prints.
ANSI = {
    "YELLOW": "\u001b[33m",
    "RED": "\u001b[31m",
    "CYAN": "\u001b[36m",
    "BOLD": "\u001b[1m",
    "RESET": "\u001b[0m",
}