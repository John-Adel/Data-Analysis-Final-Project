-- Seed dummy rows into dim_station
INSERT INTO fordgobike.dim_station (station_id, station_name, station_latitude, station_longitude) VALUES 
    (7, 'Embarcadero at Sansome', 37.804770, -122.403234),
    (93, '4th St at Mission Bay', 37.770407, -122.391198),
    (222, '10th St at University Ave', 37.869060, -122.289343),
    (323, 'Broadway at 40th St', 37.829822, -122.257195)
ON CONFLICT (station_id) DO NOTHING;

-- Seed dummy rows into dim_user
INSERT INTO fordgobike.dim_user (user_id, member_birth_year, member_gender, user_type) VALUES 
    (4898, 1980, 'Male', 'Customer'),
    (5200, 1992, 'Female', 'Subscriber'),
    (6432, 1995, 'Male', 'Subscriber'),
    (1123, 1988, 'Other', 'Customer')
ON CONFLICT (user_id) DO NOTHING;

-- Seed dummy rows into dim_time
INSERT INTO fordgobike.dim_time (time_id, start_time, date, hour) VALUES 
    (201902281, '2019-02-28 01:00:00'::TIMESTAMP, '2019-02-28'::DATE, 1),
    (201902282, '2019-02-28 02:00:00'::TIMESTAMP, '2019-02-28'::DATE, 2),
    (201902283, '2019-02-28 03:00:00'::TIMESTAMP, '2019-02-28'::DATE, 3),
    (201902284, '2019-02-28 04:00:00'::TIMESTAMP, '2019-02-28'::DATE, 4)
ON CONFLICT (time_id) DO NOTHING;