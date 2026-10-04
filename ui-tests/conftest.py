"""Shared fixtures for the live UI tests (pytest-playwright).

- Reuses the logged-in browser state in playwright/.auth/user.json (gitignored). Login involves
  a one-time email code, so the tests never log in themselves.
- Skips with a clear message if that file is missing, or if the app shows the login page
  (expired session).
- `run_pipeline` tests are opt-in: they run only with `--run-pipeline`.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from dotenv import load_dotenv
from playwright.sync_api import Page, expect
from rhombus_pages import LOAD_TIMEOUT, ProjectCanvas

REPO = Path(__file__).resolve().parent.parent
load_dotenv(REPO / ".env")

AUTH_STATE = REPO / "playwright" / ".auth" / "user.json"
APP_URL = os.environ.get("RHOMBUS_BASE_URL") or "https://rhombusai.com"
PROJECT_NAME = "rhombus-takehome-v2"
SESSION_EXPIRED = (f"logged-in session in {AUTH_STATE.relative_to(REPO)} has expired: "
                   "log in again in a headed browser and re-save the storage state")


def pytest_addoption(parser):
    parser.addoption("--run-pipeline", action="store_true", default=False,
                     help="also run tests marked run_pipeline (runs the real pipeline once)")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-pipeline"):
        return
    skip = pytest.mark.skip(reason="opt-in: pass --run-pipeline to run the real pipeline")
    for item in items:
        if "run_pipeline" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    if not AUTH_STATE.is_file():
        pytest.skip(f"missing {AUTH_STATE.relative_to(REPO)}: log in once in a headed browser "
                    "and save the storage state there")
    return {**browser_context_args, "storage_state": str(AUTH_STATE),
            "viewport": {"width": 1600, "height": 1000}}


@pytest.fixture
def canvas(page: Page) -> ProjectCanvas:
    """Open the project canvas from the dashboard; skip if the session has expired."""
    page.goto(APP_URL)
    project_link = page.get_by_role("link", name=PROJECT_NAME, exact=True)
    login = page.get_by_role("textbox", name="Email address").or_(
        page.get_by_role("button", name="Log In"))
    expect(project_link.or_(login).first).to_be_visible(timeout=LOAD_TIMEOUT)
    if login.first.is_visible():
        pytest.skip(SESSION_EXPIRED)
    project_link.click()
    expect(page).to_have_url(re.compile(r"/workflow/\d+$"), timeout=LOAD_TIMEOUT)
    project = ProjectCanvas(page)
    expect(project.input_node).to_be_visible(timeout=LOAD_TIMEOUT)
    return project
