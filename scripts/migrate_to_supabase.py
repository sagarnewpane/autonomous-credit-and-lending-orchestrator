import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
import re
from app.db.supabase import supabase


def clean_numeric(val):
    """Clean numeric values - remove 'Rs.', commas, and handle NaN/inf."""
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
        # Remove "Rs." prefix and commas
        cleaned = val.replace('Rs.', '').replace(',', '').strip()
        if cleaned == '' or cleaned.lower() == 'nan':
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return val


def clean_record(record):
    """Clean a record for JSON serialization."""
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
        elif isinstance(value, str) and key.endswith('_date') or key.endswith('_ad'):
            # Validate date format
            import re
            if re.match(r'^\d{4}-\d{2}-\d{2}$', value):
                # Check for invalid dates like 2024-02-30
                try:
                    from datetime import datetime
                    datetime.strptime(value, '%Y-%m-%d')
                    cleaned[key] = value
                except ValueError:
                    cleaned[key] = None
            else:
                cleaned[key] = value
        else:
            cleaned[key] = value
    return cleaned


def load_csv_table(table_name, file_path):
    """Load a CSV file into a Supabase table."""
    try:
        df = pd.read_csv(file_path)

        # Drop noise columns
        df = df[[col for col in df.columns if not col.startswith('_noise')]]

        # Clean numeric columns that might have formatting
        numeric_cols = [col for col in df.columns if 'amount' in col or 'value' in col or 'nrs' in col]
        for col in numeric_cols:
            df[col] = df[col].apply(clean_numeric)

        records = [clean_record(row) for row in df.to_dict('records')]

        batch_size = 100
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            supabase.table(table_name).upsert(batch).execute()

        print(f"  Loaded {len(records)} records into {table_name}")
    except Exception as e:
        print(f"  Error loading {table_name}: {e}")


def load_parquet_table(table_name, file_path, use_upsert=False):
    """Load a parquet file into a Supabase table."""
    try:
        df = pd.read_parquet(file_path)

        # Drop noise columns
        df = df[[col for col in df.columns if not col.startswith('_noise')]]

        # Clean numeric columns that might be strings with commas
        for col in df.columns:
            if 'amount' in col or 'value' in col or 'nrs' in col or 'fee' in col or 'rate' in col:
                df[col] = df[col].apply(clean_numeric)

        records = [clean_record(row) for row in df.to_dict('records')]

        # Deduplicate by primary key
        if records:
            pk = list(records[0].keys())[0]
            seen = set()
            deduped = []
            for r in records:
                if r[pk] not in seen:
                    seen.add(r[pk])
                    deduped.append(r)
            records = deduped

        batch_size = 100
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            if use_upsert:
                supabase.table(table_name).upsert(batch).execute()
            else:
                supabase.table(table_name).insert(batch).execute()

        print(f"  Loaded {len(records)} records into {table_name}")
    except Exception as e:
        print(f"  Error loading {table_name}: {e}")


print("Loading CSV files...")
csv_files = {
    'applicant_profiles': 'data/dataset/structured/applicant_profiles.csv',
    'cooperative_members': 'data/dataset/structured/cooperative_members.csv',
    'cooperative_sales': 'data/dataset/structured/cooperative_sales.csv',
    'document_registry': 'data/dataset/structured/document_registry.csv',
    'loan_applications': 'data/dataset/structured/loan_applications.csv',
}

for table_name, file_path in csv_files.items():
    print(f"  Loading {table_name}...")
    load_csv_table(table_name, file_path)

print()
print("Loading Parquet files...")
parquet_files = {
    'mobile_money_transactions': ('data/dataset/structured/mobile_money_transactions.parquet', True),
    'parsed_mobile_wallet_transactions': ('data/dataset/structured/parsed_mobile_wallet_transactions.parquet', True),
    'remittance_records': ('data/dataset/structured/remittance_records.parquet', True),
    'utility_payments': ('data/dataset/structured/utility_payments.parquet', True),
}

for table_name, (file_path, use_upsert) in parquet_files.items():
    print(f"  Loading {table_name}...")
    load_parquet_table(table_name, file_path, use_upsert)

print()
print("Done!")
