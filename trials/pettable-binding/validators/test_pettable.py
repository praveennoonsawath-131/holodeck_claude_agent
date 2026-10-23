"""Checks that the data table on the PetTable page is bound to the petstore
findPetsByTags API and is loaded with pet rows."""

import os
from urllib.parse import urlparse

import pytest
from playwright.sync_api import sync_playwright

TIMEOUT_MS = int(os.environ.get("HOLODECK_TIMEOUT_MS", "60000"))
ARTIFACT_DIR = os.environ.get("HOLODECK_ARTIFACT_DIR")

ROWS = "table tbody tr"


@pytest.fixture(scope="module")
def pet_page():
    """Opens the PetTable page once and records the API calls it makes."""
    url = os.environ["HOLODECK_TARGET_URL"]
    api_calls = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        auth_cookie = os.environ.get("HOLODECK_AUTH_COOKIE")
        if auth_cookie:
            context.add_cookies(
                [{"name": "auth_cookie", "value": auth_cookie, "domain": urlparse(url).hostname, "path": "/"}]
            )
        page = context.new_page()
        page.set_default_timeout(TIMEOUT_MS)
        page.on(
            "response",
            lambda response: api_calls.append(response)
            if response.request.resource_type in {"xhr", "fetch"}
            else None,
        )
        page.goto(url, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=TIMEOUT_MS)
        except Exception:
            pass  # a page that keeps polling never goes idle; the tests wait for what they need
        yield page, api_calls
        if ARTIFACT_DIR:
            page.screenshot(path=os.path.join(ARTIFACT_DIR, "pettable.png"), full_page=True)
        browser.close()


def data_rows(page):
    return page.locator(ROWS).filter(has_not_text="No data found")


def test_table_is_visible(pet_page):
    page, _ = pet_page
    page.locator("table").first.wait_for(state="visible")


def test_table_shows_pet_rows(pet_page):
    page, _ = pet_page
    rows = data_rows(page)
    rows.first.wait_for(state="visible")
    count = rows.count()
    assert count >= 1, f"expected at least one pet row in the table, found {count}"
    first_row = rows.first.inner_text().strip()
    assert first_row, "the first table row is empty"


def test_table_calls_petstore_find_by_tags(pet_page):
    _, api_calls = pet_page
    calls = [call for call in api_calls if "findbytags" in call.url.lower()]
    assert calls, "the page never called the petstore findPetsByTags API"
    failed = [f"{call.status} {call.url}" for call in calls if call.status >= 400]
    assert not failed, f"findPetsByTags failed: {failed}"
