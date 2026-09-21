from collections.abc import Iterator
from contextlib import contextmanager
import psycopg
from app.config import DATABASE_CONFIG, DATABASE_SCHEMA
import os

@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    uri = os.getenv("GOBIKE_DB_URI")
    connection = psycopg.connect(uri) if uri else psycopg.connect(**DATABASE_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('search_path', %s, false)", (f"{DATABASE_SCHEMA}, public",))
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()