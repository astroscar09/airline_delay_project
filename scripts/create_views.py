from tqdm import tqdm
from sql_scripts import run_execute, logging

def create_table_views(DB_FILE = "../db/flights.db"):

    views = {

        "v_flights_base": """
        CREATE VIEW IF NOT EXISTS v_flights_base AS
        SELECT
            flight_date,
            airline,
            flight_number,
            origin,
            dest,
            distance,
            dep_delay,
            arr_delay,
            arr_del15,
            cancelled,
            diverted,
            route
        FROM flights
        WHERE cancelled = 0;
        """,

        "v_airline_delay_stats": """
        CREATE VIEW IF NOT EXISTS v_airline_delay_stats AS
        SELECT
            airline,
            COUNT(*) AS n_flights,
            AVG(arr_delay) AS avg_arr_delay,
            AVG(dep_delay) AS avg_dep_delay,
            SUM(arr_del15) * 1.0 / COUNT(*) AS pct_arr_del15
        FROM flights
        WHERE cancelled = 0
        GROUP BY airline;
        """,

        "v_monthly_delays": """
        CREATE VIEW IF NOT EXISTS v_monthly_delays AS
        SELECT
            year,
            month,
            AVG(arr_delay) AS avg_arr_delay,
            COUNT(*) AS n_flights
        FROM flights
        WHERE cancelled = 0
        GROUP BY year, month;
        """,
    
        'v_airline_rolling_metrics': """CREATE VIEW IF NOT EXISTS v_airline_rolling_metrics AS
                SELECT
                    year,
                    month,
                    airline,
                    AVG(arr_delay) AS avg_arr_delay,

                    -- rolling 3-month average delay
                    AVG(AVG(arr_delay)) OVER (
                        PARTITION BY airline
                        ORDER BY year, month
                        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
                    ) AS rolling_3mo_avg_delay,

                    -- rolling flight count
                    SUM(COUNT(*)) OVER (
                        PARTITION BY airline
                        ORDER BY year, month
                        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
                    ) AS rolling_3mo_flights

                FROM flights
                WHERE cancelled = 0
                GROUP BY year, month, airline;
                """,

                'v_airline_vs_month_avg':   """
                CREATE VIEW IF NOT EXISTS v_airline_vs_month_avg AS
                SELECT
                    year,
                    month,
                    airline,
                    AVG(arr_delay) AS airline_avg_delay,
                    AVG(AVG(arr_delay)) OVER (
                        PARTITION BY year, month
                    ) AS month_avg_delay,
                    AVG(arr_delay)
                    - AVG(AVG(arr_delay)) OVER (PARTITION BY year, month)
                    AS delay_vs_month_avg
                FROM flights
                WHERE cancelled = 0
                GROUP BY year, month, airline;
                """,

        "v_delay_causes_by_airline": """
        CREATE VIEW IF NOT EXISTS v_delay_causes_by_airline AS
        SELECT
            airline,
            COUNT(*) AS n_delayed_flights,
            AVG(carrier_delay) AS avg_carrier_delay,
            AVG(weather_delay) AS avg_weather_delay,
            AVG(nas_delay) AS avg_nas_delay,
            AVG(security_delay) AS avg_security_delay,
            AVG(late_aircraft_delay) AS avg_late_aircraft_delay
        FROM flights
        WHERE cancelled = 0
          AND (carrier_delay > 0 OR weather_delay > 0 OR nas_delay > 0
               OR security_delay > 0 OR late_aircraft_delay > 0)
        GROUP BY airline;
        """,

        "v_route_delay_stats": """
        CREATE VIEW IF NOT EXISTS v_route_delay_stats AS
        SELECT
            route,
            origin,
            dest,
            COUNT(*) AS n_flights,
            AVG(arr_delay) AS avg_arr_delay,
            AVG(dep_delay) AS avg_dep_delay,
            SUM(arr_del15) * 1.0 / COUNT(*) AS pct_arr_del15
        FROM flights
        WHERE cancelled = 0
        GROUP BY route, origin, dest;
        """,

        "v_airport_delay_stats": """
        CREATE VIEW IF NOT EXISTS v_airport_delay_stats AS
        SELECT
            origin AS airport,
            COUNT(*) AS n_departures,
            AVG(dep_delay) AS avg_dep_delay,
            SUM(arr_del15) * 1.0 / COUNT(*) AS pct_arr_del15,
            SUM(cancelled) * 1.0 / (COUNT(*) + SUM(cancelled)) AS cancellation_rate
        FROM flights
        GROUP BY origin;
        """

    }

    for name, sql in tqdm(views.items(), desc="Creating views", unit="view"):
        run_execute(sql, db_file=DB_FILE)
        logging.info(f"Created view: {name}")


if __name__ == "__main__":
    create_table_views()