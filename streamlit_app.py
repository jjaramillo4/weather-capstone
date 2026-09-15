import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from pathlib import Path

st.set_page_config(page_title="Weather Data Capstone", layout="wide")

st.title("World Weather Snapshot: August 25th, 2026")

st.markdown(
    "Current conditions for 140 cities in 92 countries, scraped from "
    "timeanddate.com on August 25th, 2026. Use the slider to change how many "
    "cities appear in the ranking."
)
@st.cache_data
def load_data():
    conn = sqlite3.connect(Path(__file__).parent / "db" / "weather.db")
    df = pd.read_sql("SELECT * FROM weather_clean", conn)
    conn.close()
    return df

weather_df = load_data()

picked = st.sidebar.multiselect("Sky conditions", sorted(weather_df.condition_group.unique()))
lo, hi = st.sidebar.slider("Temperature range (°F)", 40, 108, (40, 108))

mask = weather_df["temp_f"].between(lo, hi)

if picked:
    mask = mask & weather_df["condition_group"].isin(picked)

filtered_df = weather_df[mask]

if filtered_df.empty:
    st.warning("No cities match these filters. Widen the temperature range or pick more sky conditions")
    st.stop()

conditions = ", ".join(picked) if picked else "all sky conditions"
st.caption(
    f"Filtered to {len(filtered_df)} of {len(weather_df)} cities · "
    f"{lo}–{hi}°F · {conditions} "
)

c1, c2, c3, c4 = st.columns(4)

c1.metric("Cities shown", len(filtered_df))
c2.metric("Countries", filtered_df["country"].nunique())
c3.metric("Median temp", f"{filtered_df['temp_f'].median():.0f} °F")

hottest = filtered_df.loc[filtered_df["temp_f"].idxmax()]
c4.metric("Hottest", f"{hottest['temp_f']:.0f} °F", hottest["city"], delta_color="off")

tab1, tab2, tab3 = st.tabs(["Rankings", "Heat & humidity", "Distribution"])

with tab1:
    n = st.slider("Number of cities to display", min_value = 1, max_value = 25, value = 10)
    order = st.radio("Show",["Hottest", "Coldest"], horizontal=True)

    if order == "Hottest" :
     sort_values = False
    else:
     sort_values = True


    fig = px.bar(filtered_df.sort_values("temp_f", ascending = sort_values).head(n), x="city", y="temp_f", labels={"temp_f": "Temperature (°F)", "city": "City"}, title=f"Top {n} {order} Cities")
    fig.update_traces(marker_color="#2a78d6")
    st.plotly_chart(fig)

    if order == "Hottest":
        st.markdown(
            "The hot end of the list is desert and Gulf coast. Phoenix and Las "
            "Vegas lead at 108°F and 106°F in very dry air, with Dubai, Baghdad "
            "and Kuwait City close behind. This chart ranks the raw thermometer "
            "reading, which is why Doha sits mid pack here at 91°F even though "
            "it is the most punishing city in the set once humidity is counted. "
            "The **Heat & humidity** tab shows why."
        )
    else:
        st.markdown(
            "The cold end has three separate causes. La Paz is the coldest city "
            "in the snapshot at 40°F because it sits high in the Andes. Anadyr "
            "and Reykjavik are cold by latitude. Montevideo and Antananarivo are "
            "cold by season: both are in the southern hemisphere, where late "
            "August is winter."
        )

with tab2:
    fig2 = px.scatter(
    filtered_df,
    x="temp_f",
    y="humidity_pct",
    color="feels_like_gap_f",
    color_continuous_scale="RdBu_r",
    color_continuous_midpoint=0,
    hover_name="city",
    hover_data=["feels_like_f", "condition"],
    labels={
        "feels_like_f": "Feels like (°F)",
        "temp_f": "Temperature (°F)",
        "humidity_pct": "Humidity (%)",
        "feels_like_gap_f": "Feels-like gap (°F)",
    },
    title="Humidity, not heat, drives how hot it feels",
    )
    st.plotly_chart(fig2)

    st.markdown(
     "Each dot is a city. **Red means it feels hotter than the thermometer says; "
     "blue means it feels cooler.** Doha is 91°F but feels like 123°F, a 32-degree "
     "gap at 84% humidity. Phoenix, the hottest city in the set at 108°F, actually "
     "feels *cooler* than it reads at 13% humidity. The red cluster sits in the "
     "humid upper-right, not along the hot right edge. Humidity drives the gap, "
     "not temperature."
)

with tab3:
    fig3 = px.histogram(
    filtered_df,
    x = "temp_f",
    nbins = 20,
    labels = {"temp_f": "Temperature (°F)"},
    title = "How temperatures are spread across the snapshot",
)
    fig3.update_layout(yaxis_title = "Number of cities")
    fig3.update_traces(marker_color = "#2a78d6")
    st.plotly_chart(fig3)

    st.markdown(
        f"Each bar counts the cities inside a roughly 3.5°F band. The current "
        f"slice runs {filtered_df['temp_f'].min():.0f}°F to "
        f"{filtered_df['temp_f'].max():.0f}°F, with a median of "
        f"{filtered_df['temp_f'].median():.0f}°F.\n\n"
        "Across the full snapshot the spread is tighter than 92 countries in "
        "both hemispheres would suggest: **73% of the 140 cities fall between "
        "60°F and 90°F**. The tails are thin and specific. Only Phoenix and "
        "Las Vegas clear 100°F. The five cities below 50°F are cold for three "
        "different reasons: altitude (La Paz), latitude (Anadyr, Reykjavik), "
        "and season (Montevideo and Antananarivo are in the southern "
        "hemisphere, where late August is winter)."
    )





