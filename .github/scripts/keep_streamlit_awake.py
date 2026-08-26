"""
Keeps the live Streamlit Community Cloud demo awake, and wakes it back up
if it has already gone to sleep.

Why a plain HTTP GET (e.g. a cron-job.org ping) doesn't actually work:
Streamlit Community Cloud's inactivity tracking is based on a real browser
opening the app's WebSocket session (/_stcore/stream) - the same thing that
happens when a person visits the page and the JS bundle runs. A plain GET
only fetches the static HTML shell; it never executes that JS, so it never
opens the WebSocket, and Streamlit's own inactivity clock never resets.
Once the app is already asleep, a GET just fetches the static "this app has
gone to sleep" page - it can't click the "wake up" button, because there's
no JS execution to click anything with.

This script uses a real (headless) browser instead via Playwright, which
runs the actual JS bundle and opens the WebSocket like a real visitor -
and if the app is already asleep, finds and clicks the
"Yes, get this app back up!" button and waits for it to finish restarting.

Run on a schedule well under Streamlit Cloud's inactivity window (see the
GitHub Actions workflow in this same folder).
"""

import sys
from playwright.sync_api import sync_playwright

APP_URL = "https://bellekens-valuation.streamlit.app"
# Partial, case-insensitive match - robust to Streamlit tweaking the exact
# button copy (seen both with and without a trailing "!" across reports).
WAKE_BUTTON_TEXT = "get this app back up"


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(APP_URL, wait_until="domcontentloaded", timeout=120_000)

        wake_button = page.get_by_role("button", name=WAKE_BUTTON_TEXT, exact=False)
        try:
            wake_button.wait_for(timeout=15_000)
            is_asleep = True
        except Exception:
            is_asleep = False

        if is_asleep:
            print("App was asleep - clicking the wake-up button...")
            wake_button.click()
            page.wait_for_timeout(60_000)  # give the container time to finish restarting
            print("Wake-up triggered.")
        else:
            # No wake button present - the app is already running. Simply
            # loading the page with a real browser (not a GET) still opens
            # the WebSocket session, which is what actually resets
            # Streamlit's own inactivity clock.
            page.wait_for_timeout(5_000)
            print("App already awake - visit registered.")

        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
