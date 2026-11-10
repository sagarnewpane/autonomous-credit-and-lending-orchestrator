"""Deep analysis of PostgreSQL DB: discover tables + data quality checks."""
import os, json, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv()
from app.db import supabase

# --- Phase 1: Discover tables ---
tables_to_check = [
    "users", "loan_applications", "applicant_profiles",
    "cooperative_sales", "cooperative_members",
    "mobile_money_transactions", "remittance_records",
    "utility_payments", "income_signal_features",
    "master_dataset_clean", "derived_utility_signals",
    "derived_mobile_payment_signals", "derived_remittance_signals",
    "document_registry",
]

print("=" * 60)
print("PHASE 1: DISCOVERING TABLES")
print("=" * 60)

all_found = []
for table in tables_to_check:
    try:
        res = supabase.table(table).select("*").limit(1).execute()
        all_found.append(table)
        print(f"  ✅ '{table}'")
    except Exception as e:
        err = str(e)
        if "does not exist" in err.lower() or "relation" in err.lower():
            pass  # doesn't exist
        else:
            all_found.append(table)
            print(f"  ⚠️  '{table}' — exists but error: {err[:100]}")

print(f"\n  All found tables: {all_found}")

# --- Phase 2: Inspect tables ---
print("\n" + "=" * 60)
print("PHASE 2: INSPECTING TABLES")
print("=" * 60)

for table in all_found:
    print(f"\n{'─' * 60}")
    print(f"TABLE: {table}")
    print(f"{'─' * 60}")
    try:
        res = supabase.table(table).select("*").limit(3).execute()
        if res.data:
            cols = list(res.data[0].keys())
            print(f"  Columns ({len(cols)}): {cols}")
            print(f"\n  Sample (row 1):")
            for k, v in res.data[0].items():
                val_str = json.dumps(v, default=str) if isinstance(v, (dict, list)) else str(v)
                if len(val_str) > 100:
                    val_str = val_str[:100] + "..."
                print(f"    {k}: {val_str}")
        else:
            print("  (empty)")
    except Exception as e:
        print(f"  Error: {str(e)[:200]}")

# --- Phase 3: Data quality checks on loan_applications ---
print("\n" + "=" * 60)
print("PHASE 3: DATA QUALITY CHECKS ON loan_applications")
print("=" * 60)

null_checks = [
    "approved_amount_nrs", "credit_bureau_score", "doc_completeness_score",
    "cooperative_id", "income_confidence", "credit_score",
]

from app.db.postgres import get_cursor

for field in null_checks:
    try:
        with get_cursor() as cur:
            cur.execute(f"SELECT COUNT(*) as total FROM loan_applications")
            total = cur.fetchone()["total"]
            cur.execute(f"SELECT COUNT(*) as null_count FROM loan_applications WHERE {field} IS NULL")
            null_count = cur.fetchone()["null_count"]
        pct = (null_count / total * 100) if total else 0
        print(f"  {field}: {null_count}/{total} nulls ({pct:.1f}%)")
    except Exception as e:
        print(f"  {field}: error — {str(e)[:100]}")

print("\n" + "=" * 60)
print("DONE")
print("=" * 60)
