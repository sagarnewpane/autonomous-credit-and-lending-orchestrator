from app.agents.income_agent import compute_imr, compute_income_assessment


def _db(**kw):
    base = {"mobile_txns": [], "remittances": [], "coop_sales": [], "utility_payments": [],
            "coop_member_type": "", "coop_membership_year_bs": None, "land_area_ropani": 0.0,
            "occupation": "farmer", "reference_bs_year": 2081}
    base.update(kw)
    return base


def _wallet(n_months=6, amount=500.0, category="grocery"):
    return [{"transaction_id": f"T{i}", "transaction_date": f"2024-0{i + 1}-10 10:00:00", "amount_nrs": amount,
             "direction": "credit", "counterparty_category": category, "transaction_type": "p2p_transfer",
             "platform": "esewa", "_noise_anomaly_flag": False, "_noise_amount_string": False}
            for i in range(n_months)]


def test_low_income_is_not_replaced_by_an_assumed_floor():
    # Regression: farmers with little observed income used to be assigned NPR 20,000 a month.
    a = compute_income_assessment(_db(mobile_txns=_wallet(amount=300.0)))
    assert a["estimated_income"] < 3000
    assert "LOW_OBSERVED_INCOME" in a["income_flags"]


def test_remittances_keep_their_dates_and_count_as_income():
    # Regression: remittance dates were dropped, so remittances never entered the profile.
    rem = [{"remittance_id": f"R{i}", "applicant_id": "A", "transfer_date_ad": f"2024-0{i + 1}-05",
            "received_date_ad": f"2024-0{i + 1}-06", "amount_nrs": 20000.0, "exchange_rate": 0.0,
            "amount_foreign_currency": 0.0, "sender_country_code": "", "foreign_currency_code": "",
            "_noise_wrong_currency": False, "_noise_impossible_rate": False, "_noise_duplicate": False}
           for i in range(6)]
    a = compute_income_assessment(_db(remittances=rem))
    assert "remittance_agent" in a["income_profile"]["sources"]
    assert 15000 <= a["estimated_income"] <= 25000
    assert a["remittance_share"] == 1.0
    assert 15000 <= a["income_signal_features"]["remittance_monthly_avg"] <= 25000


def test_cooperative_sales_are_annualised():
    sales = [{"sale_year_bs": "2079", "season": "Kharif", "total_amount_nrs": 60000},
             {"sale_year_bs": "2079", "season": "Rabi", "total_amount_nrs": 60000},
             {"sale_year_bs": "2080", "season": "Annual", "total_amount_nrs": 120000}]
    a = compute_income_assessment(_db(coop_sales=sales, coop_member_type="dairy"))
    # two years, NPR 120,000 a year -> NPR 10,000 a month
    assert a["income_signal_features"]["cooperative_monthly_sales"] == 10000
    assert a["income_profile"]["income"]["months_of_data"] == 0  # BS years do not widen the monthly window


def test_savings_cooperatives_carry_no_sales_income():
    sales = [{"sale_year_bs": "2080", "season": "Annual", "total_amount_nrs": 120000}]
    a = compute_income_assessment(_db(coop_sales=sales, coop_member_type="savings_credit"))
    assert a["income_signal_features"]["cooperative_monthly_sales"] == 0


def test_compute_imr_statuses():
    assert compute_imr(None, 20000) == (None, "not_declared")
    assert compute_imr(0, 20000) == (None, "not_declared")
    assert compute_imr(20000, 500) == (None, "insufficient_observed")
    assert compute_imr(30000, 20000) == (1.5, "computed")


def test_no_records_gives_low_confidence_and_no_income():
    a = compute_income_assessment(_db())
    assert a["estimated_income"] == 0 and a["confidence"] == 0.05


def test_wallet_credits_are_grouped_by_transaction_type_not_counterparty():
    # Regression: grouping by counterparty_category (unrelated to the type in Track A) turned
    # a top-up into "telecom" income and inflated the number of income sources.
    txns = _wallet(category="telecom")
    for t in txns[:3]:
        t["transaction_type"] = "wallet_topup"
    for t in txns[3:]:
        t["transaction_type"] = "remittance_receipt"
    a = compute_income_assessment(_db(mobile_txns=txns))
    assert set(a["income_profile"]["sources"]) == {"wallet_topup", "remittance_agent"}
    assert 0 < a["remittance_share"] < 1


def test_cleaning_ignores_generator_noise_labels():
    # A row labelled as a duplicate is kept unless it really repeats another row; a true
    # repeat with a new ID is dropped. Lenders do not see the generator's _noise_* labels.
    base = {"applicant_id": "A", "transfer_date_ad": "2024-01-05", "received_date_ad": "2024-01-06",
            "amount_nrs": 20000.0, "exchange_rate": 0.0, "amount_foreign_currency": 0.0,
            "sender_country_code": "", "foreign_currency_code": ""}
    rem = [{**base, "remittance_id": "R1", "_noise_duplicate": False},
           {**base, "remittance_id": "R2", "_noise_duplicate": False},          # repeat with a new ID
           {**base, "remittance_id": "R3", "transfer_date_ad": "2024-02-05",
            "received_date_ad": "2024-02-06", "_noise_duplicate": True}]        # labelled, but new
    a = compute_income_assessment(_db(remittances=rem))
    assert a["counts"]["cleaned_counts"]["remittance"] == 2


def test_records_after_the_as_of_date_are_set_aside(monkeypatch):
    monkeypatch.setenv("INCOME_AS_OF_DATE", "2024-03-31T23:59:59")
    a = compute_income_assessment(_db(mobile_txns=_wallet(n_months=6, amount=5000.0)))
    assert a["income_profile"]["income"]["months_of_data"] == 3
    assert len([f for f in a["anomaly_flags"] if "transaction_id" in f]) == 3


def test_extra_columns_do_not_change_the_result():
    # Regression: repeats were found by comparing every column present, so the batch
    # experiments (which load fewer columns) and the live pipeline disagreed.
    bill = {"applicant_id": "A", "utility_type": "electricity", "provider": "NEA", "service_number": "S1",
            "bill_amount_nrs": 400.0, "payment_date_ad": None, "days_late": None, "outstanding_arrears_nrs": 400.0}
    bills = [{**bill, "billing_period_ad": f"2024-0{m}", "due_date_ad": f"2024-0{m}-20"} for m in range(1, 4)]
    wide = [{**b, "payment_id": f"P{i}", "province_en": "Koshi", "cumulative_on_time_rate": 0.5 + i / 10}
            for i, b in enumerate(bills)]
    a = compute_income_assessment(_db(utility_payments=bills))["income_signal_features"]
    b = compute_income_assessment(_db(utility_payments=wide))["income_signal_features"]
    assert a == b and a["util_arrears_total_nrs"] == 1200.0
