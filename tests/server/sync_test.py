import pytest
from faker import Faker

from syftbox.server.sync.hash import (
    collect_files,
    hash_file,
    hash_files_parallel,
)

TEST_DATASITE_NAME = "test_datasite@openmined.org"
TEST_FILE = "test_file.txt"
PERMFILE_FILE = "_.syftperm"
PERMFILE_DICT = {
    "admin": [TEST_DATASITE_NAME],
    "read": ["GLOBAL"],
    "write": [TEST_DATASITE_NAME],
}

faker = Faker()


@pytest.fixture
def fake_file(tmp_path):
    """Create a fake file with random content."""
    file_path = tmp_path / faker.file_name()
    content = faker.text()
    with open(file_path, "wb") as f:
        f.write(content.encode("utf-8"))
    return file_path


@pytest.fixture
def fake_dir(tmp_path):
    """Create a directory with several fake files."""
    dir_path = tmp_path / faker.word()
    dir_path.mkdir()
    for _ in range(5):  # Create 5 files
        file_path = dir_path / faker.file_name()
        content = faker.text()
        with open(file_path, "wb") as f:
            f.write(content.encode("utf-8"))
    return dir_path


def test_file_hash(fake_file):
    """Test that file_hash returns the correct hash."""
    file_path, file_hash_result = hash_file(fake_file)
    assert file_path == str(fake_file), "File path should match the input file path."
    assert file_hash_result is not None, "Hash should not be None."


def test_hash_dir(fake_dir):
    """Test that hash_dir processes all files in a directory."""
    files = collect_files(fake_dir)
    results = hash_files_parallel(files)
    assert len(results) == 5, "Should process exactly 5 files."
    for result in results:
        assert result[1] is not None, "None of the hashes should be None."


def test_file_hash_failure(tmp_path):
    """Test file_hash with a non-existent file."""
    non_existent_file = tmp_path / "nonexistent.txt"
    path, hash_result = hash_file(non_existent_file)
    assert hash_result is None, "Hash should be None for non-existent files."
