import os
from pathlib import Path
import pandas as pd

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "fordgobike_cleaned.csv"
DB_URI = os.getenv("GOBIKE_DB_URI")

QUERY = """
SELECT f.trip_id, f.start_time, f.end_time, f.duration_sec, f.bike_id,
       s1.station_name AS start_station, s1.latitude AS start_lat, s1.longitude AS start_lng,
       s2.station_name AS end_station,   s2.latitude AS end_lat,   s2.longitude AS end_lng,
       u.age, u.gender, u.user_type,
       t.date, t.hour, t.day_of_week, t.month, t.year
FROM fact_trips f
JOIN dim_station s1 ON f.start_station_id = s1.station_id
JOIN dim_station s2 ON f.end_station_id   = s2.station_id
JOIN dim_user    u  ON f.user_id          = u.user_id
JOIN dim_time    t  ON f.time_id          = t.time_id
"""

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
AGE_LABELS = ["Under 20", "20-29", "30-39", "40-49", "50-59", "60+"]
REGIONS = ["San Francisco", "East Bay", "San Jose"]


def _from_csv() -> pd.DataFrame:
    raw = pd.read_csv(CSV_PATH)
    return pd.DataFrame({
        "trip_id": raw.index + 1,
        "start_time": pd.to_datetime(raw["start_time"]),
        "end_time": pd.to_datetime(raw["end_time"]),
        "duration_sec": raw["duration_sec"],
        "bike_id": raw["bike_id"],
        "start_station": raw["start_station_name"],
        "start_lat": raw["start_station_latitude"],
        "start_lng": raw["start_station_longitude"],
        "end_station": raw["end_station_name"],
        "end_lat": raw["end_station_latitude"],
        "end_lng": raw["end_station_longitude"],
        "age": raw["age"],
        "gender": raw["member_gender"],
        "user_type": raw["user_type"],
        "date": pd.to_datetime(raw["start_date"]),
        "hour": raw["start_hour"],
        "day_of_week": raw["day_of_week"],
        "month": raw["start_month"],
        "year": pd.to_datetime(raw["start_date"]).dt.year,
    })


def _from_postgres() -> pd.DataFrame:
    from sqlalchemy import create_engine
    return pd.read_sql(QUERY, create_engine(DB_URI))


def load_data() -> pd.DataFrame:
    df = _from_postgres() if DB_URI else _from_csv()

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

    # Service area, derived from the start station's coordinates
    df["region"] = "San Francisco"
    df.loc[df["start_lng"] > -122.33, "region"] = "East Bay"
    df.loc[df["start_lat"] < 37.5, "region"] = "San Jose"

    # Categoricals keep filtering fast on ~180k rows
    for col in ["start_station", "end_station", "user_type", "gender", "age_group", "region"]:
        df[col] = df[col].astype("category")
    return df


df = load_data()
