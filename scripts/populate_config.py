"""Populate config tables from actual data in Supabase."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.supabase import supabase
from collections import defaultdict
import statistics

# 1. Get occupation income baselines from loan_applications
print("Building occupation income baselines from loan_applications...")
profiles = supabase.table('applicant_profiles').select('applicant_id, occupation_en').execute()
occ_map = {p['applicant_id']: p['occupation_en'] for p in profiles.data}

loans = supabase.table('loan_applications').select('applicant_id, income_agent_monthly_est, income_confidence').execute()

occ_income = defaultdict(list)
occ_conf = defaultdict(list)
for l in loans.data:
    occ = occ_map.get(l['applicant_id'], 'Unknown')
    if l['income_agent_monthly_est']:
        occ_income[occ].append(l['income_agent_monthly_est'])
        occ_conf[occ].append(l['income_confidence'])

baselines = []
for occ, incomes in sorted(occ_income.items()):
    confs = occ_conf[occ]
    baseline = {
        'occupation': occ,
        'sample_count': len(incomes),
        'avg_income_monthly': round(statistics.mean(incomes)),
        'avg_confidence': round(statistics.mean(confs), 2),
        'median_income_monthly': round(statistics.median(incomes)),
    }
    baselines.append(baseline)
    print(f"  {occ:<30} n={baseline['sample_count']:>2}  avg=Rs.{baseline['avg_income_monthly']:>8,}  median=Rs.{baseline['median_income_monthly']:>8,}  conf={baseline['avg_confidence']:.0%}")

# Upsert into occupation_income_baselines
supabase.table('occupation_income_baselines').upsert(baselines).execute()
print(f"\n  Upserted {len(baselines)} occupation baselines")

# 2. Fetch signal weights
print("\nFetching data signal weights...")
weights = supabase.table('data_signal_weights').select('*').execute()
for w in weights.data:
    print(f"  {w['signal_name']:<25} weight={w['weight']:>+5.2f}  {w['description']}")
