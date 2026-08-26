"""Scrape current weather for cities around the world (timeanddate.com).

Saves one raw CSV: data/raw/weather_raw.csv

Usage:
    python scrape.py                 # 143 cities
    python scrape.py --cities 358    # more cities (pagination)
    python scrape.py --limit 10      # quick test run
"""

import argparse
import csv
import datetime
import os
import re
import sys
import time

from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import Select

INDEX_URL = "https://www.timeanddate.com/weather/"
OUT_CSV = os.path.join("data", "raw", "weather_raw.csv")

# The site's "Cities Shown" dropdown -> how we page to a bigger city list.
TIERS = {"143": "6", "215": "c", "358": "5", "472": "4"}

# A real browser user-agent. The site's bot-check rejects the automation default.
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")

DELAY = 1.5          # seconds between page loads, to be polite
TIMEOUT = 45         # seconds to wait for a page (the bot-check can be slow)

FIELDS = ["city", "country", "city_url", "local_time", "condition", "temperature",
          "feels_like", "forecast", "wind", "humidity", "dew_point", "pressure",
          "visibility", "station", "scraped_at"]

# The readings sit in one run of free text, so each is read by name and ends
# where the next label starts.
LABELS = ("Feels Like", "Forecast", "Wind", "Humidity", "Dew Point",
          "Pressure", "Visibility", "Location", "Current Time", "Latest Report")


def start_browser(headless=True):
    """Open Chrome, configured to look like an ordinary browser."""
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    for arg in ("--window-size=1400,1000", "--no-sandbox", "--disable-dev-shm-usage",
                "--disable-gpu", "--disable-blink-features=AutomationControlled",
                "user-agent=" + USER_AGENT):
        opts.add_argument(arg)
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    return webdriver.Chrome(options=opts)


def load(driver, url, wait_css):
    """Load a page and wait for wait_css, past the "Just a moment" bot-check.

    Returns True on success and False if the page never came up, so one bad
    city does not kill the whole run. If the browser itself has died the
    WebDriverException propagates, so the caller can restart it.
    """
    try:
        driver.get(url)
    except TimeoutException:
        return False

    deadline = time.time() + TIMEOUT
    while time.time() < deadline:
        if "just a moment" not in (driver.title or "").lower() \
                and driver.find_elements("css selector", wait_css):
            return True
        time.sleep(1)
    return False


def clean(text):
    """Collapse non-breaking spaces and whitespace; empty becomes None."""
    if not text:
        return None
    return " ".join(text.replace("\xa0", " ").split()) or None


def value_after(label, text):
    """Return what follows 'label:' up to the next known label."""
    others = "|".join(re.escape(x) for x in LABELS if x.lower() != label.lower())
    pattern = re.compile(
        rf"{re.escape(label)}\s*:\s*(.+?)(?=\s*(?:{others})\s*:|\s*$)",
        re.IGNORECASE | re.DOTALL)
    found = pattern.search(text)
    return clean(found.group(1)) if found else None


