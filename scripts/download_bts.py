"""
download_bts.py

Downloads monthly On-Time Performance data from the BTS PREZIP directory,
renames it to the expected YYYY_MM_Report.csv convention, runs the ingestion
pipeline, then cleans up all intermediate files.

Usage:
    python download_bts.py                          # defaults to prior month
    python download_bts.py --year 2025 --month 10
    python download_bts.py --year 2025 --month 10 --dry_run
"""

import argparse
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests
from tqdm import tqdm

from ingest_csv import ingestion
from sql_scripts import logging

BTS_URL_TEMPLATE = (
    "https://transtats.bts.gov/PREZIP/"
    "On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{year}_{month}.zip"
)

RAW_DATA_DIR = Path("../data/raw")
DB_FILE = "../db/flights.db"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Download a BTS monthly report, ingest it, and clean up."
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Year of the report to download (default: prior month's year)",
    )
    parser.add_argument(
        "--month",
        type=int,
        default=None,
        help="Month of the report to download (default: prior month)",
    )
    parser.add_argument(
        "--db_file",
        type=str,
        default=DB_FILE,
        help="Path to the SQLite database file",
    )
    parser.add_argument(
        "--rerun",
        action="store_true",
        help="Re-ingest even if already ingested",
    )
    parser.add_argument(
        "--dry_run",
        action="store_true",
        help="Download and extract but do not write to the database",
    )
    return parser.parse_args()


def default_year_month():
    """Return (year, month) for the most recently completed month (BTS lags ~1 month)."""
    now = datetime.now(tz=timezone.utc)
    month = now.month - 1 if now.month > 1 else 12
    year = now.year if now.month > 1 else now.year - 1
    return year, month


def download_zip(url: str, dest_path: Path) -> None:
    """Stream-download a file from url to dest_path with a progress bar."""
    logging.info(f"Downloading {url}")
    response = requests.get(url, stream=True, timeout=120)

    if response.status_code == 404:
        raise FileNotFoundError(
            f"BTS data not found at {url}. "
            "The data for this month may not be published yet."
        )
    response.raise_for_status()

    total = int(response.headers.get("content-length", 0))
    with open(dest_path, "wb") as f, tqdm(
        total=total,
        unit="B",
        unit_scale=True,
        desc=dest_path.name,
    ) as bar:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            bar.update(len(chunk))

    logging.info(f"Download complete: {dest_path}")


def extract_csv_from_zip(zip_path: Path, extract_dir: Path) -> Path:
    """Extract the ZIP and return the path of the first CSV found inside."""
    logging.info(f"Extracting {zip_path} to {extract_dir}")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)

    csvs = list(extract_dir.glob("*.csv"))
    if not csvs:
        raise FileNotFoundError(f"No CSV found inside {zip_path}")
    if len(csvs) > 1:
        logging.warning(f"Multiple CSVs found in ZIP; using first: {csvs[0].name}")

    logging.info(f"Extracted CSV: {csvs[0]}")
    return csvs[0]


def rename_to_standard(csv_path: Path, year: int, month: int) -> Path:
    """Copy the extracted CSV to data/raw/ with the YYYY_MM_Report.csv naming convention."""
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    dest = RAW_DATA_DIR / f"{year}_{month:02d}_Report.csv"
    shutil.copy2(csv_path, dest)
    logging.info(f"Copied to {dest}")
    return dest


def cleanup(paths: list) -> None:
    """Delete a list of files/directories, logging each removal."""
    for p in paths:
        p = Path(p)
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
            logging.info(f"Removed directory: {p}")
        elif p.exists():
            p.unlink()
            logging.info(f"Removed file: {p}")


def download_and_ingest(year: int, month: int, db_file: str, rerun: bool, dry_run: bool) -> None:
    url = BTS_URL_TEMPLATE.format(year=year, month=month)
    tmp_dir = Path(tempfile.mkdtemp(prefix="bts_download_"))
    zip_path = tmp_dir / f"bts_{year}_{month:02d}.zip"
    extract_dir = tmp_dir / "extracted"
    extract_dir.mkdir()

    to_cleanup = [tmp_dir]  # remove entire temp dir at the end

    try:
        download_zip(url, zip_path)
        extracted_csv = extract_csv_from_zip(zip_path, extract_dir)

        if not dry_run:
            rename_to_standard(extracted_csv, year, month)
        else:
            logging.info(f"Dry run: skipping rename and ingestion for {year}-{month:02d}")
            return

        logging.info(f"Starting ingestion for {year}-{month:02d}")
        ingestion(
            db_file=db_file,
            year_start=year,
            year_end=year,
            month_start=month,
            month_end=month,
            reset=rerun,
            dry_run=dry_run,
        )
        logging.info(f"Ingestion complete for {year}-{month:02d}")

    finally:
        cleanup(to_cleanup)
        logging.info("Cleanup complete")


if __name__ == "__main__":
    args = parse_args()

    year = args.year
    month = args.month

    if year is None or month is None:
        default_year, default_month = default_year_month()
        year = year or default_year
        month = month or default_month

    print(f"Targeting report: {year}-{month:02d}")
    download_and_ingest(
        year=year,
        month=month,
        db_file=args.db_file,
        rerun=args.rerun,
        dry_run=args.dry_run,
    )
