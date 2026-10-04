"""Live UI journey for project rhombus-takehome-v2 (workflow 5257), adapted per D1/D2.

Locators and expected texts come from the 2026-10-04 codegen recording and ARIA snapshots
of the live app. No test creates, deletes, saves or schedules anything:
- nothing clicks Apply, Create, Delete or a dataset in the input list;
- test_run_pipeline_end_to_end (opt-in, --run-pipeline) only presses ▶ Run on the existing
  pipeline.

Run: pytest ui-tests -m live --headed [--run-pipeline]
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta

import pytest
from azure_output import container_from_env, output_names, wait_for_new_output
from conftest import PROJECT_NAME, REPO
from playwright.sync_api import expect
from rhombus_pages import LOAD_TIMEOUT, ProjectCanvas

pytestmark = pytest.mark.live

# D1 evidence: exact message observed 2026-10-04 (observations/setup-s3-connection-blocked.md).
S3_DENIED = ("AWS denied Rhombus AI access to the whole bucket. Folder / path is blank. "
             "The required whole-bucket read-only policy is missing or does not match this bucket.")
S3_BUCKET = "priyansh-rhombus-s3-src"
S3_REGION = "Asia Pacific (Sydney) (ap-southeast-2)"
S3_TIMEOUT = 90_000
RUN_LOG_TIMEOUT = 120_000
COMPLETED = "Pipeline execution completed successfully."
FAILED_RE = re.compile(r"Pipeline failed at ")

BASELINE_OUTPUT = REPO / "outputs" / "manual-dryrun-4.csv"
# Baseline manual run 4 fails only these checks (validation-manual-dryrun-4.json): the
# known "None" names and dropped-trailing-zero defects.
KNOWN_BASELINE_FAILURES = {"rule_name_missing_kept_null", "values_match_policy", "output_format"}


def test_project_canvas_shows_pipeline_nodes(canvas: ProjectCanvas):
    """(1) Project canvas shows the Data Input, Custom (AI-built) and Data Output nodes."""
    expect(canvas.input_node).to_be_visible()
    expect(canvas.custom_node).to_be_visible()
    expect(canvas.output_node).to_be_visible()
    expect(canvas.input_node).to_contain_text("baseline.csv")


def test_s3_source_is_denied(canvas: ProjectCanvas):
    """(2) D1: connecting the S3 bucket shows the access-denied error; nothing is saved."""
    dialog = canvas.open_input().open_third_party_sources()
    expect(dialog.add_data_sources).to_be_visible(timeout=LOAD_TIMEOUT)
    form = dialog.open_s3_form()
    expect(form.bucket).to_be_visible(timeout=LOAD_TIMEOUT)

    form.fill(S3_BUCKET, S3_REGION)
    expect(form.region).to_contain_text(S3_REGION)
    form.connect()

    expect(form.toast.filter(has_text=S3_DENIED)).to_be_visible(timeout=S3_TIMEOUT)
    dialog.close()
    expect(dialog.dialog).to_be_hidden()


def test_data_output_targets_azure_output_container(canvas: ProjectCanvas):
    """(3) Data Output exports to the Azure Blob Storage destination `output`."""
    expect(canvas.output_node).to_contain_text("Export to output (csv)")
    panel = canvas.open_output()
    expect(panel.heading).to_be_visible(timeout=LOAD_TIMEOUT)
    expect(panel.destination("Azure Blob Storage", "output")).to_be_visible()


def test_schedule_is_active_hourly_and_hourly_is_offered(canvas: ProjectCanvas):
    """(4) The existing hourly schedule is Active; Create Schedule offers Hourly; cancelled."""
    panel = canvas.open_schedule()
    entries = panel.schedule_entries(PROJECT_NAME)
    expect(entries).to_have_count(1, timeout=LOAD_TIMEOUT)
    expect(panel.panel).to_contain_text("Active")
    expect(panel.panel).to_contain_text("hourly")
    expect(panel.active_switch).to_be_checked()

    create = panel.open_create_dialog()
    expect(create.dialog).to_be_visible()
    create.open_frequency()
    expect(create.frequency_option("Hourly")).to_be_visible()
    create.frequency_option("Daily").click()  # re-select the default to close the list
    create.cancel()

    expect(create.dialog).to_be_hidden()
    expect(entries).to_have_count(1)  # nothing was created


def test_ai_builder_chat_is_available(canvas: ProjectCanvas):
    """(5) AI Builder tab shows the chat input (nothing is sent)."""
    panel = canvas.open_ai_builder()
    expect(canvas.ai_builder_tab).to_have_attribute("aria-selected", "true")
    expect(panel.chat_input).to_be_visible()
    expect(panel.chat_input).to_be_editable()


@pytest.mark.run_pipeline
def test_run_pipeline_end_to_end(canvas: ProjectCanvas):
    """(6) Opt-in: ▶ Run the existing pipeline on baseline.csv, then check the Azure output.

    The input is not re-selected: selecting a dataset needs Apply, and Apply itself starts a
    run. The test requires the input node to already show baseline.csv.

    Log entries count only if their own timestamp is from the ▶ press onwards, read from log
    cards only. The AI Builder chat can contain old "Pipeline failed at ..." text, and runs
    are sometimes logged when the page opens.

    Status 2026-10-04 (PLAN.md "Findings log"): intermittent. Some ▶ runs log "Pipeline
    failed at src_output: A destination is required when remote export is selected." while
    the UI shows destination `output` selected. Observed outcomes: failure + no export
    (~17:07), no failure + export (17:23, 17:24), failure + export 20 s later (18:06).
    The cause is not observed.
    """
    if not os.environ.get("AZURE_OUTPUT_CONNECTION_STRING"):
        pytest.skip("AZURE_OUTPUT_CONNECTION_STRING missing in .env")
    expect(canvas.input_node).to_contain_text("baseline.csv")
    container = container_from_env()
    before = output_names(container)

    logs = canvas.open_logs()
    expect(logs.loaded).to_be_visible(timeout=LOAD_TIMEOUT)
    # Only log entries timestamped from the ▶ press onwards belong to this run. Earlier
    # entries, and runs logged when the page opened, are ignored.
    started = datetime.now().astimezone().replace(microsecond=0)
    window = [(started + timedelta(seconds=s)).strftime("%I:%M:%S %p")
              for s in range(RUN_LOG_TIMEOUT // 1000 + 1)]
    canvas.run()
    this_run = logs.cards_at(window)
    expect(this_run.filter(has_text=COMPLETED).first).to_be_visible(timeout=RUN_LOG_TIMEOUT)

    def new_failures() -> list[str]:
        return [" ".join(t.split()) for t in this_run.filter(has_text=FAILED_RE).all_inner_texts()]

    # Observed 2026-10-04: some ▶ runs logged "Pipeline failed at src_output: A destination is
    # required when remote export is selected." in the same second as "completed
    # successfully", so completion alone isn't proof of success.
    try:
        blob = wait_for_new_output(container, before, deadline_s=300, interval_s=5)
    except TimeoutError as exc:
        raise AssertionError(f"{exc}; failures logged by this run: {new_failures() or 'none'}")
    failures = new_failures()
    assert not failures, f"▶ Run exported {blob.name} but also logged a failure: {failures}"

    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S") + "z"  # validator needs lowercase
    out_csv = REPO / "outputs" / f"ui-run-{stamp}.csv"
    out_csv.parent.mkdir(exist_ok=True)
    out_csv.write_bytes(container.download_blob(blob.name).readall())

    report_path = REPO / "outputs" / f"ui-run-{stamp}.validation.json"
    proc = subprocess.run(
        [sys.executable, str(REPO / "data-validation" / "validate.py"),
         "--scenario", f"ui-run-{stamp}", "--input", str(REPO / "datasets" / "baseline.csv"),
         "--output", str(out_csv), "--baseline-output", str(BASELINE_OUTPUT),
         "--report", str(report_path)],
        capture_output=True, text=True, check=False)
    assert proc.returncode in (0, 1), proc.stderr
    report = json.loads(report_path.read_text(encoding="utf-8"))
    failed = {name for name, c in report["checks"].items() if c["status"] == "fail"}
    assert failed == KNOWN_BASELINE_FAILURES, f"{blob.name}: failed checks {sorted(failed)}"
    assert report["checks"]["determinism"]["status"] == "pass"
    assert (hashlib.sha256(out_csv.read_bytes()).hexdigest()
            == hashlib.sha256(BASELINE_OUTPUT.read_bytes()).hexdigest()), (
        f"{blob.name} is not byte-identical to {BASELINE_OUTPUT.name}")

