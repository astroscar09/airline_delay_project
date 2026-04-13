import pandas as pd
from sql_scripts import *
from tqdm import tqdm
from create_views import *
from pathlib import Path
import argparse

def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument("--db_file", type=str, default='../db/flights.db')
    parser.add_argument("--start_year", type=int, default=2025)
    parser.add_argument("--end_year", type=int, default=2025)
    parser.add_argument("--start_month", type=int, default=1)
    parser.add_argument("--end_month", type=int, default=12)

    parser.add_argument("--rerun", action="store_true",
                        help="Re-ingest files even if already ingested")

    parser.add_argument("--dry_run", action="store_true")

    return parser.parse_args()

def read_and_clean_single_file(csv_path):

    df = pd.read_csv(csv_path)

    cols_needed = [
        "YEAR",
        "MONTH",
        "DAY_OF_MONTH",
        "DAY_OF_WEEK",
        "FL_DATE",
        "OP_UNIQUE_CARRIER",
        "OP_CARRIER_FL_NUM",
        "ORIGIN",
        "DEST",
        "DISTANCE",
        "DEP_DELAY",
        "ARR_DELAY",
        "ARR_DEL15",
        "CANCELLED",
        "DIVERTED",
        "CARRIER_DELAY",
        "WEATHER_DELAY",
        "NAS_DELAY",
        "SECURITY_DELAY",
        "LATE_AIRCRAFT_DELAY"
    ]

    mapping_to_sql_tab = {
        "YEAR": 'year',
        "MONTH": 'month',
        "DAY_OF_MONTH": 'day',
        "DAY_OF_WEEK": 'day_of_week',
        "FL_DATE": 'flight_date',
        "OP_UNIQUE_CARRIER": 'airline',
        "OP_CARRIER_FL_NUM": 'flight_number',
        "ORIGIN": 'origin',
        "DEST": 'dest',
        "DISTANCE": 'distance',
        "DEP_DELAY": 'dep_delay',
        "ARR_DELAY": 'arr_delay',
        "ARR_DEL15": 'arr_del15',
        "CANCELLED": 'cancelled',
        "DIVERTED": 'diverted',
        "CARRIER_DELAY": 'carrier_delay',
        "WEATHER_DELAY": 'weather_delay',
        "NAS_DELAY": 'nas_delay',
        "SECURITY_DELAY": 'security_delay',
        "LATE_AIRCRAFT_DELAY": 'late_aircraft_delay',
    }

    # Keep only the columns we want
    df_sql = df.copy()[cols_needed]

    df_sql = df_sql.rename(columns=mapping_to_sql_tab)

    delay_cols = ["dep_delay", "arr_delay", "arr_del15",
                  "carrier_delay", "weather_delay", "nas_delay",
                  "security_delay", "late_aircraft_delay"]
    df_sql[delay_cols] = df_sql[delay_cols].fillna(0)

    df_sql["arr_del15"] = df_sql["arr_del15"].astype(int)
    df_sql["cancelled"] = df_sql["cancelled"].astype(int)
    df_sql["diverted"] = df_sql["diverted"].astype(int)

    df_sql["distance"] = df_sql["distance"].astype(float)

    df_sql["flight_number"] = df_sql["flight_number"].fillna(-99)
    df_sql["flight_number"] = df_sql["flight_number"].astype(int)

    return df_sql


def month_year_iter(start_year, start_month, end_year, end_month):
    year, month = start_year, start_month
    while (year < end_year) or (year == end_year and month <= end_month):
        yield year, month   # <-- pauses and sends (year, month)
        month += 1
        if month > 12:
            month = 1
            year += 1


def total_months(start_year, start_month, end_year, end_month):
    return (end_year - start_year) * 12 + (end_month - start_month + 1)


def add_single_file(csv_file, db_file, year, month, dry_run = False):

    logging.info(f'Processing csv file: {csv_file}')
    try:
        df_sql = read_and_clean_single_file(csv_file)

        if not dry_run:
            add_to_sql(df_sql)

            record_ingestion(
                file_name=csv_file,
                year=year,
                month=month,
                n_rows=len(df_sql),
                status="success",
                db_file=db_file
            )
        

    except FileNotFoundError:
        logging.warning(f"File not found: {csv_file}, skipping.")

    except Exception as e:
        logging.error(f"Failed processing {csv_file}: {e}")

        if not dry_run:
            record_ingestion(
                file_name=csv_file,
                year=year,
                month=month,
                n_rows=0,
                status="failed",
                db_file=db_file
            )


def read_multiple_files(year_start = 2025, 
                        year_end = 2025, 
                        month_start = 1, 
                        month_end = 12, 
                        db_file = '../db/flights.db', 
                        reset = False, 
                        dry_run = False):
    
    if reset:
        logging.info("Reset flag is True: clearing flights and ingestion log tables")
        reset_tables(db_file)
        
    
    all_months = total_months(year_start, month_start, year_end,  month_end)

    for year, month in tqdm(month_year_iter(year_start, month_start, year_end, month_end), 
                             total = all_months):
        
        
      
        csv_file = f'../data/raw/{year}_{month:02d}_Report.csv'
        if not reset and file_already_ingested(csv_file, db_file):
            logging.info(f"Skipping already ingested file: {csv_file}")
            continue

        add_single_file(csv_file, db_file, year, month, dry_run = dry_run)


        
