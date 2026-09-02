import os, sqlite3
import pandas as pd

conn = None
try: 
    os.makedirs("db", exist_ok=True)
    conn = sqlite3.connect("db/weather.db")

    df = pd.read_csv("data/processed/weather_clean.csv")
    df.to_sql("weather_clean", conn, if_exists="replace", index=False)

    raw_df = pd.read_csv("data/raw/weather_raw.csv")
    raw_df.to_sql("weather_raw", conn, if_exists="replace", index=False)

    summary_df = pd.read_csv("data/processed/country_summary.csv")
    summary_df.to_sql("country_summary", conn, if_exists="replace", index=False)    

    print("Tables created successfully in the database.")


except Exception as e:
    print(f"Error occurred while creating the table: {e}")

finally:
    if conn is not None:
        conn.close()
