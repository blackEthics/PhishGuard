# PhishGuard — Build Progress
# READ THIS FILE FIRST in every new Claude session.
# It tells you exactly what exists, what works, and what needs to be built next.

---

## Project Identity

- **Project:** PhishGuard — Phishing URL Detection System
- **Student:** Farhan (GitHub: farhan-farabi23)
- **University:** Romanian-American University, Bucharest
- **Degree:** Bachelor of Science, Computer Science for Business Management
- **Academic Year:** 2025–2026
- **Language:** Python (backend), JavaScript (browser extension)
- **Repository:** https://github.com/farhan-farabi23/bachelor-final-project
- **Working directory:** `C:\Users\RANON TRASH\Desktop\final-year-project\phishing_site_root\`

---

## What This Project Is

A phishing URL detection system with:
1. **9 trained ML models** (6 classical + 3 quantum) — ALL DONE
2. **Flask web application** with 4 feature pages — NOT BUILT YET
3. **Browser extension** (Chrome/Firefox) — NOT BUILT YET

Full architecture details are in `ARCHITECTURE.md` (same folder as this file).

---

## Part 1 — ML Models (COMPLETE)

### Data
- **Source file:** `preprocessing-dataset/processed_data.csv`
- **Size:** ~549,346 rows
- **Columns:** `URL` (raw URL), `Label` ("good"/"bad"), `processed_text` (tokenized URL)
- **Preprocessing notebook:** `preprocessing-dataset/data_preprocessing.ipynb`

### Model Accuracy Results (Official)

| Model | Folder | Accuracy | Notes |
|-------|--------|----------|-------|
| Naive Bayes | `model_logreg_nb/` | **96.98%** | Best classical model |
| Logistic Regression | `model_logreg_nb/` | **92.49%** | Same notebook as NB |
| MLP Neural Network | `model_mlp_nn/` | **92.32%** | |
| KNN (k=3) | `model_knn/` | **91.86%** | |
| Random Forest | `model_random_forest/` | **91.66%** | |
| SVM (LinearSVC) | `model_svm_rbf_kernel/` | **90.37%** | |
| VQC | `model_VQC/` | **79.50%** | Quantum |
| QKNN (k=5) | `model_qknn/` | **77.80%** | Quantum |
| QSVM | `model_qsvm/` | **76.90%** | Quantum |

### Saved Artifacts Per Model

All models save results to their own `result/` subfolder.
NOTE: `.pkl` files are gitignored — models must be retrained for the web app.
`.npy` files ARE tracked by git.

```
model_knn/result/
  └── confusion_matrix.png

model_logreg_nb/result/
  ├── confusion_matrix_logreg.png
  └── confusion_matrix_nb.png

model_mlp_nn/result/
  └── confusion_matrix_mlp_nn.png

model_random_forest/result/
  └── confusion_matrix_random_forest.png

model_svm_rbf_kernel/result/
  └── confusion_matrix_svm.png

model_qknn/result/
  ├── fidelity_matrix.npy        ← (1000 test × 500 train) quantum fidelity values
  ├── fidelity_matrix_val.npy    ← (100 val × 500 train)
  └── confusion_matrix_qknn.png

model_qsvm/result/
  ├── kernel_matrix_train.npy    ← (500 × 500) quantum kernel matrix
  ├── kernel_matrix_test.npy     ← (1000 × 500) quantum kernel matrix
  └── confusion_matrix_qsvm.png

model_VQC/result/
  ├── vqc_weights.npy            ← trained VQC rotation angles, shape (3, 4, 2)
  ├── training_curve_vqc.png
  └── confusion_matrix_vqc.png
