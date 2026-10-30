import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def database_uri():
    configured_uri = os.environ.get("DATABASE_URL")
    if configured_uri:
        if configured_uri.startswith("postgres://"):
            return configured_uri.replace("postgres://", "postgresql://", 1)
        return configured_uri

    database_path = ROOT_DIR / "instance" / "students.db"
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{database_path.as_posix()}"


class Config:
    SQLALCHEMY_DATABASE_URI = database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False
    SECRET_KEY = os.environ.get("SECRET_KEY") or "local-development-key-change-before-deploy"
    ERP_BOOTSTRAP_TOKEN = os.environ.get("ERP_BOOTSTRAP_TOKEN", "")
    TOKEN_MAX_AGE_SECONDS = int(os.environ.get("TOKEN_MAX_AGE_SECONDS", "28800"))
