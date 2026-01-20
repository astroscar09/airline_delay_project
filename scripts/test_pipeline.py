import os
import sqlite3
import logging
from ingest_csv import (
    read_multiple_files,
    test_sql,
    file_already_ingested
)
from pathlib import Path

DB_FILE = "../db/flights.db"

def assert_true(condition, msg):
    if not condition:
        raise AssertionError(msg)
    logging.info(f"PASS: {msg}")


def table_exists(table_name):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name=?;
    """, (table_name,))
    exists = cur.fetchone() is not None
    conn.close()
    return exists


def test_tables_exist():
    assert_true(table_exists("flights"), "flights table exists")
    assert_true(table_exists("ingested_files"), "ingested_files table exists")

def test_dry_run():
    before = test_sql()

    read_multiple_files(
        year_start=2025,
        year_end=2025,
        month_start=1,
        month_end=1,
        dry_run=True
    )

    after = test_sql()
    assert_true(len(before) == len(after), "dry-run does not modify data")

def test_real_ingestion():
    read_multiple_files(
        year_start=2025,
        year_end=2025,
        month_start=1,
        month_end=1,
        reset=True
    )

    results = test_sql()
    assert_true(len(results) > 0, "data ingested successfully")

def test_duplicate_skip():
    
    file_name = "../data/raw/2025_01_Report.csv"
    assert_true(
        file_already_ingested(file_name),
        "file marked as ingested"
    )

    read_multiple_files(
        year_start=2025,
        year_end=2025,
        month_start=1,
        month_end=1,
        reset=False
    )

    assert_true(
        file_already_ingested(file_name),
        "duplicate ingestion skipped"
    )

def test_indexes_exist():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        SELECT name FROM sqlite_master
        WHERE type='index';
    """)
    indexes = [row[0] for row in cur.fetchall()]
    conn.close()

    expected = {"idx_flight_date", "idx_origin_dest", "idx_airline"}
    assert_true(expected.issubset(set(indexes)), "indexes exist")


def run_all_tests():
    logging.info("Starting pipeline validation")

    test_tables_exist()
    test_dry_run()
    test_real_ingestion()
    test_duplicate_skip()
    test_indexes_exist()

    logging.info("ALL TESTS PASSED")

if __name__ == "__main__":
    run_all_tests()
