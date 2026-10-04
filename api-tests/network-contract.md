# Network contract — Rhombus AI API (observed)

Captured **2026-10-04**. Endpoints were first seen in browser DevTools while using the app, then called with `scripts/api_discovery.py`. This file records only status codes and response **shapes** (keys and types). Values are omitted or redacted, and no token appears anywhere in this repo.

**Scope:** what was observed for one account, organisation and project on that date. This is not Rhombus API documentation, and anything not listed here is not observed.

## Common

| | |
|---|---|
| Base URL | `https://api.rhombusai.com` (`RHOMBUS_API_BASE`) |
| Auth | `Authorization: Bearer <Auth0 JWT>` (`RHOMBUS_BEARER_TOKEN`, copied from DevTools) |
| Org header | `x-org-id: <org id>` (`RHOMBUS_ORG_ID`), sent on every request |
| Project | `{project_id}` = the `rhombus-takehome-v2` project (`RHOMBUS_PROJECT_ID`) |

**Unauthenticated responses**, identical for all three endpoints below:

| Case | Status | Content-Type | Body |
|---|---|---|---|
| No `Authorization` header | **401** | `application/json; charset=utf-8` | `{"detail": "Unauthorized"}` |
| `Authorization: Bearer invalid` | **401** | `application/json; charset=utf-8` | `{"detail": "Unauthorized"}` |

**Expired token: not observed.** An expired JWT is expected to be rejected too, but its status and body weren't captured. The tests treat a 401 with a configured token as "token expired" and skip.

## GET `/api/accounts/users/profile`

| Case | Status | Content-Type |
|---|---|---|
| valid token | **200** | `application/json; charset=utf-8` |

Response shape:
```json
{"first_name": null, "last_name": null}
```
Both fields were `null` for this account, and no other keys were returned. The email isn't part of this response.

## GET `/api/accounts/users/credits`

| Case | Status | Content-Type |
|---|---|---|
| valid token | **200** | `application/json; charset=utf-8` |

Response shape (types only):
```json
{
  "balance": {
    "balance": "int", "subscription_credits": "int", "purchased_credits": "int",
    "tier": "str", "monthly_allocation": "int", "topup_enabled": "bool",
    "is_unlimited": "bool", "usage_this_period": "int"
  },
  "tier_info": {"tier": "str", "monthly_credits": "int", "price_monthly": "int", "credit_value": "float"},
  "topup_packages": []
}
```
`topup_packages` was an empty list.

## GET `/api/dataset/analyzer/v2/projects/{project_id}/datasets`

| Case | Status | Content-Type |
|---|---|---|
| valid token | **200** | `application/json` (no `charset`, unlike the other two) |

The response is a **JSON list**. 8 items were observed: the 8 CSVs uploaded via From Device for the baseline and the 7 drift cases.

Item shape (types only):
```json
{
  "is_temp": "bool", "id": "int", "organization": "int", "title": "str", "description": "str",
  "file": "str", "file_size": "str", "content_type": "str", "is_local": "bool", "is_sample": "bool",
  "client_id": "str", "client_secret": "str", "object_url": "str", "user_id": "int",
  "project_id": "int", "data_array": "str", "transformations": {},
  "parameters": {
    "imputation": {"knn": {}, "mean": {}, "mice": {}, "mode": {}, "median": {}, "constant": {},
                   "forward_fill": {}, "backward_fill": {}, "decision_tree": {}, "random_forest": {},
                   "linear_regression": {}, "linear_interpolation": {}},
    "normalization": {"power": {}, "maxabs": {}, "minmax": {}, "robust": {}, "zscore": {},
                      "quantile": {}, "normalizer": {}},
    "outlier_detection": {"lof": {}, "tukey": {}, "std_dev": {}, "z_score": {}, "percentile": {},
                          "isolation_forest": {}}
  }
}
```

Observed values (non-identifying only):
- **`file` and `title`:** equal to each other on every item, and equal to the uploaded file names: `baseline.csv`, `schema_add_column.csv`, `schema_combined.csv`, `schema_drop_column.csv`, `schema_rename_column.csv`, `schema_type_change.csv`, `semantic_date_swap.csv`, `semantic_dollars_to_cents.csv`.
- **Flags:** `is_local` `true`, `is_temp` `false`, `is_sample` `false`, `content_type` `text/csv` on all items.
- **`project_id`:** equals the requested project on all items.
- **Empty on all 8 items:** `description` and `data_array`. `transformations` is an empty object.
- **`client_id` and `client_secret`:** present as **empty strings** on all 8 items.
- **`object_url`:** non-empty on all items (at most 82 characters), not an `https://` URL, and with no query string. The value is not recorded here.

Exposure check: no credential values were exposed in this response. Only empty `client_id` and `client_secret` fields appear (Info). Whether these fields are populated for other connection types, e.g. cloud sources, is **not observed**.

## Observed, not tested

- **`GET .../config/`:** returned **403** in DevTools while logged in. The full path and body weren't captured, so there's no test.
- **Failing S3 connect request (D1):** not captured, so there's no API test. The S3 failure is documented in `observations/setup-s3-connection-blocked.md`.
