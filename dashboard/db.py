import os
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

# Load .env from the root project directory
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Build connection details from local environment variables
db_host = os.getenv("POSTGRES_HOST", "localhost")
db_port = os.getenv("POSTGRES_PORT", "5432")
db_name = os.getenv("POSTGRES_DB", "fordgobike")
db_user = os.getenv("POSTGRES_USER", "postgres")
db_pass = os.getenv("POSTGRES_PASSWORD", "PostGrePasswor")

# Construct the SQLAlchemy URI for your local PostgreSQL instance (using psycopg v3 driver)
DB_URI = f"postgresql+psycopg://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"

# Query targeting your local PostgreSQL schema tables
QUERY = """
SELECT f.trip_id, f.start_time, f.end_time, f.duration_sec, f.bike_id,
       s1.station_name AS start_station, s1.station_latitude AS start_lat, s1.station_longitude AS start_lng,
       s2.station_name AS end_station,   s2.station_latitude AS end_lat,   s2.station_longitude AS end_lng,
       (2019 - u.member_birth_year) AS age, u.member_gender AS gender, u.user_type,
       t.date, t.hour, t.day_of_week, t.month, t.year
FROM fordgobike.fact_trips f
JOIN fordgobike.dim_station s1 ON f.start_station_id = s1.station_id
JOIN fordgobike.dim_station s2 ON f.end_station_id   = s2.station_id
JOIN fordgobike.dim_user    u  ON f.user_id          = u.user_id
JOIN fordgobike.dim_time    t  ON f.time_id          = t.time_id
"""

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
AGE_LABELS = ["Young", "Adult", "Senior"]
REGIONS = ["San Francisco", "East Bay", "San Jose"]

def load_data() -> pd.DataFrame:
    engine = create_engine(DB_URI)
    df = pd.read_sql(QUERY, engine)

    df["start_time"] = pd.to_datetime(df["start_time"])
    df["date"] = pd.to_datetime(df["date"])
    df["duration_min"] = df["duration_sec"] / 60
    
    # Strip any trailing spaces coming from PostgreSQL text functions
    df["day_of_week"] = df["day_of_week"].astype(str).str.strip()
    df["day_of_week"] = pd.Categorical(df["day_of_week"], categories=DAY_ORDER, ordered=True)
    
    df["weekend_flag"] = df["day_of_week"].isin(["Saturday", "Sunday"])

    df["age_group"] = pd.cut(df["age"], bins=[0, 30, 50, 120],
                             labels=AGE_LABELS, right=False)
    df["age_group"] = df["age_group"].astype(object).fillna("Unknown")
    df["gender"] = df["gender"].fillna("Unknown")
    df["user_type"] = df["user_type"].fillna("Unknown")

    df["region"] = "San Francisco"
    df.loc[df["start_lng"] > -122.33, "region"] = "East Bay"
    df.loc[df["start_lat"] < 37.5, "region"] = "San Jose"

    for col in ["start_station", "end_station", "user_type", "gender", "age_group", "region"]:
        df[col] = df[col].astype("category")
    return df

df = load_data()


