# AI builder prompts — baseline pipeline

Source of truth: `datasets/cleaning-policy.md` (approved 2026-10-03). These prompts restate that policy in plain English for the Rhombus AI builder. If the two ever disagree, the policy wins and this file gets fixed.

**Credit budget:** about 6 credits per message, 44 left at the time of writing. Plan: send **Prompt 1** once, and use **Prompt 2** at most once, only if the output breaks specific rules. That is about 12 credits, leaving about 32 for the drift-case chatbot work.

**How to use**
1. Send Prompt 1 exactly as written (copy everything inside the box).
2. Save the prompt and the builder's full reply verbatim into `evidence-raw/` (the reply's list of steps is a *claim* to verify, not ground truth).
3. Run the pipeline and download the output. The validator, not the builder's summary, decides which rules actually held.
4. Only if specific rules failed: fill in Prompt 2 with those rules and send it once. Never add manual steps (CLAUDE.md rule 6).

The prompts deliberately do not state the expected row count, so the builder cannot tune its steps to a target number.

---

## Prompt 1 — consolidated cleaning prompt

```text
Build a cleaning pipeline for this transactions dataset. Each row is one transaction. The columns are: id, name, email, country, price, qty, total, transaction_date, status. Keep exactly these 9 columns, in this order, with these names. Do not add any other columns. An empty cell means the value is missing.

Apply the steps in this order:

STEP 1 – Tidy text.
Remove spaces at the start and end of every value in every column. In name, replace runs of several spaces with a single space.

STEP 2 – Standardise formats.
- name: Title Case (first letter of each word capital, the rest lowercase), e.g. "alice NGUYEN" becomes "Alice Nguyen".
- email: all lowercase.
- country: match ignoring upper/lower case against exactly this list: Australia, New Zealand, United States, United Kingdom, Canada, India, Singapore, Germany. Write the matching name exactly as it appears in the list. If the value is not in the list, leave the cell empty.
- status: all lowercase. Allowed values are only completed, pending, refunded, cancelled. Any other value becomes an empty cell.
- price: remove a leading dollar sign if there is one.
- transaction_date: convert to YYYY-MM-DD. Accept only these input formats (examples all mean 7 March 2025, except the last):
    * 2025-03-07
    * 07 Mar 2025
    * March 07, 2025
    * 2025/03/07
    * day/month/year with slashes, e.g. 25/03/2025 (25 March 2025)
  Accept the slash day/month/year format only when the first number is greater than 12. If both numbers are 12 or less, the date is ambiguous; treat it as invalid. Do not guess any other format.

STEP 3 – Remove duplicates.
Two rows are duplicates when they have the same id. Keep the first one in the original file order and remove the later ones. Do this after steps 1 and 2. Do not remove rows just because they share an email address: the same customer can have many different transactions with different ids, and all of them must be kept.

STEP 4 – Remove rows that cannot be trusted.
Delete the whole row if any of these is true:
- price is missing, or is not a number.
- qty is missing, is not a whole number, or is zero or negative.
- transaction_date is missing, is in a format not listed above, is ambiguous, or is a date that does not exist (for example 2025-02-30 or month 13). Never shift an impossible date to a nearby real date.
- total is present but does not equal price multiplied by qty, rounded to 2 decimal places (halves round up). Compare the numbers exactly as decimals, not approximately, so 37.02 and 37.020 count as equal but 37.02 and 37.03 do not.
Do not write the removed rows anywhere else; just drop them.

STEP 5 – Fix or blank the remaining problems.
- If total is missing, fill it with price multiplied by qty, rounded to 2 decimal places.
- If email is not a valid email address (it must have exactly one @, some text before it, and a domain containing a dot after it), leave the email cell empty but keep the row.
- If name, email, country or status is missing, leave it empty and keep the row. Never invent or guess a value for these.

STEP 6 – Final output format.
- id and qty: whole numbers.
- price and total: plain numbers with exactly 2 decimal places, a dot as the decimal separator, no currency symbol and no thousands separator, e.g. 1234.50.
- transaction_date: YYYY-MM-DD.
- Missing values: empty cells.
- Do not change any other values and do not reorder the columns.

When you have finished, reply with a numbered list of every step you created and the rule each step applies.
```

---

## Prompt 2 — single correction follow-up (template; send at most once)

Fill in the bracketed parts from the **validator report**, listing only the failed rules, then send. Keep it short.

```text
The output does not follow these rules yet:
1. [rule, e.g. "Rows with a missing qty must be deleted"] – currently [what the output shows, e.g. "3 rows with an empty qty are still in the output"].
2. [...]
Please fix only these steps and leave all other steps exactly as they are. When done, list the steps you changed.
```
