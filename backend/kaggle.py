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

    # Check if user can access the data
    can_access = getattr(comp, 'userHasEntered', None) or getattr(comp, 'hasAcceptedRules', None)
    if can_access is False:
        url = f"https://www.kaggle.com/competitions/{competition_id}/rules"
        raise RuntimeError(
            f"You haven't joined this competition. "
            f"Please accept the rules first: {url}"
        )

    # Get file list
    files_resp = api.competition_list_files(competition_id)
    file_names = [f.name for f in files_resp.files] if hasattr(files_resp, "files") else []

    # Download dataset
    dest = Path(data_dir) / competition_id
    dest.mkdir(parents=True, exist_ok=True)

    # Skip download if files already exist
    existing = {f.name for f in dest.iterdir() if f.is_file()} if dest.exists() else set()
    if not existing or not all(fn in existing for fn in file_names):
        try:
            api.competition_download_files(competition_id, path=str(dest))
        except Exception as e:
            msg = str(e)
            if "403" in msg or "must accept" in msg.lower() or "rules" in msg.lower():
                raise RuntimeError(
                    f"Please join the competition first: "
                    f"https://www.kaggle.com/competitions/{competition_id}/rules"
                ) from e
            raise
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




def build_kaggle_idea(info: dict) -> str:
    """Build a rich refined idea from competition metadata + downloaded files.

    Reads data_description.txt (if present) and infers submission format
    from sample_submission.csv, so downstream agents have full context.
    """
    import csv

    data_dir = Path(info["data_dir"])
    files_str = ", ".join(info["files"]) if info["files"] else "see /workspace/data/"

    parts = [
        f"# Kaggle Competition: {info['title']}\n",
        f"{info['description']}\n",
        f"- **Evaluation Metric**: {info['metric']}",
        f"- **Dataset Files** (at /workspace/data/): {files_str}",
        f"- **Submission**: save to /workspace/output/submission.csv\n",
    ]

    # Data description (field definitions, often 100-500 lines)
    desc_path = data_dir / "data_description.txt"
    if desc_path.exists():
        desc_text = desc_path.read_text(encoding="utf-8", errors="replace")
        parts.append(f"## Data Description\n\n{desc_text}\n")

    # Submission format from sample_submission.csv
    sample_path = data_dir / "sample_submission.csv"
    if sample_path.exists():
        try:
            with open(sample_path, encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                first_row = next(reader, None)
            if header:
                parts.append(f"## Submission Format\n")
                parts.append(f"- **Columns**: {', '.join(header)}")
                if first_row:
                    parts.append(f"- **Example row**: {', '.join(first_row)}")
                parts.append("")
        except Exception:
            pass

    # Train data shape (row/column counts for planning)
    train_path = data_dir / "train.csv"
    if train_path.exists():
        try:
            with open(train_path, encoding="utf-8", errors="replace") as f:
                header = f.readline().strip().split(",")
                n_rows = sum(1 for _ in f)
            parts.append(f"## Train Data Overview\n")
            parts.append(f"- **Rows**: {n_rows}, **Columns**: {len(header)}")
            parts.append(f"- **Columns**: {', '.join(header)}\n")
        except Exception:
            pass

    return "\n".join(parts)
