import csv
from pathlib import Path
import psycopg
from app.database.connection import get_connection

DEFAULT_DATASET = Path(__file__).resolve().parents[2] / "fordgobike_cleaned.csv"
SCHEMA_FILE = Path(__file__).resolve().parents[2] / "sql" / "schema.sql"
SEED_FILE = Path(__file__).resolve().parents[2] / "sql" / "seed.sql"

def initialize_database() -> None:
    with get_connection() as connection:
        connection.execute(SCHEMA_FILE.read_text(encoding="utf-8"))

def load_dataset(csv_path: Path = DEFAULT_DATASET) -> int:
    with csv_path.open("r", encoding="utf-8") as source:
        reader = csv.reader(source)
        raw_headers = next(reader)

    headers = [h.strip().strip('"').strip("'").lower() for h in raw_headers]
    
    col_definitions = ", ".join([f'"{h}" TEXT' for h in headers])
    col_names = ", ".join([f'"{h}"' for h in headers])

    with csv_path.open("r", encoding="utf-8") as source, get_connection() as connection:
        with connection.cursor() as cursor:
            # Clean database
            cursor.execute("TRUNCATE fordgobike.fact_trips, fordgobike.dim_time, fordgobike.dim_user, fordgobike.dim_station RESTART IDENTITY CASCADE")

            # 1. Temporary staging table
            cursor.execute(f"CREATE TEMP TABLE staging_trips ({col_definitions}) ON COMMIT DROP")

            with cursor.copy(f"COPY staging_trips ({col_names}) FROM STDIN WITH (FORMAT csv, HEADER true)") as copy:
                while chunk := source.read(1024 * 1024):
                    copy.write(chunk)

            # Add temporary auto-increment row ID to staging for 1-to-1 mapping
            cursor.execute("ALTER TABLE staging_trips ADD COLUMN staging_id SERIAL PRIMARY KEY")

            # 2. Seed dummy records
            if SEED_FILE.exists():
                cursor.execute(SEED_FILE.read_text(encoding="utf-8"))
                cursor.execute("SELECT setval('fordgobike.dim_user_user_id_seq', COALESCE((SELECT MAX(user_id) FROM fordgobike.dim_user), 1));")
                cursor.execute("SELECT setval('fordgobike.dim_time_time_id_seq', COALESCE((SELECT MAX(time_id) FROM fordgobike.dim_time), 1));")

            # 3. Insert unique stations
            cursor.execute("""
                INSERT INTO fordgobike.dim_station (station_id, station_name, station_latitude, station_longitude)
                SELECT DISTINCT station_id, station_name, station_latitude, station_longitude
                FROM (
                    SELECT NULLIF(start_station_id, '')::INT AS station_id, start_station_name AS station_name,
                           NULLIF(start_station_latitude, '')::NUMERIC AS station_latitude, NULLIF(start_station_longitude, '')::NUMERIC AS station_longitude
                    FROM staging_trips
                    UNION
                    SELECT NULLIF(end_station_id, '')::INT, end_station_name,
                           NULLIF(end_station_latitude, '')::NUMERIC, NULLIF(end_station_longitude, '')::NUMERIC
                    FROM staging_trips
                ) s WHERE station_id IS NOT NULL ON CONFLICT (station_id) DO NOTHING;
            """)

            # 4. Insert unique user profiles from CSV
            cursor.execute("""
                INSERT INTO fordgobike.dim_user (user_type, member_birth_year, member_gender)
                SELECT DISTINCT 
                    COALESCE(NULLIF(user_type, ''), 'Subscriber'), 
                    NULLIF(member_birth_year, '')::NUMERIC::INT, 
                    COALESCE(NULLIF(member_gender, ''), 'Unknown')
                FROM staging_trips
                EXCEPT
                SELECT user_type, member_birth_year, member_gender FROM fordgobike.dim_user;
            """)

            # 5. Insert timestamps into dim_time
            cursor.execute("""
                INSERT INTO fordgobike.dim_time (start_time, date, hour, day, day_of_week, month, year)
                SELECT DISTINCT 
                    start_time::TIMESTAMP,
                    start_time::TIMESTAMP::DATE,
                    EXTRACT(HOUR FROM start_time::TIMESTAMP)::INT,
                    EXTRACT(DAY FROM start_time::TIMESTAMP)::INT,
                    TO_CHAR(start_time::TIMESTAMP, 'Day'),
                    EXTRACT(MONTH FROM start_time::TIMESTAMP)::INT,
                    EXTRACT(YEAR FROM start_time::TIMESTAMP)::INT
                FROM staging_trips
                WHERE NULLIF(start_time, '') IS NOT NULL
                ON CONFLICT (start_time) DO NOTHING;
            """)

            # 6. Insert fact_trips ensuring exactly 1 record per staging row
            cursor.execute("""
                INSERT INTO fordgobike.fact_trips (
                    start_time, end_time, duration_sec, duration_min,
                    start_station_id, end_station_id, bike_id, user_id, time_id, bike_share_for_all_trip
                )
                SELECT DISTINCT ON (s.staging_id)
                    NULLIF(s.start_time, '')::TIMESTAMP, 
                    NULLIF(s.end_time, '')::TIMESTAMP, 
                    NULLIF(s.duration_sec, '')::NUMERIC::INT, 
                    NULLIF(s.duration_min, '')::NUMERIC,
                    NULLIF(s.start_station_id, '')::NUMERIC::INT, 
                    NULLIF(s.end_station_id, '')::NUMERIC::INT, 
                    NULLIF(s.bike_id, '')::NUMERIC::INT, 
                    u.user_id, 
                    t.time_id,
                    s.bike_share_for_all_trip
                FROM staging_trips s
                LEFT JOIN fordgobike.dim_user u ON COALESCE(NULLIF(s.user_type, ''), 'Subscriber') = u.user_type 
                    AND COALESCE(NULLIF(s.member_birth_year, '')::NUMERIC::INT, -1) = COALESCE(u.member_birth_year, -1)
                    AND COALESCE(NULLIF(s.member_gender, ''), 'Unknown') = COALESCE(u.member_gender, 'Unknown')
                LEFT JOIN fordgobike.dim_time t ON NULLIF(s.start_time, '')::TIMESTAMP = t.start_time
                ORDER BY s.staging_id, u.user_id ASC;
            """)

            cursor.execute("SELECT COUNT(*) FROM fordgobike.fact_trips")
            return cursor.fetchone()[0]