```

### Quantum Model Config (same across all 3 quantum models)

```python
n_qubits         = 4
n_pca_components = 4
sample_size      = 5000
svd_components   = 50
angle_range      = [0, π]
encoding         = "AngleEmbedding (RY gates)"
device           = "default.qubit"
```

### Key Pipeline for Quantum Models (use exact same in web app)

```
processed_data.csv
→ 5,000 stratified sample
→ extract_url_features() → 6 numeric features
→ 80/20 train/test split (random_state=42)
→ TfidfVectorizer(sublinear_tf=True, min_df=2, max_features=50000) — fit on train
→ TruncatedSVD(n_components=50) — fit on train
→ hstack [SVD(50) + URL features(6)] → shape (n, 56)
→ StandardScaler() — fit on train
→ PCA(n_components=4) — fit on train
→ MinMaxScaler(feature_range=(0, np.pi)) — fit on train
→ angle-encoded features ready for quantum circuit
```

---

## Part 2 — Flask Web Application (COMPLETE)

### Status: 100% complete. All 4 pages built. Modular package structure.

### Folder: `phishing_site_root/webapp/`

### To start the app:
```
cd phishing_site_root/webapp/
python app.py
```
Loads all 9 models (~15 seconds), then serves on http://localhost:5000

### Pages:

- [x] **Page 1 — URL Analyser** (`/`) — DONE
  - Single URL input + quantum toggle
  - Visual URL dissector (colour-coded: protocol / subdomain / domain / TLD / path)
  - 6-feature panel with warning icons
  - Model comparison table (all 9 models, verdict + confidence bar + time)
  - Ensemble verdict banner (green/red)
  - Saves each scan to SQLite via `db.save_scan()`

- [x] **Page 2 — Batch Scanner** (`/batch`) — DONE
  - CSV upload (detects column: `url`, `URL`, `link`, `address`)
  - Scans all URLs using 6 classical models only (quantum skipped for speed)
  - Summary cards: Total / Phishing / Safe / Risk %
  - Doughnut chart (Safe vs Phishing) + Bar chart (phishing count per model)
  - Top-5 TLD badge strip
  - Scrollable results table (sticky header, red-tinted phishing rows)
  - Download `security_report.csv` button (browser-side, no extra endpoint)
  - Cap: 1,000 URLs per upload; `save_scans_batch()` uses single transaction
  - 18/18 unit tests pass (Flask test client, torch-free)

- [x] **Page 3 — Analytics Dashboard** (`/dashboard`) — DONE
  - 6 summary cards (total, phishing, safe, risk rate, today, last 7 days)
  - Line chart: scans per day for last 7 days (total + phishing)
  - Doughnut chart: all-time safe vs phishing split
  - Horizontal bar chart: all 9 model accuracies (thesis data, purple=quantum)
  - Logarithmic bar chart: prediction speed classical vs quantum
  - TLD bar chart from live scan history (hidden when empty)
  - Recent scan history table (last 20, truncated URLs, timestamps)
  - ↺ Refresh button; destroyChart() prevents canvas-reuse error

- [x] **Page 4 — Quantum Circuit Visualizer** (`/visualizer`) — DONE
  - URL input → calls `/api/circuit` → gets 4 PCA angle values
  - Angle bar chart (coloured by magnitude 0→blue, π→red) with [0,π] y-axis
  - Circuit architecture table (qubit rows: AngleEmbedding · Layer1-3 · Measure)
  - 6-step pipeline explanation cards (TF-IDF → SVD → Scaler → PCA → MinMax → VQC)
  - Angle parameter table (rad, degrees, gate, meaning per qubit)

### API Endpoints:

- [x] `POST /api/scan` — single URL, all 9 models, saves to DB, returns full results
- [x] `POST /api/batch` — CSV upload, 6 classical models, saves batch to DB
- [x] `GET /api/health` — returns `{"status": "ok", "initialized": true}`
- [x] `GET /api/circuit?url=...` — returns 4 quantum angles + pipeline metadata
- [x] `GET /api/history` — last N scans (default 20, max 100)
- [x] `GET /api/stats` — aggregate stats + daily breakdown + top TLDs
- [x] CORS headers on all endpoints (for browser extension)

### Package Structure:

```
webapp/
├── app.py                    ← Flask app + blueprint registration + CORS
├── models/
│   ├── __init__.py
│   ├── quantum.py            ← PennyLane circuits: VQC, QKNN fidelity, QSVM IQP kernel
│   └── loader.py             ← full training pipeline + predict_all() + get_angles_for_url()
├── api/
│   ├── __init__.py
│   ├── scan.py               ← /api/scan, /api/health, /api/stats, /api/history
│   ├── batch.py              ← /api/batch
│   └── circuit.py            ← /api/circuit
├── database/
│   ├── __init__.py
│   └── db.py                 ← SQLite helpers (DB at webapp/phishguard.db)
├── templates/
│   ├── base.html             ← Bootstrap 5.3 + Chart.js 4.4 + 4 JS files
│   ├── index.html            ← Page 1
│   ├── batch.html            ← Page 2
│   ├── dashboard.html        ← Page 3
│   └── visualizer.html       ← Page 4
├── static/
│   ├── css/style.css
│   └── js/
│       ├── analyser.js       ← URL Analyser JS
│       ├── batch.js          ← Batch Scanner JS
│       ├── dashboard.js      ← Analytics Dashboard JS
│       └── visualizer.js     ← Quantum Visualizer JS
├── test_batch.py             ← 18 tests, all passing (updated for new import paths)
└── phishguard.db             ← SQLite scan history
```

---

## Part 3 — Browser Extension (DONE)

### Status: 100% complete.

### Folder: `phishing_site_root/browser_extension/`

### How to load in Chrome:
1. Run `python generate_icons.py` once (creates icons/ — already done)
2. Open `chrome://extensions`
3. Enable **Developer mode** (top-right toggle)
4. Click **Load unpacked** → select the `browser_extension/` folder
5. Start Flask: `cd webapp && python app.py`

