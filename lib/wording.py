"""Wording checks shared by the processors that draft text from data (draft-report,
draft-insights): the numbers show what happened, not why (Pulse PROCESS_DETERMINISM_MAPPING
rule 4), and nothing a client reads uses internal terms or marketing jargon.
"""

from __future__ import annotations

import re

# Words that claim a cause: the data shows what happened, not why.
CAUSAL = re.compile(
    r"\b(?:because|due to|thanks to|led to|leads to|caused?|causing|drove|driven|"
    r"driving|resulted in|results in|that's why)\b",
    re.IGNORECASE,
)
# Words that say data is missing: "because" next to them explains a gap, not a result.
DATA_GAP = re.compile(
    r"\b(?:incomplete|missing|not recorded|not shown|held back|not tracked|not counted|"
    r"left out|leaves? out|leaving out|with complete (?:data|numbers))\b",
    re.IGNORECASE,
)
# How the report is made, which the client never needs to read.
INTERNAL = re.compile(
    r"\b(?:report engine|engine|snapshots?|data quality|highlight slots?)\b", re.IGNORECASE
)
# Jargon the Pulse docs keep off client surfaces (PROJECT_SCOPE pre-flight scan and
# plain-English rule).
JARGON = re.compile(
    r"\b(?:impressions?|CTR|CPC|KPIs?|conversions?|funnel|video completions?)\b",
    re.IGNORECASE,
)
