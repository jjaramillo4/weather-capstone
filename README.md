# weather-capstone

Web scraping capstone: current weather for ~140 cities around the world, scraped
from [Weather Around The World](https://www.timeanddate.com/weather/) on
timeanddate.com, cleaned with pandas and saved as CSV.

## What I'm exploring

The site's summary table gives a live snapshot of every major city at once, and
each city's own page adds the readings the table leaves out. That makes it
possible to compare cities against each other at the same moment:

- How far "feels like" drifts from the actual temperature, and where humidity
  drives that gap
- Which countries are hottest and windiest in a given snapshot
- How temperature tracks the local hour across time zones
- How conditions (rain, cloud, clear) group by country

## Setup

Requires Python 3.10+ and Google Chrome. Selenium downloads the matching
ChromeDriver by itself.

```bash
git clone https://github.com/jjaramillo4/weather-capstone.git
cd weather-capstone

python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

pip install -r requirements.txt
```

## Running it

Two scripts, run in order.

**1. Scrape** — reads the summary table, then visits each city page:

```bash
python scrape.py                 # 143 cities (default)
python scrape.py --limit 10      # quick test
python scrape.py --cities 358    # a wider city list
python scrape.py --show-browser  # watch it work
```

Writes `data/raw/weather_raw.csv` — the raw strings exactly as scraped
(`"77 °F"`, `"82 / 76 °F"`, `"12 mph from Southwest"`).

**2. Clean** — parses those strings into numbers:

```bash
python clean.py
```

Prints a before/after summary and writes:

- `data/processed/weather_clean.csv` — one tidy row per city
- `data/processed/country_summary.csv` — averages grouped by country

## How the scraping works

The table packs three cities per row, four cells each (city link, local time,
condition icon, temperature), so rows are read in blocks of four. The condition
text lives in the icon's `title` attribute, not as text.

Things the scraper has to deal with:

- **Bot check** — the site is behind a Cloudflare interstitial that serves
  "Just a moment..." first, and it rejects `requests` outright with a 403. Every
  page load waits for a real element to appear instead of sleeping a fixed time,
  and the browser sends a normal Chrome user-agent.
- **Missing tags** — plenty of cities report no visibility, and some have no
  wind or condition icon. Those fields come back empty rather than raising.
- **Pagination** — the "Cities Shown" dropdown is what widens the list, so
  `--cities` drives that `<select>` (falling back to the `?low=` URL it produces).
- **No duplicate requests** — cities are de-duplicated by URL before any detail
  page is fetched, and one browser session is reused for the whole run.
- **Crash recovery** — Chrome sometimes dies partway through a long run, so the
  scraper restarts it and retries that city. Rows are flushed as they're written,
  so an interrupted run keeps what it got.

There is a 1.5 second pause between page loads. `robots.txt` allows `/weather/`
pages; it disallows the `?hd=` history and `?sort` views, which this scraper
never touches.

## Cleaning steps

`clean.py` shows the data before and after, then:

1. Drops duplicate rows and duplicate cities, and rows with no temperature
2. Parses numbers out of the scraped strings — `"29.89 "Hg"` becomes `29.89`,
   `"82 / 76 °F"` splits into high and low, `"No wind"` becomes `0`
3. Adds derived columns: Celsius, the feels-like gap, forecast range, local hour
   on a 24-hour clock, a daytime flag, and a condition bucket
   (Rain / Cloudy / Clear / Thunderstorm / Fog / ...)
4. Drops impossible temperatures and blanks out-of-range humidity
5. Groups by country for the summary CSV

## Project layout

```
scrape.py                          # program 1: Selenium scrape -> raw CSV
clean.py                           # program 2: pandas clean -> tidy CSV
requirements.txt
data/raw/weather_raw.csv           # raw scrape output
data/processed/weather_clean.csv   # cleaned data
data/processed/country_summary.csv # grouped by country
```

## Still to come

SQLite storage, a command-line query tool, and a Streamlit dashboard.

## Note

The data is a point-in-time snapshot of a live site, scraped for a class
project. The site's layout changes from time to time, which can require
updating the selectors in `scrape.py`.
