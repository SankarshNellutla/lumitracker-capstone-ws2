# LumiTracker Capstone

## WS2: Asset-Level Aggregation and Prioritization

This repository contains the implementation for Workstream 2 of the LumiTracker capstone project.

The goal of WS2 is to take the governed cleaned luminosity observations from Workstream 1, match them to nearby lighting assets, identify underperforming assets, rank them by severity, and generate report-ready tables and visuals.

This workstream uses the cleaned dataset prepared in WS1 and does not redo upstream preprocessing.

---

## Project Objective

The main objective of this workstream is to support asset-level maintenance prioritization by answering the following question:

**Which street lighting assets show the strongest and most consistent signs of underperformance based on the cleaned LumiTracker observations?**

To answer this, the workflow:

- Uses the cleaned luminosity file from WS1
- Matches observations to nearby lighting assets
- Aggregates results at asset level
- Computes underperformance metrics
- Assigns severity tiers
- Produces ranked tables, validation summaries, and maps

---

## Scope of This Repo

This repository currently contains the WS2 implementation for:

- Asset-level spatial matching
- Asset-level aggregation
- Underperforming asset prioritization
- Severity tier assignment
- Output table generation
- Static and interactive visual generation
- Validation and summary reporting

This repository does **not** perform:

- WS1 preprocessing
- Threshold recalculation
- Crosswalk analysis
- Spatial clustering
- Policy recommendation analysis

---

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd lumitracker_capstone
   ```

2. Create a virtual environment and activate it:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

---

## Input Files

**Important**: Some input files are too large for GitHub and must be obtained separately.

### Required input files (obtain from WS1 or project data source):
- `data/processed/workstream1_clean_lux.csv` *(~360MB - not included in repo)*

### GIS asset inputs (included in repo):
- `data/raw/gis/City of Sugar Land Streetlight locations.xlsx`
- `data/raw/gis/City of Sugar Land Traffic Roadway Lights locations.xlsx`

### Reference-only file (included in repo):
- `data/raw/gis/Avalon private street lights map.pdf`

**Note**: The `workstream1_clean_lux.csv` file is generated output from Workstream 1 and is too large for GitHub. Contact your team or project coordinator to obtain this file and place it in `data/processed/` before running the analysis.

---

## Usage

Run the analysis using the provided shell script:

```bash
bash scripts/run_ws2.sh
```

This will execute the asset prioritization workflow with default parameters. The script sets up the necessary directories, runs the Python module, and logs the output.

### Custom Parameters

You can modify the script or run the Python module directly with custom parameters:

```bash
python -m ws2.asset_prioritization \
  --input-lux data/processed/workstream1_clean_lux.csv \
  --streetlights data/raw/gis/City\ of\ Sugar\ Land\ Streetlight\ locations.xlsx \
  --traffic-lights data/raw/gis/City\ of\ Sugar\ Land\ Traffic\ Roadway\ Lights\ locations.xlsx \
  --avalon-pdf data/raw/gis/Avalon\ private\ street\ lights\ map.pdf \
  --output-dir outputs/ws2 \
  --max-distance-ft 100 \
  --min-observations 20 \
  --asset-flag-threshold 0.30
```

### Parameters

- `--input-lux`: Path to the cleaned luminosity CSV from WS1
- `--streetlights`: Path to the streetlight locations Excel file
- `--traffic-lights`: Path to the traffic roadway lights Excel file
- `--avalon-pdf`: Path to the Avalon PDF reference (optional)
- `--output-dir`: Directory for output files
- `--max-distance-ft`: Maximum distance in feet for matching observations to assets (default: 100)
- `--min-observations`: Minimum number of observations required for reliable asset classification (default: 20)
- `--asset-flag-threshold`: Threshold for flagging underperforming assets (default: 0.30)

---

## Outputs

The analysis generates the following outputs in the `outputs/ws2/` directory:

### Tables (`tables/`)
- `asset_level_ranked.csv`: Ranked list of underperforming assets
- `asset_risk_summary.csv`: Summary of asset risk levels
- `asset_source_summary.csv`: Summary by asset source
- `severity_tier_summary.csv`: Summary by severity tiers
- `top20_underperforming_assets.csv`: Top 20 underperforming assets
- `ws2_validation_template.csv`: Validation template

### Figures (`figures/`)
- `flagged_assets_map.html`: Interactive map of flagged assets

### Logs (`logs/`)
- Timestamped log files for each run

---

## Repo Structure

```
lumitracker_capstone/
├── .gitignore
├── data/
│   ├── processed/
│   │   └── workstream1_clean_lux.csv
│   └── raw/
│       └── gis/
│           ├── City of Sugar Land Streetlight locations.xlsx
│           ├── City of Sugar Land Traffic Roadway Lights locations.xlsx
│           └── Avalon private street lights map.pdf
├── docs/
│   ├── index.html
│   └── flagged_assets_map.html
├── outputs/
│   └── ws2/
│       ├── figures/
│       ├── logs/
│       └── tables/
├── scripts/
│   └── run_ws2.sh
├── src/
│   └── ws2/
│       ├── __init__.py
│       └── asset_prioritization.py
├── README.md
└── requirements.txt
```

---

## GitHub Pages

This repository includes a `docs/` folder with an interactive map visualization that can be published to GitHub Pages.

### Setup GitHub Pages

1. **Create a GitHub repository** and push this code:
   ```bash
   # Add your GitHub remote (replace with your repo URL)
   git remote add origin https://github.com/yourusername/lumitracker-ws2.git
   git branch -M main
   git push -u origin main
   ```

2. **Enable GitHub Pages** in your repository:
   - Go to Settings → Pages
   - Select "Deploy from a branch"
   - Choose "main" branch and "/docs" folder
   - Click Save

3. **Access your site** at: `https://yourusername.github.io/lumitracker-ws2/`

