from setuptools import setup, find_packages
setup(
    name = "gaia_uplift",
    version = "0",
    packages = find_packages(),

    entry_points = {
        'console_scripts': [
            'uplift = gaia_uplift.driver:main'
        ]
    },

    package_data = {
        'gaia_uplift': ['*.dat'],
    },

    install_requires = ["isodate",
                        "PrettyTable"],

    # metadata for upload to PyPI
    author = "John Ford",
    author_email = "john@johnford.info",
    description = "This is a program used to uplift bugs from Gaia's master branch to release branches",
    license = "",
    keywords = "hello world example examples",
    url = "",   # project home page, if any

    # could also include long_description, download_url, classifiers, etc.
)
