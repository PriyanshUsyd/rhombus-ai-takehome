# Rhombus AI Take-Home Exercise

TODO

## Setup and how to run

TODO

Note: the reference policy engine in `data-validation/cleaning_policy.py` only computes the **expected** output for comparison; it never modifies the pipeline output. The brief's "AI builder only, no manual transformations" rule applies to the pipeline, and is respected.

## Observations summary

TODO

## Usability feedback

TODO

## Demo video link

TODO

## Limitations

TODO

- The validator's semantic anomaly thresholds are documented, **untuned heuristics** (constants at the top of `data-validation/validate.py`), compared against the baseline output:
  - row count: relative change > 10%;
  - money (`price`, `total`): median or sum ratio outside 0.5–2.0;
  - null rate: absolute increase > 0.05 in any column;
  - date parse success rate: drop > 0.01;
  - dates outside the baseline output's date range;
  - month histogram or `country`/`status` distribution: total variation distance > 0.25, or values not seen in the baseline;
  - any increase in duplicate-key count or `total ≠ price × qty` failures.

## Deviations

The brief specifies Amazon S3 (source) → Google Cloud Storage (destination). This project uses **Azure Blob Storage (source) → Azure Blob Storage (destination)** instead:

- **Amazon S3 source was blocked.** Rhombus reported "AWS denied Rhombus AI access to the selected Folder / path..." even after the Rhombus-generated bucket policy was applied exactly (folder-scoped on one bucket, whole-bucket on another). Details: `observations/setup-s3-connection-blocked.md`. Rhombus support was contacted on 2026-10-03.
- **Google Cloud Storage was not used** because GCP billing requires a card, and none was available.
- Azure Blob is a source and destination that Rhombus supports. Everything else in the exercise (scheduled runs, schema and semantic drift cases, chatbot fixes, validation) is unchanged.
