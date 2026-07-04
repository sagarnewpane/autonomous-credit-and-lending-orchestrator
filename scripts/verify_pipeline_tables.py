"""Verify existence of ALL tables the pipeline needs (read & write)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv()
from app.db import supabase

# Every table referenced by the pipeline code
pipeline_tables = {
    # Income Agent reads
    "mobile_money_transactions": "income_agent._fetch_applicant_data (READ)",
    "remittance_records": "income_agent._fetch_applicant_data (READ)",
    "cooperative_sales": "income_agent._fetch_applicant_data (READ)",
    "utility_payments": "income_agent._fetch_applicant_data (READ)",
    "cooperative_members": "income_agent._fetch_applicant_data (READ)",
    "applicant_profiles": "income_agent._fetch_applicant_data (READ)",
    
    # Income Agent writes
    "derived_utility_signals": "income_agent.analyze (WRITE)",
    "derived_mobile_payment_signals": "income_agent.analyze (WRITE)",
    "derived_remittance_signals": "income_agent.analyze (WRITE)",
    "income_signal_features": "income_agent.analyze (WRITE)",
    
    # Compliance Agent / ETL Master Builder reads+writes
    "master_dataset_clean": "etl_master_builder (WRITE) + score_agent (READ)",
    
    # Loan applications (read/write by all)
    "loan_applications": "all agents (READ/WRITE)",
    
    # Users
    "users": "auth (READ/WRITE)",
}

print("=" * 70)
print("PIPELINE TABLE DEPENDENCY CHECK")
print("=" * 70)

results = {}
for table, usage in pipeline_tables.items():
    try:
        res = supabase.table(table).select("*").limit(1).execute()
        count_res = supabase.table(table).select("count(*)").execute()
        count = count_res.data[0].get("count", "?") if count_res.data else "?"
        status = "✅ EXISTS"
        results[table] = {"status": "exists", "count": count}
        print(f"  {status}  {table:40s}  {count:>8} rows  ← {usage}")
    except Exception as e:
        err = str(e)
        if "does not exist" in err.lower() or "relation" in err.lower():
            status = "❌ MISSING"
            results[table] = {"status": "missing"}
        elif "permission" in err.lower():
            status = "🔒 NO ACCESS"
            results[table] = {"status": "no_access"}
        else:
            status = f"❓ ERROR"
            results[table] = {"status": "error", "error": err[:100]}
        print(f"  {status}  {table:40s}             ← {usage}")

# Summary
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
missing = [t for t, r in results.items() if r["status"] != "exists"]
if missing:
    print(f"\n  🚨 {len(missing)} MISSING TABLE(S) — pipeline WILL FAIL:")
    for t in missing:
        print(f"    ❌ {t} — used by {pipeline_tables[t]}")
else:
    print("  ✅ All pipeline tables exist.")

print("\n" + "=" * 70)
print("DONE")
print("=" * 70)
