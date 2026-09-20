# Ford GoBike Data Analysis Pipeline & Dashboard

## Project Overview
This repository contains a comprehensive data analysis and visualization pipeline for the 2019 Ford GoBike sharing system. Developed by a collaborative six-person team for the Digital Egypt Pioneers Initiative (DEPI) Data Science module, the project demonstrates an end-to-end analytical workflow spanning database architecture, rigorous data preprocessing, and dynamic business intelligence visualization. The repository is structured to reflect general data science best practices, ensuring scalability, reproducibility, and clear analytical narratives.

## Architecture & Tech Stack
* **Database:** PostgreSQL
* **Data Manipulation & Analysis:** Python, pandas, NumPy
* **Visualization:** Matplotlib, Seaborn, Plotly
* **Dashboarding:** Plotly Dash / Streamlit
* **Version Control:** Git & GitHub

## Project Phases

### 1. Relational Database Design
The raw dataset is modeled into a robust star schema to optimize query performance and enforce data integrity. 
* **Fact Table:** `fact_trips` (trip metrics and foreign keys).
* **Dimension Tables:** `dim_time`, `dim_station`, `dim_user` (categorical and temporal attributes).
* **Integration:** Includes a lightweight Python GUI (PyQt5/Streamlit) for direct database connection and sample record querying.

### 2. Preprocessing & Exploratory Data Analysis (EDA)
Raw trip data undergoes systematic cleaning and feature engineering to prepare for statistical analysis.
* **Data Cleaning:** Domain-specific handling of missing identifiers, categorical standardization, and removal of extreme demographic outliers.
* **Feature Engineering:** Derivation of actionable features, including trip duration in minutes, weekend flags, and targeted age grouping.
* **Visual Analysis:** Comprehensive univariate, bivariate, and multivariate analysis examining trip distributions, user demographics (Subscribers vs. Customers), and temporal riding patterns.

### 3. Interactive Business Intelligence Dashboard
A dynamic, user-facing dashboard designed for filtering and slicing core bike-sharing metrics.
* **Overview KPIs:** Total trips, average duration, active user count, and top stations.
* **Time Analysis:** Trip volume by day of the week, monthly trends, and weekday vs. hour heatmaps.
* **User Analysis:** Demographic breakdowns by user type, gender, and age distribution.
* **Station Flow:** Geospatial bubble maps and bar charts detailing the most heavily trafficked stations and popular routes.

## Setup & Installation
1. Clone the repository to your local machine:
   ```bash
   git clone [https://github.com/yourusername/ford-gobike-analysis.git](https://github.com/yourusername/ford-gobike-analysis.git)
