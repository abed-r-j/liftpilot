"""X5 RetailHero uplift data: a real randomised campaign of a grocery chain.

The source describes the treatment only as "a communication" (the competition
page speaks of deciding whether to "send a text to the client"); the channel,
the content of the message, the length of the outcome window and the currency
(presumed Russian roubles) are not documented.

Three public files (X5 Retail Group, RetailHero 2019 uplift competition):

* ``uplift_train.csv.gz`` - 200,039 loyalty-card customers, a random
  ``treatment_flg`` (1 = received the communication) and ``target``
  (1 = purchased in the period after it);
* ``clients.csv.gz``      - card issue date, first redemption date, age, gender;
* ``purchases.csv.gz``    - 45.8 million purchase lines over about four months
  BEFORE the campaign (every line of every receipt).

This module turns the raw receipts into one row per customer with honest
Recency / Frequency / Monetary features, using DuckDB so that the 640 MB file
is streamed from disk instead of loaded into memory.

Leakage guard: ``first_redeem_date`` runs past the end of the purchase history
(into the outcome period), so only redemptions dated on or before the
reference date are allowed to become features.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

RAW_FILES = ("clients.csv.gz", "uplift_train.csv.gz", "purchases.csv.gz")
BASE_URL = "https://sklift.s3.eu-west-2.amazonaws.com"


def _sql_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace("'", "''")


def _connect(tmp_dir: Path, memory_limit: str) -> duckdb.DuckDBPyConnection:
    tmp_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"SET memory_limit='{memory_limit}'")
    con.execute(f"SET temp_directory='{_sql_path(tmp_dir)}'")
    con.execute("SET preserve_insertion_order=false")
    return con


def build_transactions(raw_dir: Path, out_path: Path, memory_limit: str = "3GB") -> Path:
    """Collapse purchase lines into one row per receipt and save as Parquet."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    con = _connect(out_path.parent / "_duckdb_tmp", memory_limit)
    src = _sql_path(raw_dir / "purchases.csv.gz")
    con.execute(
        f"""
        COPY (
            SELECT
                client_id,
                transaction_id,
                min(transaction_datetime)                    AS ts,
                any_value(purchase_sum)                      AS amount,
                any_value(store_id)                          AS store_id,
                count(*)                                     AS n_lines,
                count(DISTINCT product_id)                   AS n_products,
                sum(product_quantity)                        AS n_units,
                any_value(regular_points_received)           AS points_received,
                any_value(express_points_received)           AS express_received,
                any_value(regular_points_spent)              AS points_spent,
                any_value(express_points_spent)              AS express_spent
            FROM read_csv(
                '{src}',
                header = true,
                columns = {{
                    'client_id': 'VARCHAR', 'transaction_id': 'VARCHAR',
                    'transaction_datetime': 'TIMESTAMP',
                    'regular_points_received': 'DOUBLE', 'express_points_received': 'DOUBLE',
                    'regular_points_spent': 'DOUBLE', 'express_points_spent': 'DOUBLE',
                    'purchase_sum': 'DOUBLE', 'store_id': 'VARCHAR', 'product_id': 'VARCHAR',
                    'product_quantity': 'DOUBLE', 'trn_sum_from_iss': 'DOUBLE',
                    'trn_sum_from_red': 'DOUBLE'
                }}
            )
            GROUP BY client_id, transaction_id
        ) TO '{_sql_path(out_path)}' (FORMAT PARQUET, COMPRESSION ZSTD)
        """
    )
    con.close()
    return out_path


