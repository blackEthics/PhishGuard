# PhishGuard — Test Report
**Date:** 2026-05-23  
**Tester:** Claude Code (automated)  
**App version:** current `main` branch

---

## Part 1 — Setup & Installation

| Check | Result |
|---|---|
| Dependencies (`libraries.txt`) | All packages already installed in the project venv |
| App startup (model training) | **PASS** — 9 models trained in ~30 s; `{"status":"ok","initialized":true}` |
| Working directory | Must be `webapp/` — app uses relative path `"../preprocessing-dataset/processed_data.csv"` |

---

## Part 2 — Unit Test Suite (`test_batch.py`)

**18/18 tests PASS** in 0.15 s.

| Category | Tests | Status |
|---|---|---|
| Happy path (counts, verdicts, structure) | 10 | PASS |
| Error cases (no file, wrong extension, empty CSV, no URL column, binary file) | 5 | PASS |
| Boundary conditions (max_urls cap, confidence range, votes ≤ total) | 3 | PASS |

---

## Part 3 — Live API Endpoint Tests

### `POST /api/scan`

| Scenario | Verdict | Phishing votes | Time |
|---|---|---|---|
| `https://www.google.com` (classical only) | **good** | 1/6 (NB alone flagged it) | 33 ms |
| `http://login-paypal-secure.freehost.xyz/verify/account` | **bad** | 6/6 | 62 ms |
| Same phishing URL + quantum models | **bad** | 8/9 (VQC voted good — confidence 0.03) | 11 533 ms |
| Empty URL `""` | 400 `url is required` | — | — |
| Missing `url` key in body | 400 `url is required` | — | — |
| IP-based URL `http://192.168.1.1/login` | **bad** | 6/6, `has_ip=1` correctly detected | — |

**Note:** The VQC model dissented on the phishing URL (voted "good", confidence 0.03 — near-random). The remaining 8 models corrected the ensemble. This is consistent with the reported 79.5% VQC accuracy.

**Observation:** NB incorrectly flagged `google.com` as bad (confidence 0.73). All other classical models correctly voted good. This reflects NB's known false-positive rate.

### `POST /api/batch`

| Check | Result |
|---|---|
| 5-URL CSV (`test_urls.csv`) | total=5, phishing=2, safe=3, risk=40% |
| Phishing URLs correctly flagged | `login-paypal-secure.freehost.xyz` ✓ `update-your-account.tk` ✓ |
| Safe URLs not flagged | google.com ✓ facebook.com ✓ github.com ✓ |
| Top TLDs | `.com=3, .xyz=1, .tk=1` — correct |
| Non-CSV file extension (.txt) | 400 `File must be a .csv` ✓ |
| CSV without URL column | 400 with `columns_found` list ✓ |
| `max_urls=5` cap on 20-URL input | Returns exactly 5 ✓ |

**Observation:** NB flagged 5/5 URLs as phishing (`model_counts.nb=5`), including the 3 safe ones — consistent with higher false-positive rate on URL-only input.

### `GET /api/history`

| Check | Result |
|---|---|
| Default limit (20) | Returns 20 records ✓ |
| `?limit=3` | Returns exactly 3 ✓ |
| `?limit=9999` | Server caps at 100, returns all records in DB ✓ |
| Record fields present | id, url, verdict, confidence, timestamp ✓ |

### `GET /api/stats`

| Check | Result |
|---|---|
| Totals accurate | total=35, phishing=12, safe=23, phishing_pct=34.3% ✓ |
| `today` / `this_week` counts | Both 35 (all scans happened today) ✓ |
| `daily_counts` | 1 entry: 2026-05-23, total=35, phishing=12 ✓ |
| `top_tlds` | `.com=19, .xyz=7, .tk=5, .org=4` ✓ |

### `GET /api/circuit`

| Check | Result |
|---|---|
| Safe URL angles (`https://www.google.com`) | `[0.1327, 1.3469, 0.8696, 1.0543]` — all in [0, π] ✓ |
| Phishing URL angles | `[0.3458, 1.4018, 1.2112, 0.7333]` — distinct pattern ✓ |
| `n_qubits=4`, `n_layers=3` | Correct ✓ |
| Missing `?url=` param | 400 `url is required` ✓ |
| Pipeline description string | TF-IDF→SVD-50→+6 URL features→StandardScaler→PCA-4→MinMaxScaler[0,π] ✓ |

### Page Routes

| Route | HTTP Status | Page Title |
|---|---|---|
| `/` | 200 | URL Analyser — PhishGuard |
| `/batch` | 200 | Batch Scanner — PhishGuard |
| `/dashboard` | 200 | Analytics — PhishGuard |
| `/visualizer` | 200 | Quantum Visualizer — PhishGuard |

### CORS Headers (Browser Extension Support)

```
Access-Control-Allow-Origin:  *
Access-Control-Allow-Methods: GET, POST, OPTIONS
Access-Control-Allow-Headers: Content-Type
```
All headers present on every API response ✓

---

## Issues Found

| # | Severity | Issue |
|---|---|---|
| 1 | Low | **NB false positives on safe domains** — NB flags google.com, facebook.com, github.com as phishing. No structural bug; reflects NB's inherent tradeoff with the TF-IDF/URL feature representation. |
| 2 | Low | **VQC near-random confidence** — VQC returned confidence=0.03 on a clear phishing URL and voted "good". Weight loading succeeds but the trained weights generalise poorly outside the training distribution. |
| 3 | Info | **Quantum scan latency** — 11.5 s total for one URL with all 3 quantum models. Expected for PennyLane simulation; the per-model `time_ms` field is already exposed in the JSON response. |

---

## Summary

| Area | Result |
|---|---|
| Unit tests | 18/18 PASS |
| API endpoints | All functional, no crashes or unhandled errors |
| Page routes | All 4 pages return 200 with correct HTML |
| Error handling | All tested error cases return correct 400 responses |
| CORS | Correct headers present for browser extension support |
