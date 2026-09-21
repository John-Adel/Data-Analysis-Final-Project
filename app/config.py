import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "dbname": os.getenv("POSTGRES_DB", "fordgobike"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
}

password = os.getenv("POSTGRES_PASSWORD")
if password:
    DATABASE_CONFIG["password"] = password

DATABASE_SCHEMA = os.getenv("POSTGRES_SCHEMA", "fordgobike")