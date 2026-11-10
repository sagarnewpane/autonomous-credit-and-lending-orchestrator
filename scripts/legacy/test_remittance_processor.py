"""Test remittance_processor standalone — pick random applicant, show all validation."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import random
from app.db import supabase
from app.services.remittance_processor import process_remittances, REFERENCE_RATES, CURRENCY_MAP


def divider(char='═', width=70):
    print(char * width)


def default_serializer(obj):
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    return str(obj)


if __name__ == '__main__':
    # 1. Find applicants with remittance data
    all_rem = supabase.table('remittance_records').select('applicant_id').execute()
    if not all_rem.data:
        print("No remittance records found.")
        sys.exit(1)

    applicant_ids = list(set(r['applicant_id'] for r in all_rem.data))
    applicant_id = random.choice(applicant_ids)

    # 2. Fetch raw remittance records
    raw_records = supabase.table('remittance_records') \
        .select('*').eq('applicant_id', applicant_id).execute().data or []

    print()
    divider()
    print(f"  REMITTANCE PROCESSOR TEST")
    print(f"  Applicant: {applicant_id}")
    print(f"  Raw records: {len(raw_records)}")
    divider()
    print()

    # 3. Show reference rates
    divider('─')
    print("  REFERENCE RATES (min, max, default)")
    divider('─')
    for code, (min_r, max_r, default_r) in REFERENCE_RATES.items():
        print(f"    {code}: {min_r:.1f} – {max_r:.1f}  (default: {default_r:.1f})")
    print()

    # 4. Show expected currencies
    divider('─')
    print("  EXPECTED CURRENCIES")
    divider('─')
    for country, currency in CURRENCY_MAP.items():
        print(f"    {country} → {currency}")
    print()

    # 5. Run processor
    normalized, anomalies = process_remittances(raw_records)

    # 6. Show each record
    divider('─')
    print("  PROCESSED RECORDS")
    divider('─')
    for i, (raw, norm) in enumerate(zip(raw_records, normalized), 1):
        print(f"\n  Record {i}: {raw.get('remittance_id', 'unknown')}")
        print(f"    Country:          {raw.get('sender_country_code')} ({raw.get('sender_country_name')})")
        print(f"    Service:          {raw.get('transfer_service')}")
        print(f"    Disbursement:     {raw.get('disbursement_mode')}")
        print(f"    Name match score: {raw.get('name_match_score')}")
        print(f"    Foreign amount:   {raw.get('amount_foreign_currency')} {raw.get('foreign_currency_code')}")
        print(f"    Original rate:    {raw.get('exchange_rate')}")
        print(f"    Original amount:  Rs. {raw.get('amount_nrs')}")
        print(f"    ─────────────────────────────────────────")
        print(f"    Cleaned amount:   Rs. {norm['amount']:,.2f}")
        print(f"    Confidence:       {norm['confidence_weight']}")
        if norm.get('anomalies'):
            print(f"    Anomalies:        {norm['anomalies']}")
        print()

    # 7. Show anomalies summary
    divider('─')
    print("  ANOMALIES SUMMARY")
    divider('─')
    if anomalies:
        for a in anomalies:
            print(f"    {a['remittance_id']}: {a['flags']}")
            if a.get('amount_nrs_original') != a.get('amount_nrs_cleaned'):
                print(f"      Amount: Rs. {a['amount_nrs_original']} → Rs. {a['amount_nrs_cleaned']}")
    else:
        print("    No anomalies detected")
    print()

    # 8. Summary stats
    divider('─')
    print("  SUMMARY")
    divider('─')
    total = len(normalized)
    flagged = len(anomalies)
    avg_confidence = sum(n['confidence_weight'] for n in normalized) / total if total else 0
    total_amount = sum(n['amount'] for n in normalized)
    print(f"    Total records:     {total}")
    print(f"    Flagged records:   {flagged}")
    print(f"    Clean records:     {total - flagged}")
    print(f"    Total amount:      Rs. {total_amount:,.2f}")
    print(f"    Monthly avg (6m):  Rs. {total_amount / 6:,.2f}")
    print(f"    Avg confidence:    {avg_confidence:.3f}")
    print()

    # 9. Raw JSON output
    divider('─')
    print("  RAW JSON OUTPUT")
    divider('─')
    output = {
        "applicant_id": applicant_id,
        "normalized": normalized,
        "anomalies": anomalies,
    }
    print(json.dumps(output, indent=2, default=default_serializer))
    print()
