import sys
import os
import re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from app.db import db


def _clean_amount(val):
    """Clean and convert amount to float, returning 0.0 on failure."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    try:
        cleaned = re.sub(r'[^\d.-]', '', str(val))
        return float(cleaned) if cleaned else 0.0
    except (ValueError, TypeError):
        return 0.0


def _fix_name(name):
    """Clean and title-case a name string."""
    if not name:
        return None
    return str(name).strip().title()


def build_single_master_record(state: dict) -> dict:
    """
    Build and save a master record for a SINGLE application.
    Use this in real-time flows instead of build_master_dataset().
    
    Raises exceptions on failure instead of silently failing.
    """
    from datetime import datetime
    
    applicant_id = state.get("applicant_id")
    application_id = state.get("application_id")
    
    if not applicant_id:
        raise ValueError("build_single_master_record: applicant_id is required in state")
    if not application_id:
        raise ValueError("build_single_master_record: application_id is required in state")
    
    print(f"[Master Builder] Building record for application {application_id}...")
    
    # ==========================================
    # 1. FETCH PROFILE
    # ==========================================
    try:
        profile_response = db.table('applicant_profiles') \
            .select('*') \
            .eq('applicant_id', applicant_id) \
            .single() \
            .execute()
        profile = profile_response.data
    except Exception as e:
        raise RuntimeError(f"Failed to fetch profile for {applicant_id}: {e}")
    
    if not profile:
        raise ValueError(f"No profile found for applicant {applicant_id}")
    
    # Log noise flags but DON'T skip the record
    noise_flags = [k for k in ['_noise_duplicate', '_noise_dob_bad', '_noise_geo_wrong', 
                                '_noise_cit_bad', '_noise_ward_issue'] if profile.get(k)]
    if noise_flags:
        print(f"[Master Builder] ⚠️ Profile has noise flags: {noise_flags} (proceeding anyway)")
    
    # ==========================================
    # 2. FETCH LOAN APPLICATION
    # ==========================================
    try:
        loan_response = db.table('loan_applications') \
            .select('*') \
            .eq('application_id', application_id) \
            .single() \
            .execute()
        loan = loan_response.data
    except Exception as e:
        raise RuntimeError(f"Failed to fetch loan application {application_id}: {e}")
    
    if not loan:
        raise ValueError(f"No loan application found for {application_id}")
    
    # ==========================================
    # 3. FETCH COOPERATIVE DATA
    # ==========================================
    coop_records = []
    try:
        coop_response = db.table('cooperative_members') \
            .select('*') \
            .eq('applicant_id', applicant_id) \
            .execute()
        coop_records = coop_response.data or []
    except Exception as e:
        print(f"[Master Builder] ⚠️ Cooperative fetch warning: {e}")
    
    # ==========================================
    # 4. FETCH INCOME SIGNALS (from Income Agent)
    # ==========================================
    income = {}
    try:
        income_response = db.table('income_signal_features') \
            .select('*') \
            .eq('applicant_id', applicant_id) \
            .single() \
            .execute()
        income = income_response.data or {}
    except Exception as e:
        print(f"[Master Builder] ⚠️ Income signals fetch warning: {e}")
        # CRITICAL: Check if income agent actually ran
        if not income:
            print(f"[Master Builder] ❌ CRITICAL: No income_signal_features found for {applicant_id}. "
                  f"Income Agent may not have saved data properly!")
    
    # ==========================================
    # 5. AGGREGATE COOPERATIVES
    # ==========================================
    coop_aggregated = {
        "shares": 0.0,
        "loans": 0.0,
        "status": "none",
        "mem_status": "none",
        "year": None
    }
    for c in coop_records:
        coop_aggregated["shares"] += float(c.get('total_share_value_nrs') or 0)
        coop_aggregated["loans"] += float(c.get('outstanding_loan_nrs') or 0)
        
        status = (c.get('coop_loan_repayment_status') or '').lower()
        if status == 'overdue':
            coop_aggregated["status"] = 'overdue'
        elif status not in ('none', '') and coop_aggregated["status"] == 'none':
            coop_aggregated["status"] = status
        
        mem_status = (c.get('membership_status') or '').lower()
        if mem_status == 'active':
            coop_aggregated["mem_status"] = 'active'
        elif mem_status not in ('none', '') and coop_aggregated["mem_status"] == 'none':
            coop_aggregated["mem_status"] = mem_status
        
        year = c.get('membership_year_bs')
        if year and (coop_aggregated["year"] is None or year < coop_aggregated["year"]):
            coop_aggregated["year"] = year
    
    # ==========================================
    # 6. CALCULATE AGE
    # ==========================================
    age = None
    if profile.get('dob_ad'):
        try:
            dob = datetime.strptime(str(profile['dob_ad']).split(" ")[0], "%Y-%m-%d")
            age = round((datetime.now() - dob).days / 365.25, 1)
        except Exception:
            pass
    
    # ==========================================
    # 7. BUILD MASTER ROW
    # ==========================================
    master_row = {
        # Loan fields
        'application_id': application_id,
        'applicant_id': applicant_id,
        'loan_purpose': loan.get('loan_purpose'),
        'requested_amount_nrs': _clean_amount(loan.get('requested_amount_nrs')),
        'requested_tenure_months': int(loan.get('requested_tenure_months') or 12),
        'collateral_type': loan.get('collateral_type'),
        'collateral_value_nrs': _clean_amount(loan.get('collateral_value_nrs')),
        'existing_loan_count': int(loan.get('existing_loan_count') or 0),
        'final_decision': (loan.get('final_decision') or '').lower().strip(),
        'decision_reason': loan.get('decision_reason'),
        'data_split': 'test',
        
        # Profile fields
        'full_name_en': _fix_name(profile.get('full_name_en')),
        'dob_ad': profile.get('dob_ad'),
        'gender_en': profile.get('gender_en', profile.get('gender', 'Unknown')),
        'marital_status_en': profile.get('marital_status_en', profile.get('marital_status', 'Unknown')),
        'education_level': profile.get('education_level') or 'Unknown',
        'occupation_en': profile.get('occupation_en', 'Unknown'),
        'province_en': profile.get('province_en'),
        'district_en': profile.get('district_en'),
        'municipality_en': profile.get('municipality_en'),
        'ward_no': profile.get('ward_no', 0),
        'rural_urban': profile.get('rural_urban'),
        'has_esewa_account': profile.get('has_esewa_account', False),
        'has_khalti_account': profile.get('has_khalti_account', False),
        'remittance_receiving': profile.get('remittance_receiving', False),
        'cooperative_member': profile.get('cooperative_member', False),
        'cooperative_id': profile.get('cooperative_id'),
        'phone_issue_flag': bool(profile.get('_noise_phone_bad', False)),
        'land_area_ropani': _clean_amount(profile.get('land_area_ropani', 0)),
        'age': age,
        
        # Cooperative aggregated
        'coop_total_share_value_nrs': round(coop_aggregated["shares"], 2),
        'coop_outstanding_loan_nrs': round(coop_aggregated["loans"], 2),
        'coop_loan_repayment_status': coop_aggregated["status"],
        'coop_membership_status': coop_aggregated["mem_status"],
        'coop_membership_year_bs': coop_aggregated["year"],
        
        # Income Agent Features (from income_signal_features table)
        'income_signal_count': int(income.get('income_signal_count') or 0),
        'derived_income_est': int(income.get('derived_income_est') or 0),
        'income_confidence': float(income.get('income_confidence') or 0),
        'remittance_monthly_avg': float(income.get('remittance_monthly_avg') or 0),
        'remittance_regularity_score': float(income.get('remittance_regularity_score') or 0),
        'esewa_net_monthly': float(income.get('esewa_net_monthly') or 0),
        'esewa_tx_count_6months': int(income.get('esewa_tx_count_6months') or 0),
        'cooperative_monthly_sales': float(income.get('cooperative_monthly_sales') or 0),
        'utility_avg_bill_nrs': float(income.get('utility_avg_bill_nrs') or 0),
        'elec_on_time_rate': float(income.get('elec_on_time_rate') or 0.5),
        'overall_on_time_rate': float(income.get('overall_on_time_rate') or 0.5),
        'util_arrears_total_nrs': float(income.get('util_arrears_total_nrs') or 0),
        'coop_tenure_years': float(income.get('coop_tenure_years') or 0),
        
        # Metadata (only include columns that exist in the table)
        # 'master_build_timestamp' and 'noise_flags' removed - not in DB schema
    }
    
    # ==========================================
    # 8. SAVE TO MASTER TABLE
    # ==========================================
    try:
        result = db.table("master_dataset_clean").upsert(
            master_row,
            on_conflict="application_id"
        )
        
        if result.data:
            print(f"✅ Master record saved for application {application_id}")
            return master_row
        else:
            raise RuntimeError(f"Upsert returned no data for {application_id}")
            
    except Exception as e:
        raise RuntimeError(f"Failed to save master record for {application_id}: {e}")
    


def debug_master_build_pipeline(applicant_id: str, application_id: str):
    """Run this to diagnose why master table is empty"""
    print(f"\n{'='*60}")
    print(f"DEBUGGING MASTER BUILD FOR: {applicant_id} / {application_id}")
    print(f"{'='*60}\n")
    
    # Check 1: Profile exists?
    profile = db.table('applicant_profiles').select('*').eq('applicant_id', applicant_id).single().execute().data
    print(f"1. Profile exists: {profile is not None}")
    if profile:
        noise_flags = [k for k in ['_noise_duplicate', '_noise_dob_bad', '_noise_geo_wrong', '_noise_cit_bad', '_noise_ward_issue'] if profile.get(k)]
        print(f"   Noise flags: {noise_flags if noise_flags else 'None'}")
        print(f"   Would be SKIPPED by old code: {bool(noise_flags)}")
    
    # Check 2: Loan application exists?
    loan = db.table('loan_applications').select('*').eq('application_id', application_id).single().execute().data
    print(f"\n2. Loan application exists: {loan is not None}")
    if loan:
        print(f"   Amount: {loan.get('requested_amount_nrs')}")
        print(f"   Income est (from DB): {loan.get('income_agent_monthly_est')}")
    
    # Check 3: Income signals exist?
    income = db.table('income_signal_features').select('*').eq('applicant_id', applicant_id).single().execute().data
    print(f"\n3. Income signal features exist: {income is not None}")
    if income:
        print(f"   derived_income_est: {income.get('derived_income_est')}")
        print(f"   income_confidence: {income.get('income_confidence')}")
    else:
        print(f"   ❌ THIS IS LIKELY THE PROBLEM - Income Agent didn't save to income_signal_features!")
    
    # Check 4: Master record exists?
    try:
        master = db.table('master_dataset_clean').select('*').eq('application_id', application_id).single().execute().data
        print(f"\n4. Master record exists: True")
    except Exception:
        master = None
        print(f"\n4. Master record exists: False (needs to be built)")
    
    print(f"\n{'='*60}\n")