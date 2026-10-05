"""
Olist E-Commerce Data Loader
=============================
Loads CSV files from the Olist Brazilian E-Commerce dataset into MySQL.

Usage:
    python load_data.py

Prerequisites:
    1. MySQL server running with database created via sql/01_schema.sql
    2. CSV files placed in the data/ directory
    3. pip install mysql-connector-python pandas
"""

import os
import sys
import pandas as pd
import mysql.connector
from mysql.connector import Error
import warnings

warnings.filterwarnings('ignore')

# ─── Configuration ───────────────────────────────────────────────────────────
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Mehul@2807',
    'database': 'olist_ecommerce',
    'allow_local_infile': True,
    'charset': 'utf8mb4',
    'use_unicode': True,
}

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

# Mapping: CSV filename -> (table_name, column_order)
# Column order must match the CREATE TABLE column order exactly.
CSV_TABLE_MAP = {
    'olist_customers_dataset.csv': {
        'table': 'customers',
        'columns': ['customer_id', 'customer_unique_id', 'customer_zip_code_prefix',
                     'customer_city', 'customer_state'],
    },
    'olist_geolocation_dataset.csv': {
        'table': 'geolocation',
        'columns': ['geolocation_zip_code_prefix', 'geolocation_lat',
                     'geolocation_lng', 'geolocation_city', 'geolocation_state'],
        'extra_cols': {'geo_id': None},  # auto-increment, skip
    },
    'olist_sellers_dataset.csv': {
        'table': 'sellers',
        'columns': ['seller_id', 'seller_zip_code_prefix', 'seller_city', 'seller_state'],
    },
    'product_category_name_translation.csv': {
        'table': 'product_category_translation',
        'columns': ['product_category_name', 'product_category_name_english'],
    },
    'olist_products_dataset.csv': {
        'table': 'products',
        'columns': ['product_id', 'product_category_name', 'product_name_lenght',
                     'product_description_lenght', 'product_photos_qty',
                     'product_weight_g', 'product_length_cm', 'product_height_cm',
                     'product_width_cm'],
    },
    'olist_orders_dataset.csv': {
        'table': 'orders',
        'columns': ['order_id', 'customer_id', 'order_status',
                     'order_purchase_timestamp', 'order_approved_at',
                     'order_delivered_carrier_date', 'order_delivered_customer_date',
                     'order_estimated_delivery_date'],
        'datetime_cols': ['order_purchase_timestamp', 'order_approved_at',
                          'order_delivered_carrier_date', 'order_delivered_customer_date',
                          'order_estimated_delivery_date'],
    },
    'olist_order_items_dataset.csv': {
        'table': 'order_items',
        'columns': ['order_id', 'order_item_id', 'product_id', 'seller_id',
                     'shipping_limit_date', 'price', 'freight_value'],
        'datetime_cols': ['shipping_limit_date'],
    },
    'olist_order_payments_dataset.csv': {
        'table': 'order_payments',
        'columns': ['order_id', 'payment_sequential', 'payment_type',
                     'payment_installments', 'payment_value'],
    },
    'olist_order_reviews_dataset.csv': {
        'table': 'order_reviews',
        'columns': ['review_id', 'order_id', 'review_score',
                     'review_comment_title', 'review_comment_message',
                     'review_creation_date', 'review_answer_timestamp'],
        'datetime_cols': ['review_creation_date', 'review_answer_timestamp'],
    },
}

# Load order matters for foreign key constraints
LOAD_ORDER = [
    'olist_customers_dataset.csv',
    'olist_geolocation_dataset.csv',
    'olist_sellers_dataset.csv',
    'product_category_name_translation.csv',
    'olist_products_dataset.csv',
    'olist_orders_dataset.csv',
    'olist_order_items_dataset.csv',
    'olist_order_payments_dataset.csv',
    'olist_order_reviews_dataset.csv',
]


