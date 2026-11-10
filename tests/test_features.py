from app.services.credit_features import FEATURES, MONOTONE


def test_no_unconstrained_copy_of_a_constrained_feature():
    # Regression: elec_on_time_rate always equals overall_on_time_rate; as an unconstrained
    # model input it let PD rise with on-time payments despite the monotone constraint.
    assert "elec_on_time_rate" not in FEATURES
    assert set(MONOTONE) <= set(FEATURES)


def test_no_protected_attributes_or_generator_scores_as_inputs():
    banned = {"gender", "marital_status", "age", "province_en", "district_en", "rural_urban",
              "credit_score", "income_confidence_organiser", "default_probability_model"}
    assert not banned & set(FEATURES)
