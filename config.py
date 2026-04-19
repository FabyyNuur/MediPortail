import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DEFAULT_DATA_PATH = os.path.join(BASE_DIR, "data", "hospital_data.csv")


def get_data_path() -> str:
    return os.environ.get("HOSPITAL_DATA_PATH", DEFAULT_DATA_PATH)