def test_sql(db_file="../db/flights.db"):

    query1 = """
                SELECT * 
                FROM flights
                LIMIT 10;
            """


    check_results = run_select(query1, db_file)
    logging.info(f' ')
    logging.info(f'{check_results}')
    logging.info(f' ')

    query2 = """
                SELECT * 
                FROM ingested_files
                LIMIT 10;
            """

    check_results = run_select(query2, db_file)
    logging.info(f' ')
    logging.info(f'{check_results}')
    logging.info(f' ')

    #return check_results

def create_sql_indexes(db_file):

    queries = [
                "CREATE INDEX IF NOT EXISTS idx_flight_date ON flights(flight_date);",
                "CREATE INDEX IF NOT EXISTS idx_origin_dest ON flights(origin, dest);",
                "CREATE INDEX IF NOT EXISTS idx_airline ON flights(airline);"
                ]

    for query in queries:
        run_execute(query, db_file=db_file)


def add_route_column_if_not_exists(db_file):
    query = "PRAGMA table_info(flights);"
    columns = run_select(query, db_file)['name'].values
    if 'route' not in columns:
        run_execute("ALTER TABLE flights ADD COLUMN route TEXT;")

def check_files_exists(file):
    path = Path(file)
    return path.exists()


def ingestion(db_file, 
              year_start, year_end, month_start, month_end, 
              reset, 
              dry_run):

    #We create the table
    make_airline_table(db_file=db_file)

    #we also make the ingested table to keep track of already ingested files
    make_ingested_table(db_file=db_file)

    #migrate existing databases to include any new columns
    migrate_add_columns(db_file=db_file)

    #we read in the files they should be stored in the ../data/raw/ folder 
    #rn they have the filenames as YEAR_MM_Report.csv
    read_multiple_files(year_start = year_start, 
                        year_end = year_end, 
                        month_start = month_start, 
                        month_end = month_end, 
                        db_file = db_file, 
                        reset = reset, 
                        dry_run = dry_run)
    
    #adding in the routes column if it is not already there
    add_route_column_if_not_exists(db_file)

    #populating the routes to be origin-dest
    populate_routes = """
                      UPDATE flights
                      SET route = origin || '-' || dest
                      WHERE route IS NULL;
                      """
    run_execute(populate_routes)

    #making the indexes for quicker look up later
    create_sql_indexes(db_file)

    #creating views for easy downstream analysis
    create_table_views(db_file)

    #testing function to ensure the table looks correct
    test_sql(db_file)

    #saving the analysis files for visualization purposes
    OUTPUT_FOLDER = "../data/viz_data"

    rolling_metric_file = f"{OUTPUT_FOLDER}/airline_rolling_metrics.csv"
    delay_stats_file = f"{OUTPUT_FOLDER}/airline_delay_stats.csv"
    monthly_delays_file = f"{OUTPUT_FOLDER}/monthly_delays.csv"
    airline_vs_month_file = f"{OUTPUT_FOLDER}/airline_vs_month_avg.csv"

    if not check_files_exists(rolling_metric_file) or reset:
        df = run_select("SELECT * FROM v_airline_rolling_metrics;", db_file=db_file)
        df.to_csv(rolling_metric_file, index=False)

    if not check_files_exists(delay_stats_file) or reset:
        df = run_select("SELECT * FROM v_airline_delay_stats;", db_file=db_file)
        df.to_csv(delay_stats_file, index=False)

    if not check_files_exists(monthly_delays_file) or reset:
        df = run_select("SELECT * FROM v_monthly_delays;", db_file=db_file)
        df.to_csv(monthly_delays_file, index=False)

    if not check_files_exists(airline_vs_month_file) or reset:
        df = run_select("SELECT * FROM v_airline_vs_month_avg;", db_file=db_file)
        df.to_csv(f"{OUTPUT_FOLDER}/airline_vs_month_avg.csv", index=False)

    delay_causes_file = f"{OUTPUT_FOLDER}/delay_causes_by_airline.csv"
    route_stats_file = f"{OUTPUT_FOLDER}/route_delay_stats.csv"
    airport_stats_file = f"{OUTPUT_FOLDER}/airport_delay_stats.csv"

    if not check_files_exists(delay_causes_file) or reset:
        df = run_select("SELECT * FROM v_delay_causes_by_airline;", db_file=db_file)
        df.to_csv(delay_causes_file, index=False)

    if not check_files_exists(route_stats_file) or reset:
        df = run_select("SELECT * FROM v_route_delay_stats;", db_file=db_file)
        df.to_csv(route_stats_file, index=False)

    if not check_files_exists(airport_stats_file) or reset:
        df = run_select("SELECT * FROM v_airport_delay_stats;", db_file=db_file)
        df.to_csv(airport_stats_file, index=False)

if __name__ == '__main__':

    args = parse_args()

    db_file = args.db_file
    year_start = args.start_year
    year_end = args.end_year
    month_start = args.start_month
    month_end = args.end_month
    reset = args.rerun
    dry_run = args.dry_run

    ingestion(db_file, 
              year_start, year_end, month_start, month_end, 
              reset, 
              dry_run)