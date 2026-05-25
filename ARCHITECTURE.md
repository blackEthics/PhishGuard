# PhishGuard — Architecture & Features

## Project Overview

PhishGuard is a phishing URL detection system built as a bachelor's final-year
project at Romanian-American University (2025-2026). It combines classical and
quantum machine learning models into a single web application with a browser
extension. The system detects phishing URLs by analysing URL structure and text
features — not blacklists — so it can catch brand-new phishing links that have
never been seen before.

---

## System Components

```
┌─────────────────────────────────────────────────────────────┐
│                     PhishGuard System                       │
│                                                             │
│  ┌──────────────────┐        ┌──────────────────────────┐   │
│  │ Browser Extension│◄──────►│    Flask Web Application │   │
│  │  (Chrome/Firefox)│  API   │       (localhost:5000)   │   │
│  └──────────────────┘        └──────────┬───────────────┘   │
│                                         │                   │
│                               ┌─────────▼─────────┐         │
│                               │   Model Pipeline  │         │
│                               │                   │         │
│                               │  Preprocessing:   │         │
│                               │  TF-IDF → SVD     │         │
│                               │  + URL Features   │         │
│                               │  → Scaler → PCA   │         │
│                               │  → MinMaxScaler   │         │
│                               │                   │         │ 
│                               │  9 Models:        │         │
│                               │  6 Classical      │         │
│                               │  3 Quantum        │         │
│                               └─────────┬─────────┘         │
│                                         │                   │
│                               ┌─────────▼─────────┐         │
│                               │   SQLite Database │         │
│                               │  (scan history)   │         │
│                               └───────────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

---

## Trained Models & Accuracy

| # | Model | Type | Accuracy | Training Samples | Test Samples |
|---|-------|------|----------|-----------------|--------------|
| 1 | Naive Bayes | Classical | **96.98%** | ~440k | ~110k |
| 2 | Logistic Regression | Classical | **92.49%** | ~440k | ~110k |
| 3 | MLP Neural Network | Classical | **92.32%** | 40k | 10k |
| 4 | Random Forest | Classical | **91.66%** | 40k | 10k |
| 5 | KNN (k=3) | Classical | **91.86%** | 40k | 10k |
| 6 | SVM (LinearSVC) | Classical | **90.37%** | 40k | 10k |
| 7 | VQC | Quantum | **79.50%** | 4k | 1k |
| 8 | QKNN (k=5) | Quantum | **77.80%** | 500 subset | 1k |
| 9 | QSVM | Quantum | **76.90%** | 500 subset | 1k |

All quantum models use: PCA(4 components) → MinMaxScaler([0, π]) → 4-qubit circuit.

---

## Data Pipeline (All Models Share This)

```
processed_data.csv (~549k rows)
        │
        ▼
Stratified sample
        │
        ▼
URL Feature Extraction (6 features):
  url_length, num_dots, num_digits,
  num_special_chars, has_ip, subdomain_depth
        │
        ▼
80/20 Train/Test Split (stratified, random_state=42)
        │
        ├──────────── Classical models use 50k rows ──────────────┐
        │                                                          │
        └──────────── Quantum models use 5k rows ─────────────────┘
        │
        ▼
TF-IDF Vectorization
  (sublinear_tf=True, min_df=2, max_features=50k–100k)
        │
        ▼
TruncatedSVD (50–200 components)
        │
        ▼
hstack [SVD features + 6 URL features]
        │
        ▼
StandardScaler (zero mean, unit variance)
        │
        ▼ (quantum models only)
PCA (4 components, one per qubit)
        │
        ▼ (quantum models only)
MinMaxScaler → [0, π]  (angle encoding range)
```

---

## Quantum Circuit Design (QKNN & QSVM)

```
q0: ──RY(x[0])──●──────────────X──
q1: ──RY(x[1])──X──●───────────│──
q2: ──RY(x[2])──────X──●───────│──
q3: ──RY(x[3])──────────X──────●──
     AngleEmbedding    CNOT ring
