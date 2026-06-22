"""
Mobile Wallet Transaction Parser
================================
Parses eSewa and Khalti statement Excel files and converts them
to the data dictionary schema for mobile_money_transactions.

Output columns (per DATA_DESCRIPTION_Track_A.md §3.3):
- transaction_id: TX-AP-NNNNNN-MMKK
- applicant_id: AP-NNNNNN
- platform: esewa | khalti
- transaction_date: YYYY-MM-DD HH:MM:SS
- transaction_type: from enum
- amount_nrs: STRING
- direction: credit | debit
- counterparty_category: from enum
- geolocation_district: district name
- is_festival_period: BOOLEAN
- _noise_anomaly_flag: BOOLEAN
- _noise_anomaly_type: STRING | NULL
- _noise_null_party: BOOLEAN
- _noise_amount_string: BOOLEAN
"""

import pandas as pd
import numpy as np
import hashlib
from pathlib import Path
from typing import Optional


# ============================================================================
# eSewa PARSER
# ============================================================================

def parse_esewa_statement(
    filepath: str,
    applicant_id: str = "AP-000001",
) -> pd.DataFrame:
    """
    Parse eSewa XLS statement into data dictionary format.

    eSewa columns: Reference Code, Date Time, Description, Dr., Cr., Status, Balance (NPR), Channel
    """
    df = pd.read_excel(filepath, header=8)

    # Drop summary/total rows at the end
    df = df.dropna(subset=["Reference Code"])
    df = df[df["Status"] == "COMPLETE"].copy()

    records = []
    for _, row in df.iterrows():
        ref_code = str(row["Reference Code"])
        desc = str(row.get("Description", ""))
        dr = float(row.get("Dr.", 0) or 0)
        cr = float(row.get("Cr.", 0) or 0)
        dt = pd.to_datetime(row["Date Time"])
        channel = str(row.get("Channel", "App"))

        # Direction
        if cr > 0 and dr == 0:
            direction = "credit"
            amount = cr
        elif dr > 0 and cr == 0:
            direction = "debit"
            amount = dr
        else:
            continue

        # Transaction type from description
        txn_type, counterparty = _classify_esewa_transaction(desc, direction)

        # Festival period (Dashain/Tihar: Oct 2024 = months 6-7 in BS 2081)
        is_festival = dt.month == 10  # October

        # Generate transaction ID from reference
        tx_id = _make_transaction_id(ref_code, applicant_id, dt)

        records.append({
            "transaction_id": tx_id,
            "applicant_id": applicant_id,
            "platform": "esewa",
            "transaction_date": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "transaction_type": txn_type,
            "amount_nrs": str(amount),
            "direction": direction,
            "counterparty_category": counterparty,
            "geolocation_district": "Kathmandu",  # Default for test data
            "is_festival_period": is_festival,
            "_noise_anomaly_flag": False,
            "_noise_anomaly_type": None,
            "_noise_null_party": counterparty is None,
            "_noise_amount_string": False,
        })

    return pd.DataFrame(records)


def _classify_esewa_transaction(description: str, direction: str):
    """
    Classify eSewa transaction into data dictionary transaction_type enum.

    Returns: (transaction_type, counterparty_category)
    """
    desc_upper = description.upper()

    # Credit transactions
    if direction == "credit":
        if "FUND TRANSFERRED BY" in desc_upper:
            return "p2p_transfer", "financial_services"
        if "MONEY TRANSFERRED FROM" in desc_upper:
            return "wallet_topup", "financial_services"
        if "REMITTANCE" in desc_upper or "REMIT" in desc_upper:
            return "remittance_receipt", "remittance_agent"
        if "TOPUP" in desc_upper or "RECHARGE" in desc_upper:
            return "wallet_topup", "telecom"
        return "wallet_topup", "financial_services"

    # Debit transactions
    if "TOPUP" in desc_upper or "RECHARGE" in desc_upper or "NCELL" in desc_upper or "NTC" in desc_upper:
        return "utility_payment", "telecom"
    if "FUND TRANSFERRED TO" in desc_upper:
        return "p2p_transfer", "financial_services"
    if "PAID FOR" in desc_upper:
        # Merchant payment
        merchant = description.replace("Paid for", "").strip()
        category = _categorize_merchant(merchant)
        return "merchant_payment", category
    if "QR" in desc_upper:
        return "qr_payment", "grocery"
    if "WITHDRAW" in desc_upper:
        return "wallet_withdrawal", "financial_services"
    if "LOAN" in desc_upper:
        return "loan_repayment", "financial_services"

    # Default
    return "merchant_payment", None


