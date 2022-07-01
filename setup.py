from setuptools import setup, find_packages

with open("PeilMerkDB/README.md", "r") as fh:
    long_description = fh.read()

with open("requirements.txt") as requirement_file:
    requirements = requirement_file.read().split()

setup(
    name='peilmerkdb',  
    version='0.1',
    author="Hans Martens",
    author_email="hansmartens@wxs.nl",
    description="Utility for analyzing levelling data (NL)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/tramsnah/PeilMerkDB",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: GPL",
        "Operating System :: OS Independent",
    ],
    install_requires=requirements,
    packages=["PeilMerkDB"]
)