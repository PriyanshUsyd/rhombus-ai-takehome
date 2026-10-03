# Rhombus AI Take-Home Exercise

TODO

## Setup and how to run

TODO

## Observations summary

TODO

## Usability feedback

TODO

## Demo video link

TODO

## Limitations

TODO

## Deviations

The brief specifies Amazon S3 (source) → Google Cloud Storage (destination). This project uses **Azure Blob Storage (source) → Azure Blob Storage (destination)** instead:

- **Amazon S3 source was blocked.** Rhombus reported "AWS denied Rhombus AI access to the selected Folder / path..." even after the Rhombus-generated bucket policy was applied exactly (folder-scoped on one bucket, whole-bucket on another). Details: `observations/setup-s3-connection-blocked.md`. Rhombus support was contacted on 2026-10-03.
- **Google Cloud Storage was not used** because GCP billing requires a card, and none was available.
- Azure Blob is a source and destination that Rhombus supports. Everything else in the exercise (scheduled runs, schema and semantic drift cases, chatbot fixes, validation) is unchanged.
