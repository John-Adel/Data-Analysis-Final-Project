CREATE SCHEMA IF NOT EXISTS fordgobike;

DROP TABLE IF EXISTS fordgobike.fact_trips CASCADE;
DROP TABLE IF EXISTS fordgobike.dim_time CASCADE;
DROP TABLE IF EXISTS fordgobike.dim_user CASCADE;
DROP TABLE IF EXISTS fordgobike.dim_station CASCADE;

CREATE TABLE fordgobike.dim_station (
    station_id INT PRIMARY KEY,
    station_name VARCHAR(255),
    station_latitude NUMERIC(10, 6),
    station_longitude NUMERIC(10, 6)
);

CREATE TABLE fordgobike.dim_user (
    user_id SERIAL PRIMARY KEY,
    user_type VARCHAR(50),
    member_birth_year INT,
    member_gender VARCHAR(20)
);

CREATE TABLE fordgobike.dim_time (
    time_id SERIAL PRIMARY KEY,
    start_time TIMESTAMP UNIQUE,
    date DATE,
    hour INT,
    day INT,
    day_of_week VARCHAR(20),
    month INT,
    year INT
);

CREATE TABLE fordgobike.fact_trips (
    trip_id SERIAL PRIMARY KEY,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    duration_sec INT,
    duration_min NUMERIC(10, 2),
    start_station_id INT REFERENCES fordgobike.dim_station(station_id),
    end_station_id INT REFERENCES fordgobike.dim_station(station_id),
    bike_id INT,
    user_id INT REFERENCES fordgobike.dim_user(user_id),
    time_id INT REFERENCES fordgobike.dim_time(time_id),
    bike_share_for_all_trip VARCHAR(10)
);