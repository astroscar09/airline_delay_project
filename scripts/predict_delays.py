"""
predict_delays.py

Binary classification: predict whether a flight will have an arrival delay
of 15+ minutes (ARR_DEL15 = 1).

Model: RandomForestClassifier
Features: airline, origin, dest, distance, month, day_of_week, dep_delay,
          carrier_delay, weather_delay, nas_delay, security_delay, late_aircraft_delay

Outputs (written to --output_dir):
  - delay_predictions.csv    test-set rows with actual label + predicted probability
  - feature_importance.csv   feature name + importance score

Usage:
    python predict_delays.py
    python predict_delays.py --db_file ../db/flights.db --year 2024 --output_dir ../data/viz_data
"""

import argparse
from pathlib import Path

import pandas as pd
from tqdm import tqdm
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, roc_auc_score, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from sql_scripts import run_select, logging


CATEGORICAL_FEATURES = ["airline", "origin", "dest"]
BASE_NUMERICAL_FEATURES = ["distance", "month", "dep_delay"]
OPTIONAL_NUMERICAL_FEATURES = ["day_of_week", "carrier_delay", "weather_delay",
                                "nas_delay", "security_delay", "late_aircraft_delay"]
TARGET = "arr_del15"


def parse_args():
    parser = argparse.ArgumentParser(description="Train a binary delay classifier.")
    parser.add_argument("--db_file", type=str, default="../db/flights.db")
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Filter training data to a specific year (default: all years)",
    )
    parser.add_argument("--output_dir", type=str, default="../data/viz_data")
    parser.add_argument(
        "--n_estimators",
        type=int,
        default=100,
        help="Number of trees in the random forest (default: 100)",
    )
    parser.add_argument(
        "--test_size",
        type=float,
        default=0.2,
        help="Fraction of data held out for testing (default: 0.2)",
    )
    parser.add_argument(
        "--random_state",
        type=int,
        default=42,
    )
    return parser.parse_args()


def load_data(db_file: str, year: int | None) -> pd.DataFrame:
    year_filter = f"AND year = {year}" if year is not None else ""
    query = f"""
        SELECT
            airline, origin, dest, distance, month, dep_delay, arr_del15,
            day_of_week, carrier_delay, weather_delay, nas_delay,
            security_delay, late_aircraft_delay
        FROM flights
        WHERE cancelled = 0
          {year_filter};
    """
    logging.info(f"Loading data from {db_file}" + (f" (year={year})" if year else ""))
    df = run_select(query, db_file=db_file)
    logging.info(f"Loaded {len(df):,} rows")
    return df


def get_available_features(df: pd.DataFrame) -> list:
    """Return the full feature list, dropping optional columns absent from the data."""
    optional_present = [c for c in OPTIONAL_NUMERICAL_FEATURES if c in df.columns]
    missing = [c for c in OPTIONAL_NUMERICAL_FEATURES if c not in df.columns]
    if missing:
        logging.warning(
            f"Optional feature columns not found in DB (re-ingest to add them): {missing}"
        )
    return CATEGORICAL_FEATURES + BASE_NUMERICAL_FEATURES + optional_present


def encode_categoricals(df: pd.DataFrame, encoders: dict | None = None):
    """Label-encode categorical columns. Returns (encoded_df, encoders_dict)."""
    encoders = encoders or {}
    for col in tqdm(CATEGORICAL_FEATURES, desc="Encoding categoricals", unit="col"):
        if col not in encoders:
            encoders[col] = LabelEncoder().fit(df[col].astype(str))
        df[col] = encoders[col].transform(df[col].astype(str))
    return df, encoders


def train_and_evaluate(args) -> None:
    df = load_data(args.db_file, args.year)

    features = get_available_features(df)
    df = df[features + [TARGET]].dropna()

    df, encoders = encode_categoricals(df)

    X = df[features]
    y = df[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=args.test_size,
        stratify=y,
        random_state=args.random_state,
    )

    logging.info(
        f"Train size: {len(X_train):,}  |  Test size: {len(X_test):,}  |  "
        f"Delay rate: {y.mean():.1%}"
    )
    print(f"\nTraining RandomForestClassifier ({args.n_estimators} trees) ...")

    model = RandomForestClassifier(
        n_estimators=args.n_estimators,
        n_jobs=-1,
        random_state=args.random_state,
        class_weight="balanced",
        verbose=1,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_prob)

    print("\n--- Classification Report ---")
    print(classification_report(y_test, y_pred, target_names=["On Time", "Delayed 15+"]))
    print(f"ROC-AUC: {auc:.4f}")
    print("\n--- Confusion Matrix ---")
    cm = confusion_matrix(y_test, y_pred)
    print(pd.DataFrame(cm,
                       index=["Actual On Time", "Actual Delayed"],
                       columns=["Predicted On Time", "Predicted Delayed"]))

    logging.info(f"ROC-AUC: {auc:.4f}")

    # Save outputs
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    predictions_df = X_test.copy()
    predictions_df["actual_arr_del15"] = y_test.values
    predictions_df["predicted_arr_del15"] = y_pred
    predictions_df["delay_probability"] = y_prob
    pred_path = output_dir / "delay_predictions.csv"
    predictions_df.to_csv(pred_path, index=False)
    print(f"\nPredictions saved to: {pred_path}")

    importance_df = pd.DataFrame({
        "feature": features,
        "importance": model.feature_importances_,
    }).sort_values("importance", ascending=False)
    imp_path = output_dir / "feature_importance.csv"
    importance_df.to_csv(imp_path, index=False)
    print(f"Feature importance saved to: {imp_path}")

    logging.info(f"Outputs written to {output_dir}")


if __name__ == "__main__":
    args = parse_args()
    train_and_evaluate(args)
