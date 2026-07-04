import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from app.db import supabase
import time

def clean_val(val):
    if pd.isna(val):
        return None
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return None if (np.isinf(val) or np.isnan(val)) else float(val)
    if isinstance(val, (np.bool_,)):
        return bool(val)
    if isinstance(val, str) and val.strip() in ('', 'nan', 'None'):
        return None
    return val

def load_csv_offset(table_name, file_path, db_columns, offset=0, limit=None):
    df = pd.read_csv(file_path)
    df = df[[c for c in df.columns if c in db_columns]]
    if offset > 0:
        df = df.iloc[offset:]
    if limit:
        df = df.head(limit)
    records = [{k: clean_val(v) for k, v in row.items()} for _, row in df.iterrows()]
    batch_size = 500
    total = 0
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        try:
            supabase.table(table_name).upsert(batch).execute()
            total += len(batch)
            if total % 10000 == 0:
                print(f'  [{table_name}] {total} rows loaded (offset={offset})')
                sys.stdout.flush()
        except Exception as e:
            print(f'  Error at batch {i}: {e}')
            sys.stdout.flush()
    print(f'  [{table_name}] Done: {total} rows loaded')
    return total

# Load remaining utility_payments (rows from 557500 onward)
print('=== Loading remaining utility_payments ===')
sys.stdout.flush()
utility_cols = ['payment_id','applicant_id','province_en','district_en','municipality_en','ward_no','utility_type','provider','service_number','billing_period_bs','billing_period_ad','bill_amount_nrs','units_consumed','due_date_ad','payment_date_ad','payment_method','days_late','cumulative_on_time_rate','outstanding_arrears_nrs']
load_csv_offset('utility_payments', 'cleaned_db/utility_payments_clean.csv', utility_cols, offset=557500)

# Load mobile_money_transactions
print('\n=== Loading mobile_money_transactions (2.2M rows) ===')
sys.stdout.flush()
mm_cols = ['transaction_id','applicant_id','platform','transaction_date','transaction_type','amount_nrs','direction','counterparty_category','geolocation_district','is_festival_period']
load_csv_offset('mobile_money_transactions', 'cleaned_db/mobile_money_transactions_clean.csv', mm_cols)

print('\n=== ALL DONE ===')