FEATURE_SQL = """
WITH ref AS (
    SELECT date_trunc('day', max(ts)) + INTERVAL 1 DAY AS t0, min(ts) AS t_start
    FROM tx
),
agg AS (
    SELECT
        client_id,
        date_diff('day', max(ts), (SELECT t0 FROM ref))               AS recency_days,
        count(*)                                                       AS frequency,
        sum(amount)                                                    AS monetary,
        avg(amount)                                                    AS avg_basket,
        coalesce(stddev_samp(amount), 0)                               AS std_basket,
        max(amount)                                                    AS max_basket,
        median(amount)                                                 AS median_basket,
        date_diff('day', min(ts), (SELECT t0 FROM ref))                AS tenure_days,
        count(DISTINCT date_trunc('day', ts))                          AS active_days,
        count(DISTINCT date_trunc('week', ts))                         AS active_weeks,
        count(DISTINCT store_id)                                       AS n_stores,
        avg(n_lines)                                                   AS avg_lines,
        avg(n_units)                                                   AS avg_units,
        sum(points_received)                                           AS points_received,
        sum(express_received)                                          AS express_received,
        -sum(points_spent)                                             AS points_spent,
        -sum(express_spent)                                            AS express_spent,
        avg(CASE WHEN points_spent < 0 OR express_spent < 0 THEN 1.0 ELSE 0.0 END)
                                                                       AS share_tx_redeeming,
        avg(CASE WHEN dayofweek(ts) IN (0, 6) THEN 1.0 ELSE 0.0 END)   AS share_weekend,
        avg(CASE WHEN hour(ts) >= 18 THEN 1.0 ELSE 0.0 END)            AS share_evening,
        sum(CASE WHEN ts >= (SELECT t0 FROM ref) - INTERVAL 30 DAY THEN 1 ELSE 0 END)
                                                                       AS frequency_30d,
        sum(CASE WHEN ts >= (SELECT t0 FROM ref) - INTERVAL 30 DAY THEN amount ELSE 0 END)
                                                                       AS monetary_30d,
        sum(CASE WHEN ts >= (SELECT t0 FROM ref) - INTERVAL 60 DAY
                  AND ts <  (SELECT t0 FROM ref) - INTERVAL 30 DAY THEN 1 ELSE 0 END)
                                                                       AS frequency_31_60d,
        sum(CASE WHEN ts >= (SELECT t0 FROM ref) - INTERVAL 60 DAY
                  AND ts <  (SELECT t0 FROM ref) - INTERVAL 30 DAY THEN amount ELSE 0 END)
                                                                       AS monetary_31_60d,
        sum(CASE WHEN ts >= (SELECT t0 FROM ref) - INTERVAL 7 DAY THEN 1 ELSE 0 END)
                                                                       AS frequency_7d
    FROM tx
    GROUP BY client_id
)
SELECT
    a.*,
    CASE WHEN a.frequency > 1
         THEN (a.tenure_days - a.recency_days) / (a.frequency - 1.0) END AS avg_gap_days,
    a.frequency_30d - a.frequency_31_60d                                 AS frequency_trend,
    date_diff('day', c.first_issue_date, (SELECT t0 FROM ref))           AS card_age_days,
    CASE WHEN c.first_redeem_date IS NOT NULL
              AND c.first_redeem_date < (SELECT t0 FROM ref) THEN 1 ELSE 0 END AS redeemed_before,
    CASE WHEN c.first_redeem_date IS NOT NULL
              AND c.first_redeem_date < (SELECT t0 FROM ref)
         THEN date_diff('day', c.first_redeem_date, (SELECT t0 FROM ref)) END AS days_since_first_redeem,
    c.age        AS age_raw,
    c.gender     AS gender,
    u.treatment_flg AS t,
    u.target        AS y,
    (SELECT t0 FROM ref)      AS reference_date,
    (SELECT t_start FROM ref) AS history_start
FROM agg a
JOIN clients c USING (client_id)
LEFT JOIN uplift u USING (client_id)
"""


def build_customer_table(
    raw_dir: Path, interim_dir: Path, memory_limit: str = "3GB", rebuild: bool = False
) -> pd.DataFrame:
    """One row per customer: RFM + behaviour features, audit columns, T and Y.

    Customers outside the experiment (no treatment flag) are kept with
    ``t``/``y`` missing: they are "new customers to score", not training data.
    """
    tx_path = interim_dir / "x5_transactions.parquet"
    if rebuild or not tx_path.exists():
        build_transactions(raw_dir, tx_path, memory_limit)
    con = _connect(interim_dir / "_duckdb_tmp", memory_limit)
    con.execute(f"CREATE VIEW tx AS SELECT * FROM read_parquet('{_sql_path(tx_path)}')")
    con.execute(
        f"CREATE VIEW clients AS SELECT * FROM read_csv_auto('{_sql_path(raw_dir / 'clients.csv.gz')}')"
    )
    con.execute(
        "CREATE VIEW uplift AS SELECT * FROM "
        f"read_csv_auto('{_sql_path(raw_dir / 'uplift_train.csv.gz')}')"
    )
    df = con.execute(FEATURE_SQL).df()
    con.close()
    return df.set_index("client_id").sort_index()


def monthly_activity(interim_dir: Path) -> pd.DataFrame:
    """Customer x calendar-month activity (orders, revenue) for retention maths."""
    tx_path = interim_dir / "x5_transactions.parquet"
    con = duckdb.connect()
    df = con.execute(
        f"""
        SELECT client_id,
               strftime(date_trunc('month', ts), '%Y-%m') AS month,
               count(*)    AS orders,
               sum(amount) AS revenue
        FROM read_parquet('{_sql_path(tx_path)}')
        GROUP BY 1, 2
        """
    ).df()
    con.close()
    return df


def history_summary(interim_dir: Path) -> dict[str, object]:
    tx_path = interim_dir / "x5_transactions.parquet"
    con = duckdb.connect()
    row = con.execute(
        f"""
        SELECT count(*), count(DISTINCT client_id), min(ts), max(ts), sum(amount), avg(amount),
               sum(n_lines)
        FROM read_parquet('{_sql_path(tx_path)}')
        """
    ).fetchone()
    con.close()
    assert row is not None
    return {
        "transactions": int(row[0]),
        "customers": int(row[1]),
        "first_purchase": str(row[2]),
        "last_purchase": str(row[3]),
        "revenue": float(row[4]),
        "average_basket": float(row[5]),
        "purchase_lines": int(row[6]),
    }
