import sqlite3
import pandas as pd
import logging
from datetime import datetime, timezone


# Configure logging
logging.basicConfig(
    filename='../logs/ingestion_pipeline.log',  # path to log file
    filemode='a',                             # 'a' = append, 'w' = overwrite
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO                        # log INFO and above
)

def run_select(query, db_file="../db/flights.db", params=None):
    logging.info("Executing SQL query")
    logging.info(query)

    with sqlite3.connect(db_file) as conn:
        return pd.read_sql(query, conn, params=params)
    

def reset_tables(db_file):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Empty the main flights table
    cursor.execute("DELETE FROM flights;")
    
    # Empty the ingestion log
    cursor.execute("DELETE FROM ingested_files;")
    
    conn.commit()
    conn.close()

def run_execute(query, db_file="../db/flights.db", params=None):
    
    logging.info("Executing SQL query")
    logging.info(query)

    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params or ())
        conn.commit()


def make_airline_table(db_file="../db/flights.db"):

    query = """
            CREATE TABLE IF NOT EXISTS flights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER,
                month INTEGER,
                day INTEGER,
                flight_date TEXT,
                airline TEXT,
                flight_number INTEGER,
                origin TEXT,
                dest TEXT,
                distance REAL,
                dep_delay REAL,
                arr_delay REAL,
                arr_del15 INTEGER,
                cancelled INTEGER,
                diverted INTEGER
            );
            """

    run_execute(query, db_file, params=None)


def make_ingested_table(db_file):

    query = """
            CREATE TABLE IF NOT EXISTS ingested_files (
            file_name TEXT PRIMARY KEY,
            year INTEGER,
            month INTEGER,
            ingested_at TEXT,
            n_rows INTEGER,
            status TEXT   -- 'success' | 'failed'
            );
            """
    run_execute(query, db_file, params=None)

def file_already_ingested(file_name, db_file="../db/flights.db"):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT 1 FROM ingested_files WHERE file_name = ? AND status = 'success';",
        (file_name,)
    )

    exists = cursor.fetchone() is not None
    conn.close()
    return exists


def record_ingestion(
    file_name,
    year,
    month,
    n_rows,
    status,
    db_file="../db/flights.db"
):
    
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    timestamp = datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()

    cursor.execute("""
        INSERT OR REPLACE INTO ingested_files
        (file_name, year, month, ingested_at, n_rows, status)
        VALUES (?, ?, ?, ?, ?, ?);
    """, (
        file_name,
        year,
        month,
        timestamp,
        n_rows,
        status
    ))

    conn.commit()
    conn.close()


def mark_file_ingested(filename, db_file):
    query = """
        INSERT OR IGNORE INTO ingested_files (filename)
        VALUES (?);
    """
    run_execute(query, db_file=db_file, params=(filename,))

def add_to_sql(df, table = 'flights', db_file = "../db/flights.db"):

    conn = sqlite3.connect(db_file)
    df.to_sql(table, conn, if_exists="append", index=False)
    conn.close()

def create_feature_table():

    query = """
            CREATE TABLE IF NOT EXISTS airline_month_features(
                year INTEGER,
                month INTEGER,
                airline TEXT,
                n_flights INTEGER,
                avg_arr_delay REAL,
                std_arr_delay REAL,
                avg_dep_delay REAL,
                pct_arr_del15 REAL,
                rolling_3mo_avg_delay REAL
                )
            """
    
    run_execute(query)

def compute_features():

    select_query = """
                    SELECT airline, year, month, dep_delay, arr_delay, arr_del15
                    FROM flights
                    WHERE cancelled = 0;
                    """
    df = run_select(select_query)

    #compute monthly avg
    monthly = (
                    df
                    .groupby(["year", "month", "airline"])
                    .agg(
                        n_flights=("arr_delay", "count"),
                        avg_arr_delay=("arr_delay", "mean"),
                        std_arr_delay=("arr_delay", "std"),
                        avg_dep_delay=("dep_delay", "mean"),
                        n_arr_del15=("arr_del15", "sum"),
                    )
                    .reset_index()
                )

    monthly["pct_arr_del15"] = (
                                    monthly["n_arr_del15"] / monthly["n_flights"] * 100
                                )

    monthly = monthly.sort_values(["airline", "year", "month"])

    monthly["rolling_3mo_avg_delay"] = (
                                        monthly
                                        .groupby("airline")["avg_arr_delay"]
                                        .rolling(3)
                                        .mean()
                                        .reset_index(level=0, drop=True)
                                    )
    
    cols_to_keep = ['year', 'month', 'airline', 
                    'n_flights', 'avg_arr_delay', 
                    'std_arr_delay', 'avg_dep_delay', 
                    'pct_arr_del15', 'rolling_3mo_avg_delay']
    
    sql_df = monthly[cols_to_keep]

    return sql_df 


def make_feature_table(table = 'airline_month_features'):

    create_feature_table()
    sql_df = compute_features()
    add_to_sql(sql_df, table = table)
    
