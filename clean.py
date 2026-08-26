"""Clean the scraped weather data and save a tidy CSV.

Reads:  data/raw/weather_raw.csv
Writes: data/processed/weather_clean.csv
        data/processed/country_summary.csv

Usage:
    python clean.py
"""

import os
import re

import pandas as pd

RAW_CSV = os.path.join("data", "raw", "weather_raw.csv")
CLEAN_CSV = os.path.join("data", "processed", "weather_clean.csv")
SUMMARY_CSV = os.path.join("data", "processed", "country_summary.csv")

# Values the site uses to mean "no reading".
MISSING = ["N/A", "n/a", "--", "-", ""]


def number(series):
    """Pull the first number out of each string, e.g. '77 °F' -> 77.0."""
    return pd.to_numeric(series.astype(str).str.extract(r"(-?\d+\.?\d*)")[0],
                         errors="coerce")


def report(df, label):
    """Print row/column counts, duplicates and missing values."""
    print("\n--- %s ---" % label)
    print("rows: %d   columns: %d" % df.shape)
    print("duplicate rows: %d" % df.duplicated().sum())
    missing = df.isna().sum()
    missing = missing[missing > 0]
    if missing.empty:
        print("missing values: none")
    else:
        print("missing values:")
        for col, count in missing.items():
            print("   %-16s %d" % (col, count))


def condition_group(text):
    """Bucket the wordy condition text into a few categories."""
    text = str(text).lower()
    for keyword, group in [("thunder", "Thunderstorm"), ("snow", "Snow"),
                           ("rain", "Rain"), ("shower", "Rain"),
                           ("drizzle", "Rain"), ("fog", "Fog"), ("mist", "Fog"),
                           ("haze", "Haze"), ("overcast", "Overcast"),
                           ("cloud", "Cloudy"), ("sunny", "Clear"),
                           ("clear", "Clear")]:
        if keyword in text:
            return group
    return "Other"


def main():
    df = pd.read_csv(RAW_CSV, na_values=MISSING, keep_default_na=True)
    report(df, "BEFORE cleaning (raw scrape)")
    print("\nraw sample:")
    print(df[["city", "temperature", "feels_like", "forecast", "wind",
              "humidity", "pressure"]].head(3).to_string(index=False))

    # --- 1. drop duplicates and rows with no usable reading ----------------
    df = df.drop_duplicates()
    df = df.drop_duplicates(subset="city_url", keep="first")
    df = df.dropna(subset=["city", "temperature"])

    # --- 2. turn the scraped strings into numbers -------------------------
    df["temp_f"] = number(df["temperature"])
    df["feels_like_f"] = number(df["feels_like"])
    df["humidity_pct"] = number(df["humidity"])
    df["dew_point_f"] = number(df["dew_point"])
    df["pressure_inhg"] = number(df["pressure"])
    df["visibility_mi"] = number(df["visibility"])
    df["wind_mph"] = number(df["wind"])
    # "No wind" has no number in it, but it does mean zero.
    df.loc[df["wind"].astype(str).str.contains("no wind", case=False),
           "wind_mph"] = 0

    # Wind direction, e.g. "12 mph from Southwest" -> "Southwest".
    df["wind_from"] = df["wind"].astype(str).str.extract(
        r"from\s+([A-Za-z-]+)", flags=re.IGNORECASE)[0]

    # Forecast is a single "82 / 76 °F" field -> two columns.
    forecast = df["forecast"].astype(str).str.extract(
        r"(-?\d+\.?\d*)\s*/\s*(-?\d+\.?\d*)")
    df["forecast_high_f"] = pd.to_numeric(forecast[0], errors="coerce")
    df["forecast_low_f"] = pd.to_numeric(forecast[1], errors="coerce")

    # Local hour on a 24-hour clock, from "Wed 3:05 am".
    clock = df["local_time"].astype(str).str.extract(
        r"(\d{1,2}):(\d{2})\s*(am|pm)", flags=re.IGNORECASE)
    hour = pd.to_numeric(clock[0], errors="coerce") % 12
    df["local_hour"] = hour + clock[2].str.lower().eq("pm").mul(12)

    # --- 3. derived columns ----------------------------------------------
    df["temp_c"] = ((df["temp_f"] - 32) * 5 / 9).round(1)
    df["feels_like_gap_f"] = (df["feels_like_f"] - df["temp_f"]).round(1)
    df["forecast_range_f"] = df["forecast_high_f"] - df["forecast_low_f"]
    df["condition_group"] = df["condition"].apply(condition_group)
    df["is_daytime"] = df["local_hour"].between(6, 18)

    # --- 4. drop impossible readings -------------------------------------
    before = len(df)
    df = df[df["temp_f"].between(-100, 140)]
    df.loc[~df["humidity_pct"].between(0, 100), "humidity_pct"] = pd.NA
    print("\ndropped %d row(s) with an out-of-range temperature" % (before - len(df)))

    keep = ["city", "country", "condition", "condition_group", "temp_f", "temp_c",
            "feels_like_f", "feels_like_gap_f", "forecast_high_f", "forecast_low_f",
            "forecast_range_f", "humidity_pct", "dew_point_f", "pressure_inhg",
            "visibility_mi", "wind_mph", "wind_from", "local_hour", "is_daytime",
            "station", "city_url", "scraped_at"]
    df = df[keep].sort_values("city").reset_index(drop=True)

    report(df, "AFTER cleaning")
    print("\nclean sample:")
    print(df[["city", "temp_f", "temp_c", "feels_like_f", "forecast_high_f",
              "humidity_pct", "wind_mph", "condition_group"]].head(3).to_string(index=False))

    # --- 5. group by country ---------------------------------------------
    summary = (df.groupby("country")
                 .agg(cities=("city", "count"),
                      avg_temp_f=("temp_f", "mean"),
                      avg_humidity_pct=("humidity_pct", "mean"),
                      avg_wind_mph=("wind_mph", "mean"))
                 .round(1)
                 .sort_values("avg_temp_f", ascending=False))

    print("\nhottest countries in this snapshot:")
    print(summary.head(5).to_string())

    os.makedirs(os.path.dirname(CLEAN_CSV), exist_ok=True)
    df.to_csv(CLEAN_CSV, index=False, encoding="utf-8")
    summary.to_csv(SUMMARY_CSV, encoding="utf-8")
    print("\nSaved %d rows to %s" % (len(df), CLEAN_CSV))
    print("Saved %d countries to %s" % (len(summary), SUMMARY_CSV))


if __name__ == "__main__":
    main()