The main page (`index.html`) provides an overview and links to the interactive asset prioritization map.

---

## Dependencies

See `requirements.txt` for the list of Python packages required. Key dependencies include:

- pandas: Data manipulation
- numpy: Numerical computations
- scikit-learn: Machine learning utilities
- openpyxl: Excel file handling
- matplotlib: Static plotting
- folium: Interactive maps

---

## Contributing

Please follow standard Git practices for contributions. Ensure all changes are tested and documented.

---

## License

[Add license information here if applicable]

## Environment Setup

This project uses Python 3.11.

### Create and activate virtual environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

### Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Dependencies

Main Python packages used:

* pandas
* numpy
* scikit-learn
* openpyxl
* matplotlib
* folium

These packages support file loading, nearest-neighbor spatial matching, aggregation, figure generation, and interactive mapping.

---

## How to Run

Run the full WS2 pipeline from the project root:

```bash
bash scripts/run_ws2.sh
```

This script:

* Sets the repo root
* Adds `src` to `PYTHONPATH`
* Creates output folders if needed
* Creates a timestamped log file
* Runs the WS2 asset prioritization pipeline

---

## Analysis Workflow

The WS2 workflow follows these steps:

1. Load the governed cleaned luminosity dataset from WS1
2. Load city streetlight and traffic roadway GIS asset layers
3. Validate required columns
4. Standardize asset columns to a common schema
5. Exclude traffic records with subtype `Service Meter`
6. Build a nearest-neighbor search index using haversine distance
7. Match luminosity readings to the nearest asset within 100 feet
8. Aggregate matched readings at the asset level
9. Compute underperformance metrics for each asset
10. Apply the asset flag rule
11. Assign severity tiers
12. Rank assets by severity and risk
13. Export final tables and figures

---

## Key Methodology Decisions

### Governed input

This workflow uses the cleaned luminosity file from WS1 as the authoritative source.

The following were not recalculated in WS2:

* Lux_mean
* 99.5% cap
* 15th percentile threshold
* low_performance flag

### Spatial matching method

Nearest-neighbor matching with haversine distance was used.

Reason:
LumiTracker readings are mobile GPS observations, while lighting assets are fixed points. Exact point overlap is not expected, so nearest-neighbor matching is the practical method.

### Distance tolerance

A maximum match tolerance of **100 feet** was used.

### Asset flag rule

An asset is flagged if:

* it has at least **20 matched observations**
* and at least **30%** of those observations are `low_performance`

### Severity tiers

Assets are classified as:

* **Critical**: 50% or more low_performance
* **High**: 30% to under 50%
* **Moderate**: 15% to under 30%
* **Low**: under 15%
* **Insufficient data**: fewer than 20 matched observations

---

## Important Data Quality Fix

During development, the traffic roadway asset layer was found to include records with subtype `Service Meter`.

These are not actual lighting fixtures. They are support infrastructure.

To keep the asset ranking valid, traffic records with subtype `Service Meter` were excluded from the automated analysis.

This improved the quality of the traffic asset results and ensured the ranked outputs focused on actual lighting assets.

---

## Output Files

After running the pipeline, the following outputs are created.

### Tables

`outputs/ws2/tables/asset_level_ranked.csv`
Full ranked list of all matched assets

`outputs/ws2/tables/top20_underperforming_assets.csv`
Clean Top 20 underperforming asset table

`outputs/ws2/tables/asset_risk_summary.csv`
Overall WS2 run summary and risk counts

`outputs/ws2/tables/severity_tier_summary.csv`
Count of assets by severity tier

`outputs/ws2/tables/ws2_validation_template.csv`
Validation metrics for governance and integration

`outputs/ws2/tables/asset_source_summary.csv`
Comparison of city streetlights and traffic roadway lights

### Figures

`outputs/ws2/figures/top20_underperforming_assets.png`
Top 20 underperforming assets chart

`outputs/ws2/figures/flagged_assets_map.png`
Static flagged assets map

