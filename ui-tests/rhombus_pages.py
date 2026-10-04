"""Page objects for the Rhombus AI canvas (locators + actions only; assertions live in tests).

Locators come from the 2026-10-04 codegen recording and ARIA snapshots of the live app.
Preference order: get_by_role -> get_by_label/get_by_text -> real data-testid -> CSS.
Two data-testids are used because the controls have no accessible name: `run-pipeline`
(the ▶ button) and `right-sidebar` (the node settings panel). No CSS selectors are used.
"""

from __future__ import annotations

import re

from playwright.sync_api import Locator, Page

LOAD_TIMEOUT = 60_000


class ProjectCanvas:
    """The pipeline canvas of one project (`/workflow/<id>`)."""

    def __init__(self, page: Page):
        self.page = page
        self.input_node = page.get_by_role("button", name=re.compile(r"^Data Input"))
        self.custom_node = page.get_by_role("button").filter(
            has=page.get_by_text("Custom", exact=True))
        self.output_node = page.get_by_role("button", name=re.compile(r"^Data Output"))
        self.run_button = page.get_by_test_id("run-pipeline")
        self.sidebar = page.get_by_test_id("right-sidebar")
        self.logs_button = page.get_by_role("button", name="Logs")
        self.ai_builder_tab = page.get_by_role("tab", name="AI Builder")
        self.schedule_tab = page.get_by_role("tab", name="Schedule")
        self.canvas_tab = page.get_by_role("tab", name="Canvas")

    def open_input(self) -> DataInputPanel:
        self.input_node.click()
        return DataInputPanel(self.page)

    def open_output(self) -> DataOutputPanel:
        self.output_node.click()
        return DataOutputPanel(self.page)

    def open_schedule(self) -> SchedulePanel:
        self.schedule_tab.click()
        return SchedulePanel(self.page)

    def open_ai_builder(self) -> AIBuilderPanel:
        self.ai_builder_tab.click()
        return AIBuilderPanel(self.page)

    def open_logs(self) -> LogsPanel:
        self.logs_button.click()
        return LogsPanel(self.page)

    def run(self) -> None:
        """Press ▶ Run. Runs the existing pipeline; changes nothing."""
        self.run_button.click()


class DataInputPanel:
    def __init__(self, page: Page):
        self.page = page
        sidebar = page.get_by_test_id("right-sidebar")
        self.third_party_sources = sidebar.get_by_role("button", name="Third Party Sources")

    def dataset(self, file_name: str) -> Locator:
        return self.page.get_by_test_id("right-sidebar").get_by_text(file_name, exact=True)

    def open_third_party_sources(self) -> ThirdPartyDialog:
        self.third_party_sources.click()
        return ThirdPartyDialog(self.page)


class ThirdPartyDialog:
    def __init__(self, page: Page):
        self.page = page
        self.dialog = page.get_by_role("dialog", name="Third Party Data")
        self.add_data_sources = self.dialog.get_by_role("button", name="Add Data Sources")
        self.close_button = self.dialog.get_by_role("button", name="Close", exact=True)

    def open_s3_form(self) -> S3SourceForm:
        self.add_data_sources.click()
        self.dialog.get_by_text("Connect to Amazon S3").click()
        return S3SourceForm(self.page)

    def close(self) -> None:
        self.close_button.click()


class S3SourceForm:
    def __init__(self, page: Page):
        self.page = page
        dialog = page.get_by_role("dialog", name="Third Party Data")
        self.bucket = dialog.get_by_role("textbox", name="Bucket*")
        self.region = dialog.get_by_role("combobox", name="Region*")
        self.connect_button = dialog.get_by_role("button", name="Connect S3 source")
        # The verification result is shown as a toast (role=status) in the Notifications region.
        self.toast = page.get_by_role("status")

    def fill(self, bucket: str, region_label: str) -> None:
        self.bucket.fill(bucket)
        self.region.click()
        self.page.get_by_role("option", name=re.compile(re.escape(region_label))).click()

    def connect(self) -> None:
        self.connect_button.click()


class DataOutputPanel:
    def __init__(self, page: Page):
        sidebar = page.get_by_test_id("right-sidebar")
        self.heading = sidebar.get_by_text("Select Destination")

    def destination(self, provider: str, name: str) -> Locator:
        return self.heading.page.get_by_test_id("right-sidebar").get_by_role(
            "button", name=f"{provider} {name}", exact=True)


class SchedulePanel:
    def __init__(self, page: Page):
        self.page = page
        self.add_schedule = page.get_by_role("button", name="Add Schedule")
        self.panel = page.get_by_role("complementary").filter(has=self.add_schedule)
        self.active_switch = page.get_by_role("switch", name="Deactivate schedule")

    def schedule_entries(self, project_name: str) -> Locator:
        return self.page.get_by_text(f"Schedule for {project_name}")

    def open_create_dialog(self) -> CreateScheduleDialog:
        self.add_schedule.click()
        return CreateScheduleDialog(self.page)


class CreateScheduleDialog:
    def __init__(self, page: Page):
        self.page = page
        self.dialog = page.get_by_role("dialog", name="Create Schedule")
        self.frequency = self.dialog.get_by_role("combobox")
        self.cancel_button = self.dialog.get_by_role("button", name="Cancel")

    def frequency_option(self, label: str) -> Locator:
        return self.page.get_by_role("listbox").get_by_role("option", name=label, exact=True)

    def open_frequency(self) -> None:
        self.frequency.click()

    def cancel(self) -> None:
        self.cancel_button.click()


class AIBuilderPanel:
    def __init__(self, page: Page):
        # The chat input is the only textbox on the canvas page and has no accessible name.
        self.chat_input = page.get_by_role("textbox")
        self.clear_history = page.get_by_role("button", name="Clear History")


class LogsPanel:
    """Logs panel. Each entry card holds a time ("06:05:27 PM"), its message and an
    "Expand log" button. Entries are read from those cards only, never page-wide: the AI
    Builder chat can also contain "Pipeline failed at ..." text from earlier conversations.
    """

    def __init__(self, page: Page):
        self.page = page
        # Header shows e.g. "5 visible" once the entries have loaded.
        self.loaded = page.get_by_text(re.compile(r"^\d+ visible$"))
        # Cards have no role or test id; the "Expand log" button's parent holds time + message.
        self.cards = page.get_by_role("button", name="Expand log").locator("xpath=..")

    def cards_at(self, times: list[str]) -> Locator:
        """Entry cards whose own timestamp is one of `times` (e.g. "06:05:27 PM")."""
        pattern = re.compile("|".join(re.escape(t) for t in times))
        return self.cards.filter(has_text=pattern)
