"""Explicit live smoke check; not included in unittest discovery."""
from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".runtime/python"))
sys.path.insert(0, str(ROOT))
from pipeline.core import PipelineError, download_x, new_job, save_job

parser = argparse.ArgumentParser()
parser.add_argument("url")
args = parser.parse_args()
directory, data = new_job()
data["source_url"] = args.url
save_job(directory, data)
print("DOWNLOAD_TEST_JOB=" + str(directory), flush=True)
try:
    download_x(directory, data)
except PipelineError as exc:
    print("NEEDS_MANUAL: " + str(exc), flush=True)
    raise SystemExit(2)
print("DOWNLOAD_OK", flush=True)
