"""Test income_agent via the LangGraph orchestrator with a random applicant from Supabase."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import random
from app.db.supabase import supabase
from app.services.orchestrator import app as workflow


def divider(char='═', width=70):
    print(char * width)


def default_serializer(obj):
    """Handle non-serializable types for json.dumps."""
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    if hasattr(obj, '__dict__'):
        return str(obj)
    return str(obj)


if __name__ == '__main__':
    # 1. Pick a random applicant_id from the DB
    all_ids = supabase.table('applicant_profiles').select('applicant_id').execute()
    if not all_ids.data:
        print("No applicants found in the database.")
        sys.exit(1)

    applicant_id = random.choice(all_ids.data)['applicant_id']

    print()
    divider()
    print(f"  ORCHESTRATOR INCOME AGENT TEST")
    print(f"  Random applicant_id: {applicant_id}")
    divider()
    print()

    # 2. Build initial state
    initial_state = {
        "applicant_id": applicant_id,
        "file_paths": {},
        "raw_transactions": [],
        "loan_request": {
            "amount": 200000,
            "tenure_months": 18,
            "existing_liabilities_monthly": 0,
            "collateral_value_nrs": 800000,
        },
        "errors": [],
    }

    # 3. Invoke the orchestrator
    print("  Invoking orchestrator: parser -> income_analyzer -> END")
    print()
    result = workflow.invoke(initial_state)

    # 4. Print raw output
    print(json.dumps(result, indent=2, default=default_serializer))
    print()
