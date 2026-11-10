# Legacy files

Kept for transparency about the hackathon version. Nothing in `app/` imports them.

| File | What it was | Why it was retired |
| --- | --- | --- |
| `hackathon_model/xgboost_4class_model.pkl` and companions | Four-class XGBoost trained on the Track A `final_decision` label | The label is a deterministic function of other Track A fields (see `experiments/e1_label_circularity.py`); `model_config.json` listed 64 features while the model expects 60, so the shipped scorer failed on every call; the credit score was 300 + 550 × the winning class probability, so confident rejections scored high. |
| `score_calculations.py` | Rule-based scorecard and identity-mismatch helpers | Never called by the pipeline. |

Do not load the `.pkl` files from untrusted copies: unpickling runs code.