### Files:

- [x] `manifest.json` — Chrome Manifest V3; permissions: activeTab, tabs, storage, webNavigation
- [x] `content.js` — hover tooltip on all `<a>` tags (400ms debounce, result cache, routes
  scan through background.js to avoid CORS); injects full-page warning overlay when
  background.js sends `showWarning` message
- [x] `background.js` — service worker: handles `scan` messages from content/popup, POSTs
  to `/api/scan` (include_quantum: false for speed); intercepts `webNavigation.onBeforeNavigate`,
  redirects to warning.html if `phishing_votes / total_models >= 0.80`
- [x] `popup.html` + `popup.js` + `popup.css` — toolbar icon popup; auto-scans active tab,
  shows SAFE/PHISHING verdict, vote progress bar, per-model badges (KNN/LogReg/NB/SVM/RF/MLP),
  rescan button, link to web app
- [x] `warning.html` + `warning.css` — standalone full-page block overlay; shows blocked URL,
  votes/total/risk-% stats, "Go Back (Safe)" and "Proceed Anyway" buttons; no CDN deps
- [x] `icons/icon16.png`, `icons/icon48.png`, `icons/icon128.png` — generated by generate_icons.py
- [x] `generate_icons.py` — stdlib-only PNG generator (no Pillow needed); draws purple shield
  with white checkmark

### How the Extension Works:
1. **Hover tooltip**: content.js debounces 400ms on any `<a>` → sends `{action:"scan", url}` to
   background.js → background.js POSTs to `localhost:5000/api/scan` → result shown in tooltip
2. **Navigation block**: background.js listens on `webNavigation.onBeforeNavigate` → scans URL →
   if ≥80% of 6 classical models flag it, redirects tab to warning.html before page renders
3. **Toolbar popup**: popup.js queries active tab URL → sends scan message → renders result with
   vote bar and per-model badges

### IMPORTANT: For thesis defense, Flask must be running on localhost:5000

---

## Libraries

All required libraries are listed in `libraries.txt`.
Install with: `pip install -r libraries.txt`
PyTorch install: `pip install torch --index-url https://download.pytorch.org/whl/cpu`

---

## Git & File Notes

- `.pkl` files → gitignored (too large, 63MB–126MB)
- `.txt` files → gitignored EXCEPT `libraries.txt` (has `!phishing_site_root/libraries.txt` exception)
- `.npy` files → tracked by git (quantum matrices, VQC weights)
- `.png` files → tracked by git (confusion matrices, training curves)
- `phishing_site_urls.csv` → gitignored (too large)
- `CLAUDE.md` → gitignored

---

## Recommended Build Order for Next Sessions

