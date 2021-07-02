from setuptools import setup

with open("DESCRIPTION.txt") as file:
    long_description = file.read()

REQUIREMENTS = [
    "click",
    "pandas",
    "uszipcode",
    "tqdm",
    "phonenumbers",
    "country_converter",
]

# some more details
CLASSIFIERS = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
]

setup(
    name="customer-match-translator",
    version="1.0.2",
    description="A simple command line program to translate a CSV containing customer contact information to Google's Customer Match format.",
    long_description=long_description,
    url="https://github.com/Esquire-Digital/customer-match-tool",
    author="Ryan Hartman",
    author_email="rhartman1239@gmail.com",
    license="MIT",
    # packages=["geo"],
    classifiers=CLASSIFIERS,
    install_requires=REQUIREMENTS,
    keywords="google customer match csv",
)
