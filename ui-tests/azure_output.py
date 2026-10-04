"""Out-of-band check of the Azure Blob destination container `output`.

Pipeline completion and the export to Azure happen outside the browser, so the UI can't
`expect()` them. `wait_for_new_output` is a **bounded condition poll**, not a fixed sleep:
- it returns as soon as the condition holds (a new `RhombusAI_output_*.csv` appears);
- it gives up at a hard deadline;
- on timeout it raises with the last observed state (blob count and newest blob seen).
The pause between polls only spaces out requests to Azure; it's never what decides success.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass

from azure.storage.blob import ContainerClient

OUTPUT_RE = re.compile(r"^RhombusAI_output_\d+\.csv$")


@dataclass
class OutputBlob:
    name: str
    created: str


def container_from_env() -> ContainerClient:
    return ContainerClient.from_connection_string(
        os.environ["AZURE_OUTPUT_CONNECTION_STRING"],
        os.environ.get("AZURE_OUTPUT_CONTAINER") or "output",
    )


def output_names(container: ContainerClient) -> set[str]:
    return {b.name for b in container.list_blobs() if OUTPUT_RE.match(b.name)}


def wait_for_new_output(container: ContainerClient, before: set[str], deadline_s: float,
                        interval_s: float) -> OutputBlob:
    """Poll until a RhombusAI_output_*.csv not in `before` exists, or fail at the deadline."""
    end = time.monotonic() + deadline_s
    polls = 0
    last_state = "no poll completed"
    while True:
        polls += 1
        blobs = [b for b in container.list_blobs() if OUTPUT_RE.match(b.name)]
        new = sorted((b for b in blobs if b.name not in before), key=lambda b: b.creation_time)
        if new:
            return OutputBlob(new[-1].name, new[-1].creation_time.isoformat())
        newest = max(blobs, key=lambda b: b.creation_time, default=None)
        last_state = (f"{len(blobs)} output blobs, none new; newest "
                      f"{newest.name if newest else '-'} "
                      f"({newest.creation_time.isoformat() if newest else '-'})")
        if time.monotonic() >= end:
            raise TimeoutError(f"no new output blob after {deadline_s:.0f}s ({polls} polls); "
                               f"last observed: {last_state}")
        time.sleep(interval_s)  # spacing between bounded polls, not a wait strategy