```

- **QKNN**: Quantum fidelity kernel K(x1,x2) = |⟨ψ(x1)|ψ(x2)⟩|², KNN majority vote
- **QSVM**: IQP feature map (Hadamard + RZ + ZZ interactions), SVC(kernel='precomputed')
- **VQC**: AngleEmbedding → 3 variational layers (RY+RZ+CNOT ring) → PauliZ measurements

---

## Web Application — Pages & Features

### Page 1: URL Analyser (Home — `/`)
- Single URL input form
- Visual URL dissector: breaks URL into scheme/subdomain/domain/TLD/path with colour coding (red = suspicious, green = safe)
- Feature panel: shows the 6 extracted features with warning icons
- Model comparison table: all 9 models vote simultaneously, showing verdict + confidence + response time
- Ensemble final verdict banner (majority vote): big green SAFE or red PHISHING
- Each scan is saved to SQLite database

### Page 2: Quantum Circuit Visualizer (`/visualizer`)
- URL input
- Renders the actual PennyLane circuit diagram for that URL's encoded features
- Shows the 4 angle values encoded (one per qubit) as a bar chart
- Plain-English explanation of each gate layer
- Side-by-side: QKNN circuit vs QSVM circuit vs VQC circuit

### Page 3: Batch Scanner (`/batch`)
- Upload a CSV file (must have a column named `url` or `URL`)
- Scans all URLs using fast classical models (NB + RF + LogReg — quantum skipped for speed)
- Results page:
  - Summary cards: Total / Phishing / Safe / Risk %
  - Full results table with verdict + confidence per URL
  - Bar chart: phishing vs safe breakdown by model
  - Pie chart: overall verdict distribution
- Download button: exports `security_report.csv`

### Page 4: Analytics Dashboard (`/dashboard`)
- Historical stats from SQLite: total scans today / this week / all time
- Most common phishing TLDs detected (.xyz, .tk, .ml, etc.)
- Model accuracy comparison bar chart (from thesis results, static)
- Classical vs Quantum speed comparison chart
- Recent scan history table (last 20 scans)

---

## Flask API Endpoints

| Method | Endpoint | Input | Returns |
|--------|----------|-------|---------|
| POST | `/api/scan` | `{"url": "..."}` | verdict, confidence, per-model results, features |
| POST | `/api/batch` | CSV file upload | list of verdicts, summary stats |
| GET | `/api/circuit` | `?url=...` | circuit diagram HTML, encoded angles |
| GET | `/api/history` | — | last 50 scans from SQLite |
| GET | `/api/stats` | — | aggregate stats for dashboard |

---

## Browser Extension

Works in Chrome and Firefox (Manifest V3).

**Behaviour 1 — Hover Tooltip:**
- Content script watches all `<a>` tags on every page
- On hover: sends URL to Flask `/api/scan`
- Shows small popup tooltip: verdict + confidence + top 3 reasons
- Colour: green border (safe) or red border (phishing)

**Behaviour 2 — Navigation Block:**
- Background service worker intercepts navigation events
- If verdict is HIGH risk (confidence > 85%): injects full-page warning overlay
- User can dismiss and proceed, or go back

**Toolbar Popup:**
- Click the PhishGuard icon in the browser toolbar
- Shows verdict for the current tab's URL
- Link to open full analysis in the web app

**Files:**
```
browser_extension/
├── manifest.json
├── content.js          ← hover tooltip logic
├── background.js       ← navigation intercept, service worker
├── popup.html          ← toolbar popup UI
├── popup.js            ← toolbar popup logic
├── popup.css
├── warning.html        ← full-page block overlay
├── warning.css
└── icons/
    ├── icon16.png
    ├── icon48.png
    └── icon128.png
```

---

## Planned Folder Structure (Web App)

```
phishing_site_root/
├── webapp/
│   ├── app.py                    ← Flask app entry point
│   ├── models/
│   │   ├── __init__.py
│   │   ├── loader.py             ← loads & caches all models on startup
│   │   ├── classical.py          ← prediction logic for classical models
│   │   └── quantum.py            ← prediction logic for quantum models
│   ├── api/
│   │   ├── __init__.py
│   │   ├── scan.py               ← /api/scan route
│   │   ├── batch.py              ← /api/batch route
│   │   └── circuit.py            ← /api/circuit route
│   ├── database/
│   │   ├── db.py                 ← SQLite connection + schema
│   │   └── scans.db              ← auto-created on first run
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css
│   │   └── js/
│   │       ├── analyser.js       ← URL analyser page logic
│   │       ├── batch.js          ← batch scanner page logic
│   │       └── dashboard.js      ← dashboard charts (Chart.js)
│   └── templates/
│       ├── base.html             ← shared layout, navbar
│       ├── index.html            ← URL analyser
│       ├── visualizer.html       ← quantum circuit
│       ├── batch.html            ← batch scanner
│       └── dashboard.html        ← analytics
└── browser_extension/
    ├── manifest.json
    ├── content.js
    ├── background.js
    ├── popup.html / popup.js / popup.css
    ├── warning.html / warning.css
    └── icons/
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.x, Flask |
| ML Models | scikit-learn, PennyLane |
| Database | SQLite (via Python sqlite3) |
| Frontend | HTML5, Bootstrap 5, vanilla JavaScript |
| Charts | Chart.js (CDN) |
| Quantum drawing | PennyLane `qml.draw()` |
| Browser extension | JavaScript, Manifest V3 |

---

## How the Web App Loads Models

Because `.pkl` files are gitignored, the web app rebuilds the preprocessing
pipeline from the CSV on startup, then retrains the fast classical models
(takes ~30 seconds). Quantum model weights are loaded from saved `.npy` files.

Startup sequence in `loader.py`:
1. Load `processed_data.csv`, take 5k stratified sample
2. Rebuild: TF-IDF → SVD → StandardScaler → PCA → MinMaxScaler (fit on train split)
3. Retrain: KNN, LogReg, NB, SVM, RF, MLP (fast — seconds each)
4. Load quantum models:
   - QKNN: load `fidelity_matrix.npy` + training labels from re-derived split
   - QSVM: load `kernel_matrix_train.npy` + kernel_matrix_test.npy, refit SVC
   - VQC: load `vqc_weights.npy`, reconstruct circuit

---

## University Requirements Coverage

| Requirement | How It Is Met |
|-------------|--------------|
| Software product | Flask web app + browser extension |
| Live demo | Open browser during defense, type any URL |
| Ch1 — Existing systems | Compare vs VirusTotal, Google Safe Browsing, PhishTank |
| Ch2 — Overall design | System diagram above, API design, database schema |
| Ch3 — Detailed design | Each model algorithm, quantum circuit, pipeline |
| Ch4 — App + economic efficiency | App itself + batch scanner business case |
| ≥5 international bibliography | Havlíček 2019, Schuld 2019, IBM Cost of Breach Report, IEEE phishing papers |
| Economic efficiency | $4.9M average cost per breach; tool scans 1000 URLs/min vs 50/day manually |
