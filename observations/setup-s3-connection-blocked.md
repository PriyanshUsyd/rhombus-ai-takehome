# Setup: Amazon S3 source connection blocked

| | |
|---|---|
| **Goal** | Use Amazon S3 as the pipeline source, as the brief specifies. |
| **Result** | Blocked. Rhombus could not read the bucket. |
| **Route used instead** | Azure Blob Storage container `source` → AI-built pipeline → Azure Blob Storage container `output` (Deviation D1, see `PLAN.md`). |
| **Date** | 2026-10-03 (first attempts), 2026-10-04 (final attempt + CloudTrail check) |

## Steps followed

Followed the Rhombus guide: https://doc.rhombusai.com/docs/Integrations/aws-s3-connection/

Final attempt (2026-10-04):
- Fresh bucket `priyansh-rhombus-s3-src`, region `ap-southeast-2`.
- Block Public Access ON, default encryption SSE-S3.
- Folder / path left blank in the Rhombus connection form.
- Applied the Rhombus-generated whole-bucket read-only policy exactly as generated (CloudTrail `PutBucketPolicy` at 2026-10-04 12:36:22 AEDT).

Earlier attempts (2026-10-03), same result:
- Folder-scoped policy on `priyansh-rhombus-takehome-src`.
- Whole-bucket policy on `priyansh-rhombus-src-v2`.

## Rhombus error

> AWS denied Rhombus AI access to the whole bucket. Folder / path is blank. The required whole-bucket read-only policy is missing or does not match this bucket. Apply the generated policy, or update the CloudFormation stack so SourceBucket matches the connection form and SourcePrefix is empty, then retry.

## CloudTrail evidence

Recorded in my AWS account (`187887017706`). All three events are `GetBucketLocation` calls with these shared fields:

- Caller account: `730335216038`
- principalId: `AROA2UC27AGTLYXU6JHR5`
- sourceIPAddress: `13.55.55.61`
- userAgent: Boto3 1.41.5
- Result: `AccessDenied` (403)

| Time (UTC, 2026-10-04) | Bucket policy in place | requestID |
|---|---|---|
| 01:36:16Z | None yet (denial expected) | `8PQHB8577D4KQ776` |
| 01:43:18Z | Rhombus-generated policy | `FJ2FK5RFX099RJHW` |
| 01:50:33Z | Test policy granting `arn:aws:iam::730335216038:root` the same read-only actions | `G32T2NSDBFHACFJC` |

The test policy was removed after the check.

## Conclusion

Rhombus's requests reach the bucket and are denied, even when the bucket policy allows the whole Rhombus AWS account. That rules out the generated policy and its principals as the cause. Two causes remain, and neither can be determined from my side:

- **(a)** The Rhombus calling role lacks S3 permission in its own identity policy.
- **(b)** An AWS Organizations policy applies to my account. AWS's sign-up flow created the account inside an AWS Organization, and org policies are not viewable from a member account.

## Usability observations

- **Misleading error.** The message says the policy is "missing or does not match" even when the generated policy was applied exactly.
- **Verification runs early.** Verification ran automatically before Connect was clicked.
- **Inconsistent setup text.** The "AWS access setup" text says "this prefix only" even when Folder / path is blank.
- **Chatbot did not help.** Asking Rhombo cost 6 credits and returned a generic checklist that didn't identify the cause.
- **Support.** Rhombus support was contacted on 2026-10-03. The reply pointed to the S3 guide.

## Evidence

- [`observations/evidence/s3-denied.png`](evidence/s3-denied.png): the Rhombus error notification above the generated policy. Principals: Rhombus account `730335216038`; resource `arn:aws:s3:::priyansh-rhombus-s3-src/*`. Taken in project `rhombus-takehome` (workflow 5251).
- **CloudTrail events:** the full JSON for the three `GetBucketLocation` events is **not published** (raw evidence retained privately). Their key fields are in the table above: time, caller principalId, `AccessDenied` (403) and requestID (`8PQHB8577D4KQ776`, `FJ2FK5RFX099RJHW`, `G32T2NSDBFHACFJC`).
- **Other S3 setup screenshots:** **not published** (raw evidence retained privately). These are the "AWS access setup" text saying "this prefix only" with Folder / path blank, the bucket settings (Block Public Access ON, SSE-S3) and the generated policy as applied. Their content is described under "Steps followed" and "Usability observations".
- **Rhombo chatbot reply:** summary only, with no screenshot published. It cost 6 credits and returned a generic checklist that didn't identify the cause (see `PLAN.md`).

## Follow-up

Candidate negative API/UI test for Phase 5 (see `phases/phase-5-code.md`).
