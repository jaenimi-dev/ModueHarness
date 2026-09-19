from setuptools import find_packages, setup

setup(
    name="modue-harness",
    version="0.5.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
)