def scrape_index(driver, tier):
    """Get the city list from the summary table.

    Each row packs three cities side by side, four cells each:
    link | local time | condition icon | temperature.
    """
    if not load(driver, INDEX_URL, "table.tb-theme td a[href^='/weather/']"):
        sys.exit("Could not load the index page.")

    if TIERS[tier] != "6":                      # pagination: widen the list
        try:
            Select(driver.find_element("css selector", "select#pop")) \
                .select_by_value(TIERS[tier])
            time.sleep(2)
        except WebDriverException:
            pass                                # fall back to the direct URL
        if not load(driver, INDEX_URL + "?low=" + TIERS[tier],
                    "table.tb-theme td a[href^='/weather/']"):
            sys.exit("Could not load the wider city list.")

    cities = {}
    for row in driver.find_elements("css selector", "table.tb-theme tbody tr"):
        cells = row.find_elements("css selector", "td")
        for i in range(0, len(cells), 4):
            block = cells[i:i + 4]
            if len(block) < 4:
                continue                        # short trailing block
            link = block[0].find_elements("css selector", "a[href^='/weather/']")
            if not link:
                continue                        # spacer cell, no city
            url = link[0].get_attribute("href") or ""
            parts = url.split("/weather/")[-1].strip("/").split("/")
            condition = None
            try:
                icon = block[2].find_element("css selector", "img")
                condition = clean(icon.get_attribute("title")
                                  or icon.get_attribute("alt"))
            except NoSuchElementException:
                pass                            # missing icon -> leave blank
            cities[url] = {                     # dict key de-duplicates cities
                "city": clean(link[0].text),
                "country": parts[0].replace("-", " ").title() if parts else None,
                "city_url": url,
                "local_time": clean(block[1].text),
                "condition": condition,
                "temperature": clean(block[3].text),
            }
    return list(cities.values())


def scrape_city(driver, city):
    """Add the detail-page readings to one city record."""
    row = dict.fromkeys(FIELDS)
    row.update(city)
    row["scraped_at"] = datetime.datetime.now().isoformat(timespec="seconds")

    if not load(driver, city["city_url"], "#qlook"):
        print("  skipped (page did not load)")
        return row

    block = driver.find_element("css selector", "#qlook")
    text = block.text or ""
    row["temperature"] = (clean(block.find_element("css selector", ".h2").text)
                          or city.get("temperature"))
    paragraphs = block.find_elements("css selector", "p")
    if paragraphs:
        row["condition"] = clean(paragraphs[0].text) or city.get("condition")
    row["feels_like"] = value_after("Feels Like", text)
    row["forecast"] = value_after("Forecast", text)
    row["wind"] = value_after("Wind", text)

    # Side table: Location / Visibility / Pressure / Humidity / Dew Point.
    wanted = {"location": "station", "visibility": "visibility",
              "pressure": "pressure", "humidity": "humidity",
              "dew point": "dew_point"}
    for tr in driver.find_elements("css selector", ".bk-focus__info table tr"):
        try:
            label = clean(tr.find_element("css selector", "th").text) or ""
            key = wanted.get(label.rstrip(":").strip().lower())
            if key:
                row[key] = clean(tr.find_element("css selector", "td").text)
        except NoSuchElementException:
            continue                            # missing row -> leave blank
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cities", choices=sorted(TIERS), default="143",
                    help="how many cities the site should list")
    ap.add_argument("--limit", type=int, help="only scrape the first N cities")
    ap.add_argument("--show-browser", action="store_true")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    driver = start_browser(headless=not args.show_browser)
    try:
        cities = scrape_index(driver, args.cities)
        if args.limit:
            cities = cities[:args.limit]
        print("Found %d cities. Fetching detail pages..." % len(cities))

        with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=FIELDS)
            writer.writeheader()
            for n, city in enumerate(cities, 1):
                print("[%d/%d] %s" % (n, len(cities), city["city"]))
                try:
                    row = scrape_city(driver, city)
                except Exception:
                    # Chrome dies every so often on a long run, and it surfaces
                    # as anything from WebDriverException to a raw urllib3
                    # connection reset - so catch broadly, restart, retry once.
                    print("  browser died, restarting")
                    try:
                        driver.quit()
                    except Exception:
                        pass
                    driver = start_browser(headless=not args.show_browser)
                    try:
                        row = scrape_city(driver, city)
                    except Exception:
                        print("  giving up on this city")
                        row = dict.fromkeys(FIELDS)
                        row.update(city)
                writer.writerow(row)
                fh.flush()                      # keep progress if interrupted
                time.sleep(DELAY)
    finally:
        try:
            driver.quit()
        except WebDriverException:
            pass

    print("Saved %d rows to %s" % (len(cities), OUT_CSV))


if __name__ == "__main__":
    main()