def get_connection():
    """Establish MySQL connection."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        if conn.is_connected():
            print(f"v Connected to MySQL server (version {conn.get_server_info()})")
            return conn
    except Error as e:
        print(f"x Error connecting to MySQL: {e}")
        sys.exit(1)


def clean_dataframe(df, config):
    """Clean a DataFrame before loading."""
    # Replace empty strings and whitespace-only strings with None (NULL)
    df = df.replace(r'^\s*$', None, regex=True)
    df = df.where(pd.notnull(df), None)

    # Parse datetime columns
    datetime_cols = config.get('datetime_cols', [])
    for col in datetime_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
            # Replace NaT with None for MySQL NULL
            df[col] = df[col].where(df[col].notna(), None)

    # Convert numeric columns that might have NaN
    for col in df.columns:
        if df[col].dtype in ['float64', 'int64']:
            df[col] = df[col].where(df[col].notna(), None)

    return df


def load_csv_to_table(conn, csv_file, config):
    """Load a single CSV file into its corresponding MySQL table."""
    filepath = os.path.join(DATA_DIR, csv_file)
    if not os.path.exists(filepath):
        print(f"   File not found: {filepath} — skipping")
        return False

    table = config['table']
    columns = config['columns']

    print(f"\n{'='*60}")
    print(f"Loading: {csv_file} → {table}")
    print(f"{'='*60}")

    # Read CSV
    try:
        df = pd.read_csv(filepath, encoding='utf-8', low_memory=False)
        print(f"  Rows in CSV: {len(df):,}")
    except Exception as e:
        print(f"  x Error reading CSV: {e}")
        return False

    # Keep only the columns we need (in case of extra columns)
    available_cols = [c for c in columns if c in df.columns]
    if len(available_cols) < len(columns):
        missing = set(columns) - set(available_cols)
        print(f"   Missing columns in CSV: {missing}")

    df = df[available_cols]

    # Clean data
    df = clean_dataframe(df, config)

    # Handle geolocation special case (skip geo_id auto-increment)
    insert_columns = available_cols

    # Build INSERT statement
    placeholders = ', '.join(['%s'] * len(insert_columns))
    col_names = ', '.join(insert_columns)
    insert_sql = f"INSERT IGNORE INTO {table} ({col_names}) VALUES ({placeholders})"

    # Convert DataFrame to list of tuples
    cursor = conn.cursor()

    # Disable FK checks for faster loading
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
    cursor.execute("SET UNIQUE_CHECKS = 0;")

    # Batch insert
    batch_size = 1000
    total_inserted = 0
    rows = df.values.tolist()

    # Convert numpy types to Python native types
    clean_rows = []
    for row in rows:
        clean_row = []
        for val in row:
            if pd.isna(val) if not isinstance(val, str) else False:
                clean_row.append(None)
            elif hasattr(val, 'item'):  # numpy scalar
                clean_row.append(val.item())
            elif isinstance(val, pd.Timestamp):
                clean_row.append(val.strftime('%Y-%m-%d %H:%M:%S'))
            else:
                clean_row.append(val)
        clean_rows.append(tuple(clean_row))

    for i in range(0, len(clean_rows), batch_size):
        batch = clean_rows[i:i + batch_size]
        try:
            conn.ping(reconnect=True, attempts=3, delay=1)
            cursor.executemany(insert_sql, batch)
            conn.commit()
            total_inserted += cursor.rowcount
            pct = min(100, int((i + batch_size) / len(clean_rows) * 100))
            print(f"  Progress: {pct:3d}% ({total_inserted:,} rows inserted)", end='\r')
        except Error as e:
            print(f"\n  X Error at batch {i//batch_size}: {e}")
            # Try inserting one by one to find the problematic row
            for j, row in enumerate(batch):
                try:
                    conn.ping(reconnect=True, attempts=3, delay=1)
                    cursor.execute(insert_sql, row)
                    conn.commit()
                    total_inserted += 1
                except Error as row_e:
                    print(f"    X Row {i+j}: {row_e}")

    # Re-enable checks
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
    cursor.execute("SET UNIQUE_CHECKS = 1;")
    cursor.close()

    print(f"\n  v Loaded {total_inserted:,} rows into `{table}`")
    return True


def verify_load(conn):
    """Print row counts for all tables to verify the load."""
    cursor = conn.cursor()
    tables = ['customers', 'geolocation', 'sellers', 'product_category_translation',
              'products', 'orders', 'order_items', 'order_payments', 'order_reviews']

    print(f"\n{'='*60}")
    print("VERIFICATION: Row counts per table")
    print(f"{'='*60}")

    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  {table:40s} {count:>10,} rows")
        except Error as e:
            print(f"  {table:40s} ERROR: {e}")

    cursor.close()


def run_schema(conn):
    """Execute the schema SQL file."""
    schema_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                'sql', '01_schema.sql')
    if not os.path.exists(schema_file):
        print(f" Schema file not found: {schema_file}")
        print("  Please run the schema SQL manually in MySQL Workbench first.")
        return False

    print(f"Running schema from: {schema_file}")
    cursor = conn.cursor()

    with open(schema_file, 'r', encoding='utf-8') as f:
        sql = f.read()

    # Split by semicolons but handle delimiter changes
    statements = [s.strip() for s in sql.split(';') if s.strip()]

    for stmt in statements:
        if stmt.upper().startswith('DELIMITER') or not stmt:
            continue
        try:
            cursor.execute(stmt + ';')
        except Error as e:
            # Skip non-critical errors like DROP IF NOT EXISTS
            if e.errno not in [1008, 1050, 1051, 1060, 1061, 1091]:
                print(f"   SQL Warning: {e}")

    conn.commit()
    cursor.close()
    print("v Schema created successfully")
    return True


def main():
    """Main entry point."""
    print("=" * 60)
    print("  OLIST E-COMMERCE DATA LOADER")
    print("=" * 60)

    # Check for CSV files
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)

    csv_files = [f for f in os.listdir(DATA_DIR) if f.endswith('.csv')]
    if not csv_files:
        print(f"\nx No CSV files found in: {DATA_DIR}")
        print("  Please download the Olist dataset from Kaggle and place")
        print("  the CSV files in the data/ directory.")
        print("  URL: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce")
        sys.exit(1)

    print(f"\nFound {len(csv_files)} CSV files in {DATA_DIR}")
    for f in sorted(csv_files):
        size_mb = os.path.getsize(os.path.join(DATA_DIR, f)) / (1024 * 1024)
        print(f"  • {f} ({size_mb:.1f} MB)")

    # Connect to MySQL (initially without database to create it)
    print("\n--- Step 1: Create Database Schema ---")
    try:
        conn_init = mysql.connector.connect(
            host='localhost', user='root', password='Mehul@2807',
            charset='utf8mb4', use_unicode=True
        )
        cursor = conn_init.cursor()

        # Read and execute schema
        schema_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    'sql', '01_schema.sql')
        if os.path.exists(schema_file):
            run_schema_from_file(cursor, conn_init, schema_file)
        else:
            # Create database if schema file not available
            cursor.execute("CREATE DATABASE IF NOT EXISTS olist_ecommerce "
                          "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            conn_init.commit()
            print("v Database created (schema file not found, run it separately)")

        cursor.close()
        conn_init.close()
    except Error as e:
        print(f"X Error during schema creation: {e}")

    # Connect to the database
    print("\n--- Step 2: Load CSV Data ---")
    conn = get_connection()

    success_count = 0
    for csv_file in LOAD_ORDER:
        if csv_file in CSV_TABLE_MAP:
            if load_csv_to_table(conn, csv_file, CSV_TABLE_MAP[csv_file]):
                success_count += 1

    # Verify
    print(f"\n--- Step 3: Verify Load ---")
    verify_load(conn)

    print(f"\n{'='*60}")
    print(f"  COMPLETE: {success_count}/{len(LOAD_ORDER)} tables loaded")
    print(f"{'='*60}")
    print("\nNext steps:")
    print("  1. Run sql/01_schema.sql in MySQL Workbench for views & cleanup")
    print("  2. Run analysis queries: sql/02-05_*.sql")
    print("  3. Launch dashboard: streamlit run dashboard/app.py")

    conn.close()


def run_schema_from_file(cursor, conn, schema_file):
    """Execute schema SQL from file, handling multi-statement scripts."""
    print(f"  Executing schema: {schema_file}")
    with open(schema_file, 'r', encoding='utf-8') as f:
        sql_content = f.read()

    # Simple statement splitter (handles most cases)
    statements = sql_content.split(';')
    executed = 0
    for stmt in statements:
        stmt = stmt.strip()
        if not stmt or stmt.upper().startswith('--') or stmt.upper().startswith('DELIMITER'):
            continue
        # Skip comment-only blocks
        lines = [l for l in stmt.split('\n') if not l.strip().startswith('--')]
        clean_stmt = '\n'.join(lines).strip()
        if not clean_stmt:
            continue
        try:
            cursor.execute(clean_stmt + ';')
            executed += 1
        except Error as e:
            # Ignore benign errors
            pass

    conn.commit()
    print(f"  v Executed {executed} SQL statements")


if __name__ == '__main__':
    main()