def _categorize_merchant(merchant_name: str) -> str:
    """Categorize merchant into counterparty_category enum."""
    name_upper = merchant_name.upper()

    grocery_keywords = ["GROCERY", "KIRANA", "KHADHYA", "PASAL", "STORE", "MART", "BAZAAR"]
    medical_keywords = ["MEDICAL", "PHARMA", "HOSPITAL", "CLINIC", "HEALTH"]
    transport_keywords = ["DRIVING", "TRANSPORT", "TAXI", "BUS", "FUEL", "PETROL"]
    restaurant_keywords = ["CAFE", "RESTAURANT", "FOOD", "SWEETS", "SALT"]
    utility_keywords = ["ELECTRICITY", "NEA", "WATER", "INTERNET"]
    telecom_keywords = ["NCELL", "NTC", "TELECOM", "TOPUP", "RECHARGE"]
    agriculture_keywords = ["AGRI", "FARM", "SEED", "FERTILIZER"]
    education_keywords = ["SCHOOL", "COLLEGE", "EDUCATION", "TUITION"]
    financial_keywords = ["BANK", "FINANCE", "INSURANCE"]

    for kw in grocery_keywords:
        if kw in name_upper:
            return "grocery"
    for kw in medical_keywords:
        if kw in name_upper:
            return "medical"
    for kw in transport_keywords:
        if kw in name_upper:
            return "transport"
    for kw in restaurant_keywords:
        if kw in name_upper:
            return "restaurant"
    for kw in utility_keywords:
        if kw in name_upper:
            return "utility"
    for kw in telecom_keywords:
        if kw in name_upper:
            return "telecom"
    for kw in agriculture_keywords:
        if kw in name_upper:
            return "agriculture_input"
    for kw in education_keywords:
        if kw in name_upper:
            return "education"
    for kw in financial_keywords:
        if kw in name_upper:
            return "financial_services"

    return None


# ============================================================================
# KHALTI PARSER
# ============================================================================

def parse_khalti_statement(
    filepath: str,
    applicant_id: str = "AP-000001",
) -> pd.DataFrame:
    """
    Parse Khalti XLSX statement into data dictionary format.

    Khalti columns: Transaction ID, Transaction Type, Transaction State, Transaction Date,
                    Transaction Time, Service, Description, From, To, Username, Fullname,
                    Branch, Purpose, Remarks, Reference, Amount(-) Rs, Amount(+) Rs, Balance
    """
    df = pd.read_excel(filepath, header=0)

    # Filter completed transactions only
    df = df[df["Transaction State"].isin(["Success", "Completed"])].copy()

    records = []
    for _, row in df.iterrows():
        txn_id_raw = str(row.get("Transaction ID", ""))
        txn_type_raw = str(row.get("Transaction Type", ""))
        service = str(row.get("Service", ""))
        desc = str(row.get("Description", ""))
        from_acct = str(row.get("From", ""))
        to_acct = str(row.get("To", ""))
        amount_dr = row.get("Amount(-) Rs", 0) or 0
        amount_cr = row.get("Amount(+) Rs", 0) or 0
        purpose = str(row.get("Purpose", ""))
        remarks = str(row.get("Remarks", ""))

        # Parse date
        date_str = str(row.get("Transaction Date", ""))
        time_str = str(row.get("Transaction Time", ""))
        try:
            dt = pd.to_datetime(f"{date_str} {time_str}")
        except Exception:
            continue

        # Direction
        if amount_cr > 0 and (amount_dr == 0 or pd.isna(amount_dr)):
            direction = "credit"
            amount = float(amount_cr)
        elif amount_dr > 0 and (amount_cr == 0 or pd.isna(amount_cr)):
            direction = "debit"
            amount = float(amount_dr)
        else:
            continue

        # Transaction type
        txn_type, counterparty = _classify_khalti_transaction(
            txn_type_raw, service, desc, purpose, remarks, direction
        )

        # Festival period
        is_festival = dt.month == 10

        # Generate ID
        tx_id = _make_transaction_id(txn_id_raw, applicant_id, dt)

        records.append({
            "transaction_id": tx_id,
            "applicant_id": applicant_id,
            "platform": "khalti",
            "transaction_date": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "transaction_type": txn_type,
            "amount_nrs": str(amount),
            "direction": direction,
            "counterparty_category": counterparty,
            "geolocation_district": "Kathmandu",
            "is_festival_period": is_festival,
            "_noise_anomaly_flag": False,
            "_noise_anomaly_type": None,
            "_noise_null_party": counterparty is None,
            "_noise_amount_string": False,
        })

    return pd.DataFrame(records)


