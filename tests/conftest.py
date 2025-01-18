import pytest
import time
import os
from pathlib import Path
import sys

cur_dir = Path(__file__).parent
config_file_path = cur_dir.parent / "config.toml"

os.environ["ENV_FILE"] = config_file_path.as_posix()
# ../src
sys.path.insert(0, str(cur_dir.parent / "src"))


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    start_time = time.time()
    _ = yield
    end_time = time.time()
    duration = end_time - start_time
    print(f"\n{item.nodeid} took {duration:.4f} seconds")
