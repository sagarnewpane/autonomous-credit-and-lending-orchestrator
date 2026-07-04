import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from app.db import supabase

CLEANED_DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cleaned_db')

TABLE_CSV_MAP = {
    'applicant_profiles': ('applicant_profiles_clean.csv', 'applicant_id'),
    'cooperative_members': ('cooperative_members_clean.csv', 'member_id'),
    'income_signal_features': ('income_signal_features_clean.csv', 'applicant_id'),
    'loan_applications': ('loan_applications_clean.csv', 'application_id'),
    'mobile_money_transactions': ('mobile_money_transactions_clean.csv', 'transaction_id'),
    'remittance_records': ('remittance_records_clean.csv', 'remittance_id'),
    'utility_payments': ('utility_payments_clean.csv', 'payment_id'),
}


def clean_numeric(val):
    if pd.isna(val):
        return None
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        if np.isinf(val) or np.isnan(val):
            return None
        return float(val)
    if isinstance(val, (np.bool_,)):
        return bool(val)
    if isinstance(val, str):
        cleaned = val.replace('Rs.', '').replace(',', '').strip()
        if cleaned == '' or cleaned.lower() in ('nan', 'none'):
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return val


def clean_record(record):
    cleaned = {}
    for key, value in record.items():
        if key.startswith('_noise'):
            continue
        if isinstance(value, (np.integer,)):
            cleaned[key] = int(value)
        elif isinstance(value, (np.floating,)):
            cleaned[key] = None if (np.isinf(value) or np.isnan(value)) else float(value)
        elif isinstance(value, (np.bool_,)):
            cleaned[key] = bool(value)
        elif pd.isna(value):
            cleaned[key] = None
        elif isinstance(value, str) and value.lower() in ('nan', 'none', ''):
            cleaned[key] = None
        else:
            cleaned[key] = value
    return cleaned


def clear_table(table_name):
    try:
        supabase.table(table_name).delete().neq('applicant_id', '__nonexistent_pk__').execute()
        print(f"  Cleared {table_name}")
    except Exception as e:
        print(f"  Error clearing {table_name}: {e}")


def clear_table_by_pk(table_name, pk_column):
    try:
        supabase.table(table_name).delete().neq(pk_column, '__nonexistent__').execute()
        print(f"  Cleared {table_name}")
    except Exception as e:
        print(f"  Error clearing {table_name}: {e}")


def load_csv(table_name, file_path):
    try:
        df = pd.read_csv(file_path)
        df = df[[col for col in df.columns if not col.startswith('_noise')]]

        numeric_cols = [col for col in df.columns if 'amount' in col or 'value' in col or 'nrs' in col or 'score' in col or 'rate' in col]
        for col in numeric_cols:
            df[col] = df[col].apply(clean_numeric)

        records = [clean_record(row) for row in df.to_dict('records')]

        batch_size = 100
        total = 0
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            supabase.table(table_name).upsert(batch).execute()
            total += len(batch)

        print(f"  Loaded {total} records into {table_name}")
    except Exception as e:
        print(f"  Error loading {table_name}: {e}")


def main():
    print("=" * 60)
    print("CLEARING AND RELOADING DATABASE TABLES")
    print("=" * 60)

    print("\nStep 1: Clearing all tables...")
    for table_name, (_, pk_column) in TABLE_CSV_MAP.items():
        clear_table_by_pk(table_name, pk_column)

    print("\nStep 2: Loading data from cleaned CSV files...")
    for table_name, (csv_file, _) in TABLE_CSV_MAP.items():
        file_path = os.path.join(CLEANED_DB_DIR, csv_file)
        if os.path.exists(file_path):
            print(f"  Loading {table_name} from {csv_file}...")
            load_csv(table_name, file_path)
        else:
            print(f"  File not found: {file_path}")

    print("\n" + "=" * 60)
    print("DONE!")
    print("=" * 60)


if __name__ == '__main__':
    main()
