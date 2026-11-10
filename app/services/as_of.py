"""
The point in time the Income Agent treats as "now".

Records dated after it are left out of the income profile and reported as anomalies.
Set INCOME_AS_OF_DATE (ISO date or date-time) to replay a dataset reproducibly; otherwise
the current time is used. The Track A records run from January to June 2024, so the
offline backend and the experiments set TRACK_A_AS_OF.
"""

from __future__ import annotations

import os
from datetime import datetime

TRACK_A_AS_OF = "2024-06-30T23:59:59"


def as_of() -> datetime:
    value = os.getenv("INCOME_AS_OF_DATE")
    if value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return datetime.now()
