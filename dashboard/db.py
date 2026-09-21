import os
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# Grab the Neon URI and format it for SQLAlchemy + psycopg v3
raw_uri = os.getenv("GOBIKE_DB_URI", "")
if raw_uri.startswith("postgresql://"):
    raw_uri = raw_uri.replace("postgresql://", "postgresql+psycopg://", 1)
DB_URI = raw_uri

# Query updated to match your exact PostgreSQL schema columns
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
AGE_LABELS = ["Under 20", "20-29", "30-39", "40-49", "50-59", "60+"]
REGIONS = ["San Francisco", "East Bay", "San Jose"]

def load_data() -> pd.DataFrame:
    from sqlalchemy import create_engine
    engine = create_engine(DB_URI)
    df = pd.read_sql(QUERY, engine)

    df["start_time"] = pd.to_datetime(df["start_time"])
    df["date"] = pd.to_datetime(df["date"])
    df["duration_min"] = df["duration_sec"] / 60
    df["day_of_week"] = pd.Categorical(df["day_of_week"], categories=DAY_ORDER, ordered=True)
    df["weekend_flag"] = df["day_of_week"].isin(["Saturday", "Sunday"])

    df["age_group"] = pd.cut(df["age"], bins=[0, 20, 30, 40, 50, 60, 120],
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