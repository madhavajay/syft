from setuptools import findall, setup

# Find all Python files in the current directory
python_files = [
    f[:-3] for f in findall() if f.endswith(".py") and not f.startswith("__")
]

setup(
    py_modules=python_files,
)