`outputs/ws2/figures/flagged_assets_map.html`
Interactive flagged assets map

### Logs

`outputs/ws2/logs/`
Timestamped run logs for troubleshooting and reruns

---

## Final Run Settings

The final validated run used:

* Join method: `nearest_neighbor_haversine`
* Distance tolerance: `100 ft`
* Minimum observations: `20`
* Asset flag threshold: `0.30`

---

## Final Results Snapshot

### Overall WS2 run

* Total input rows: **2,455,221**
* Eligible rows for join: **2,455,221**
* Matched rows within 100 feet: **1,814,825**
* Assets with matches: **12,569**
* Flagged assets: **5,044**

### Validation summary

* Zero readings count: **567,743**
* Zero readings percent: **23.1239**
* Cap value used: **24.766667 lux**
* Cutoff value used: **0.556667 lux**
* Low_performance count: **951,497**
* Low_performance share: **38.754%**

### Asset source summary

#### City streetlight

* Assets with matches: **12,321**
* Flagged assets: **4,916**
* Critical: **3,203**
* High: **1,713**
* Moderate: **1,531**
* Low: **5,778**
* Insufficient data: **96**
* Average percent low performance: **28.49**
* Median observation count: **104.0**
* Flag rate: **39.9%**

#### Traffic roadway light

* Assets with matches: **248**
* Flagged assets: **128**
* Critical: **66**
* High: **62**
* Moderate: **33**
* Low: **85**
* Insufficient data: **2**
* Average percent low performance: **35.29**
* Median observation count: **118.5**
* Flag rate: **51.61%**

---

## Validation Performed

The following checks were completed during development:

* Verified repo structure and file placement
* Installed all required dependencies
* Compiled the main Python file successfully
* Confirmed module CLI works
* Validated shell script syntax
* Ran the full pipeline end to end
* Verified summary counts for consistency
* Reviewed ranked asset outputs
* Inspected asset source behavior
* Corrected traffic Service Meter records
* Reran pipeline and verified cleaner results
* Exported validation and summary files for reporting

---

## Troubleshooting

### ModuleNotFoundError: No module named ws2

Cause: `src` is not on `PYTHONPATH`

Fix:

```bash
PYTHONPATH=src python -m ws2.asset_prioritization --help
```

Or use the run script:

```bash
bash scripts/run_ws2.sh
```

### Shell script runs but does nothing

Cause: script may be empty, unsaved, or not executable

Fix:

```bash
cat scripts/run_ws2.sh
chmod +x scripts/run_ws2.sh
bash -n scripts/run_ws2.sh
```

### Traffic assets include Service Meter records

Cause: traffic GIS file includes non-light support infrastructure

Fix: confirm that rows with subtype `Service Meter` are excluded in the Python pipeline

### Very low match count

Possible causes:

* wrong GIS files
* invalid coordinates
* distance tolerance too strict
* broken numeric parsing

Fix:
Check file paths, coordinate fields, and tolerance setting

### Validation values do not match expectations

Possible causes:

* wrong input CSV
* modified governed file
* logic changes to low_performance handling

Fix:
Confirm that `workstream1_clean_lux.csv` is the governed WS1 file and that WS2 is not recalculating upstream thresholds

### Avalon not included in results

Cause: Avalon file is a PDF reference map, not a machine-readable asset layer

Fix:
Document it as a limitation unless a proper coordinate layer is provided

---

## Standard Commands

### Activate environment

```bash
source .venv/bin/activate
```

### Run Python syntax check

```bash
python -m py_compile src/ws2/asset_prioritization.py
```

### Run the pipeline

```bash
bash scripts/run_ws2.sh
```

### View summary outputs

```bash
cat outputs/ws2/tables/asset_risk_summary.csv
cat outputs/ws2/tables/severity_tier_summary.csv
cat outputs/ws2/tables/ws2_validation_template.csv
cat outputs/ws2/tables/asset_source_summary.csv
```

### Preview Top 20 underperforming assets

```bash
python - <<'PY'
import pandas as pd
df = pd.read_csv("outputs/ws2/tables/top20_underperforming_assets.csv")
print(df.to_string(index=False))
PY
```

---

## Limitations

* WS2 depends on the governed WS1 cleaned file
* Avalon was not included in the automated join because the available file is a PDF map
* The workflow prioritizes operational asset ranking, not causal diagnosis
* Asset matching depends on GPS proximity and a fixed 100-foot tolerance

---

## Final Status

This WS2 implementation is complete and usable.

It:

* uses the governed cleaned dataset from WS1
* matches observations to actual lighting assets
* aggregates performance at the asset level
* removes non-light Service Meter records from traffic assets
* assigns severity tiers
* ranks assets for maintenance prioritization
* generates final tables and visuals
* exports validation and source-level summaries
* documents Avalon correctly as a limitation

This is the final stable state of the work. At this point, further random edits would mostly be a hobby, not an improvement.

```