def _classify_khalti_transaction(
    txn_type_raw: str, service: str, desc: str, purpose: str, remarks: str, direction: str
):
    """
    Classify Khalti transaction into data dictionary transaction_type enum.

    Returns: (transaction_type, counterparty_category)
    """
    combined = f"{txn_type_raw} {service} {desc} {purpose} {remarks}".upper()

    # Credit transactions
    if direction == "credit":
        if "BONUS" in combined or "CASHBACK" in combined:
            return "wallet_topup", "financial_services"
        if "TRANSFER" in combined:
            return "p2p_transfer", "financial_services"
        if "REMIT" in combined:
            return "remittance_receipt", "remittance_agent"
        return "wallet_topup", "financial_services"

    # Debit transactions
    if "TOPUP" in combined or "RECHARGE" in combined:
        return "utility_payment", "telecom"
    if "NTC" in combined or "NCELL" in combined:
        return "utility_payment", "telecom"
    if "ELECTRICITY" in combined or "NEA" in combined:
        return "utility_payment", "utility"
    if "SERVICE PAYMENT" in combined:
        if "NTC" in combined or "NCELL" in combined:
            return "utility_payment", "telecom"
        return "merchant_payment", None
    if "TRANSFER" in combined:
        return "p2p_transfer", "financial_services"
    if "QR" in combined:
        return "qr_payment", "grocery"
    if "WITHDRAW" in combined:
        return "wallet_withdrawal", "financial_services"
    if "LOAN" in combined:
        return "loan_repayment", "financial_services"

    return "merchant_payment", None


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def _make_transaction_id(source_id: str, applicant_id: str, dt: pd.Timestamp) -> str:
    """
    Generate transaction_id in format: TX-AP-NNNNNN-MMKK
    Where MM = month (01-12), KK = sequence within month (hashed from source_id)
    """
    month = f"{dt.month:02d}"
    # Use hash of source_id to generate a 2-digit sequence
    hash_val = int(hashlib.md5(source_id.encode()).hexdigest()[:4], 16)
    seq = f"{hash_val % 100:02d}"
    return f"TX-{applicant_id}-{month}{seq}"


# ============================================================================
# BATCH PROCESSING
# ============================================================================

def parse_wallet_statements(
    directory: str,
    applicant_id: str = "AP-000001",
) -> pd.DataFrame:
    """
    Parse all eSewa/Khalti files in a directory.
    Returns combined DataFrame in data dictionary format.
    """
    p = Path(directory)
    all_frames = []

    # Find eSewa files
    for f in p.glob("*.xls"):
        print(f"Parsing eSewa: {f.name}")
        df = parse_esewa_statement(str(f), applicant_id)
        all_frames.append(df)

    # Find Khalti files
    for f in p.glob("*.xlsx"):
        print(f"Parsing Khalti: {f.name}")
        df = parse_khalti_statement(str(f), applicant_id)
        all_frames.append(df)

    if not all_frames:
        return pd.DataFrame()

    combined = pd.concat(all_frames, ignore_index=True)

    # Sort by date
    combined["transaction_date"] = pd.to_datetime(combined["transaction_date"])
    combined = combined.sort_values("transaction_date").reset_index(drop=True)
    combined["transaction_date"] = combined["transaction_date"].dt.strftime("%Y-%m-%d %H:%M:%S")

    return combined


def save_to_csv(df: pd.DataFrame, output_path: str):
    """Save parsed transactions to CSV."""
    df.to_csv(output_path, index=False)
    print(f"Saved {len(df)} transactions to {output_path}")


def save_to_parquet(df: pd.DataFrame, output_path: str):
    """Save parsed transactions to Parquet."""
    df.to_parquet(output_path, index=False)
    print(f"Saved {len(df)} transactions to {output_path}")


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import sys

    directory = sys.argv[1] if len(sys.argv) > 1 else "data/mobile_wallet_transactions"
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "data/dataset/structured"

    print(f"Parsing wallet statements from: {directory}")
    result = parse_wallet_statements(directory)
    print(f"\nParsed {len(result)} transactions")
    print(f"\nTransaction types:\n{result['transaction_type'].value_counts()}")
    print(f"\nDirection:\n{result['direction'].value_counts()}")
    print(f"\nPlatform:\n{result['platform'].value_counts()}")

    # Save
    csv_path = f"{output_dir}/parsed_mobile_wallet_transactions.csv"
    save_to_csv(result, csv_path)

    parquet_path = f"{output_dir}/parsed_mobile_wallet_transactions.parquet"
    save_to_parquet(result, parquet_path)
