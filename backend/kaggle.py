"""Kaggle integration — fetch competition info and download datasets.

Detects Kaggle URLs in user input, pulls competition metadata via
the Kaggle Python API, and downloads datasets to a local directory.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

# Regex to extract competition slug from various Kaggle URL formats
_KAGGLE_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?kaggle\.com/competitions/([a-zA-Z0-9_-]+)"
)


def extract_competition_id(text: str) -> str | None:
    """Extract a Kaggle competition ID from user input.

    Supports:
    - https://www.kaggle.com/competitions/titanic
    - kaggle.com/competitions/titanic
    - Just the ID if it looks like a URL path segment won't match

    Returns competition ID (e.g., "titanic") or None.
    """
    m = _KAGGLE_URL_RE.search(text)
    return m.group(1) if m else None


def fetch_competition(competition_id: str, data_dir: str = "data") -> dict:
    """Fetch competition info and download dataset.

    Args:
        competition_id: Kaggle competition slug (e.g., "titanic").
        data_dir: Base directory for datasets. Data saved to {data_dir}/{competition_id}/.

    Returns:
        {
            "id": "titanic",
            "title": "Titanic - Machine Learning from Disaster",
            "description": "...",
            "metric": "Categorization Accuracy",
            "data_dir": "/abs/path/to/data/titanic",
            "files": ["train.csv", "test.csv", ...],
        }
    """
    from kaggle.api.kaggle_api_extended import KaggleApi

    api = KaggleApi()
    api.authenticate()

    # Get competition metadata
    result = api.competitions_list(search=competition_id)
    comp = None
    for c in result.competitions:
        # Match exact slug in the ref URL
        if c.ref and competition_id in c.ref:
            comp = c
            break

    if not comp:
        raise ValueError(f"Competition '{competition_id}' not found on Kaggle")

    # Get file list
    files_resp = api.competition_list_files(competition_id)
    file_names = [f.name for f in files_resp.files] if hasattr(files_resp, "files") else []

    # Download dataset
    dest = Path(data_dir) / competition_id
    dest.mkdir(parents=True, exist_ok=True)

    # Skip download if files already exist
    existing = {f.name for f in dest.iterdir() if f.is_file()} if dest.exists() else set()
    if not existing or not all(fn in existing for fn in file_names):
        api.competition_download_files(competition_id, path=str(dest))
        # Unzip if downloaded as zip
        for zf in dest.glob("*.zip"):
            with zipfile.ZipFile(zf, "r") as z:
                z.extractall(dest)
            zf.unlink()

    return {
        "id": competition_id,
        "title": comp.title or competition_id,
        "description": comp.description or "",
        "metric": comp.evaluation_metric or "",
        "data_dir": str(dest.resolve()),
        "files": file_names,
    }


def submit_and_score(competition_id: str, submission_path: str) -> float | None:
    """Submit predictions to Kaggle and return the public score.

    Polls until Kaggle finishes scoring (up to 60s).

    Args:
        competition_id: Kaggle competition slug.
        submission_path: Path to the submission CSV file.

    Returns:
        Public score as float, or None if scoring failed/timed out.
    """
    import time
    from kaggle.api.kaggle_api_extended import KaggleApi

    api = KaggleApi()
    api.authenticate()

    # Submit
    api.competition_submit(
        file_name=submission_path,
        competition=competition_id,
        message="MAARS auto-submission",
    )

    # Poll for score (Kaggle takes a few seconds to process)
    for _ in range(12):  # 12 * 5s = 60s max
        time.sleep(5)
        subs = api.competition_submissions(competition_id)
        if not hasattr(subs, 'submissions') and hasattr(subs, '__iter__'):
            latest = list(subs)[0] if subs else None
        elif hasattr(subs, 'submissions'):
            latest = subs.submissions[0] if subs.submissions else None
        else:
            latest = None

        if latest is None:
            continue

        # Check if scoring is complete
        status = getattr(latest, 'status', None)
        if status and 'COMPLETE' in str(status).upper():
            score_str = getattr(latest, 'publicScore', None) or getattr(latest, 'public_score', None)
            if score_str:
                try:
                    return float(score_str)
                except (ValueError, TypeError):
                    return None
            return None

    return None  # Timed out


def build_kaggle_idea(info: dict) -> str:
    """Build a structured research input from Kaggle competition info.

    The output serves as both the idea and the refined_idea (Refine is skipped).
    """
    files_str = ", ".join(info["files"]) if info["files"] else "see /workspace/data/"
    return (
        f"# Kaggle Competition: {info['title']}\n\n"
        f"**Description**: {info['description']}\n\n"
        f"**Evaluation Metric**: {info['metric']}\n\n"
        f"**Dataset Files** (located at /workspace/data/): {files_str}\n\n"
        f"## Task\n"
        f"Build a predictive model for this competition. Requirements:\n"
        f"1. Exploratory data analysis on the training data\n"
        f"2. Feature engineering (handle missing values, encode categoricals, create derived features)\n"
        f"3. Train and compare at least 3 different models\n"
        f"4. Generate predictions on the test set\n"
        f"5. Save submission file to /workspace/output/submission.csv\n"
        f"6. Optimize for the competition metric: {info['metric']}\n"
    )