1. ~~**Session A:** Build Flask app skeleton + `loader.py` + `/api/scan` endpoint~~ ✅
2. ~~**Session B:** Build Page 1 — URL Analyser with model comparison table~~ ✅
3. ~~**Session C:** Build Page 2 — Batch Scanner~~ ✅
4. ~~**Session D:** Build Page 3 — Analytics Dashboard (`/dashboard`)~~ ✅
5. ~~**Session E:** Build Page 4 — Quantum Circuit Visualizer (`/visualizer`)~~ ✅
6. ~~**Session F:** Build Browser Extension (content.js + popup + warning overlay)~~ ✅
7. **Session G:** Final polish — mobile responsive, cross-browser test, thesis screenshots

---

## Current Status Summary

```
[DONE]  preprocessing-dataset/   ← data cleaning, TF-IDF pipeline
[DONE]  model_knn/               ← KNN 91.86%
[DONE]  model_logreg_nb/         ← LogReg 92.49%, NB 96.98%
[DONE]  model_mlp_nn/            ← MLP 92.32%
[DONE]  model_random_forest/     ← RF 91.66%
[DONE]  model_svm_rbf_kernel/    ← SVM 90.37%
[DONE]  model_qknn/              ← QKNN 77.80%
[DONE]  model_qsvm/              ← QSVM 76.90%
[DONE]  model_VQC/               ← VQC 79.50%
[DONE]  libraries.txt            ← pip install list
[DONE]  ARCHITECTURE.md          ← full architecture document
[DONE]  PROGRESS.md              ← this file

[DONE]  webapp/app.py            ← all routes wired; BATCH_MAX_URLS constant
[DONE]  webapp/loader.py         ← 9 models at startup; torch optional (graceful fallback)
[DONE]  webapp/db.py             ← save_scan, save_scans_batch, get_stats, get_recent_scans, get_dashboard_stats, get_recent_history
[DONE]  webapp/templates/base.html      ← Bootstrap 5.3 + Chart.js 4.4
[DONE]  webapp/templates/index.html     ← Page 1 URL Analyser (full)
[DONE]  webapp/templates/batch.html     ← Page 2 Batch Scanner (full)
[DONE]  webapp/templates/dashboard.html ← Page 3 Analytics Dashboard (full)
[DONE]  webapp/static/js/main.js        ← URL Analyser + Batch Scanner + Dashboard JS
[DONE]  webapp/static/css/style.css     ← all styles
[DONE]  webapp/test_batch.py            ← 18 tests, all passing

[DONE]  webapp/models/quantum.py         ← PennyLane circuits (VQC, QKNN, QSVM)
[DONE]  webapp/models/loader.py          ← training pipeline + predict_all + get_angles_for_url
[DONE]  webapp/api/scan.py               ← Blueprint: /api/scan /api/health /api/stats /api/history
[DONE]  webapp/api/batch.py              ← Blueprint: /api/batch
[DONE]  webapp/api/circuit.py            ← Blueprint: /api/circuit
[DONE]  webapp/database/db.py            ← SQLite helpers (moved from flat db.py)
[DONE]  webapp/templates/visualizer.html ← Page 4 Quantum Visualizer (full)
[DONE]  webapp/static/js/analyser.js     ← URL Analyser JS (split from main.js)
[DONE]  webapp/static/js/batch.js        ← Batch Scanner JS (split from main.js)
[DONE]  webapp/static/js/dashboard.js    ← Analytics Dashboard JS (split from main.js)
[DONE]  webapp/static/js/visualizer.js   ← Quantum Visualizer JS (new)

[DONE]  browser_extension/manifest.json     ← MV3, activeTab+tabs+storage+webNavigation
[DONE]  browser_extension/background.js     ← service worker: scan proxy + nav intercept
[DONE]  browser_extension/content.js        ← hover tooltip + overlay injection
[DONE]  browser_extension/popup.html/js/css ← toolbar popup with vote bar + model badges
[DONE]  browser_extension/warning.html/css  ← standalone block page (no CDN)
[DONE]  browser_extension/generate_icons.py ← stdlib-only PNG icon generator
[DONE]  browser_extension/icons/            ← icon16.png, icon48.png, icon128.png (generated)
```
