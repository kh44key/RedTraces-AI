"""Shared Pakistan cyber-threat detection logic.

Extracted so every collector (X / Facebook / Instagram) classifies text the same
way instead of copy-pasting the indicator lists into each file. The Telegram and
DarkForums collectors keep their own tuned lists for now; the social collectors
(short-post platforms) all share the refined X ruleset below.

analyze_text(text) -> (is_alert, matched_domains, matched_entities, severity)
"""

import re

# ---------------------------------------------------------------------------
# INDICATORS
# ---------------------------------------------------------------------------
GOVT_ENTITY_INDICATORS = list(
    set([
        "gov.pk", "gop.pk", "mil.pk", "government", "govt", "ministry",
        "cabinet", "public sector", "national database", "vehicle registration",
        "transportation", "nadra", "fia", "pta", "fbr", "hec", "secp", "sbp",
        "state bank", "pak army", "pak navy", "paf", "isi", "cnic", "passport",
        "punjab", "sindh", "kpk", "balochistan", "islamabad", "lahore",
        "karachi", "peshawar", "quetta", "نادرا", "پاک فوج", "پاک فضائیہ",
        "پاک بحریہ", "حکومت پاکستان", "حکومت",
    ])
)

BIG_PRIVATE_ENTITY_INDICATORS = list(
    set([
        "jazz", "zong", "telenor", "ufone", "ptcl", "nayatel", "kelectric",
        "lesco", "gepco", "mepco", "fesco", "meezan bank", "hbl", "ubl", "mcb",
        "abl", "bank alfalah", "easypaisa", "jazzcash", "nust", "fast nu",
        "lums", "uol", "giki", "comsats",
    ])
)

PAKISTAN_ENTITY_INDICATORS = list(
    set(
        GOVT_ENTITY_INDICATORS
        + BIG_PRIVATE_ENTITY_INDICATORS
        + ["pakistan", "pakistani"]
    )
)

# Specific compound threat phrases avoid matching harmless uses of words such
# as "leak", "breach", or "database" by themselves.
EXPLICIT_CYBER_ACTIONS = [
    "data leak", "database leak", "db leak", "data breach", "database breach",
    "hacked db", "hacked database", "selling access", "selling db",
    "selling data", "data for sale", "access for sale", "combolist",
    "stealer log", "stealer logs", "exfiltrated", "root access", "sql dump",
    "db dump", "defaced by", "pwned by", "unauthorized access", "darkweb",
    "dark web", "wso webshell", "b374k", "c99shell", "de-face.txt",
    "hacked.txt", "ہیک کر دیا", "ڈیٹا لیک", "ڈیٹا چوری", "ہیکرز",
]

EXCLUDE_WORDS = [
    "neet", "rahul gandhi", "republic", "paper leak", "exam leak", "student",
    "education", "nta", "upsc", "cbse", "mppsc", "bihar", "delhi", "india",
    "paper leaks", "exam", "question paper", "ratta baaz", "patwari", "hiring",
    "vacancy", "job", "technician", "salaries", "recruitment", "career",
    "script", "movie", "dhurander", "funny", "lol", "rainfall", "rain",
    "inundating", "heavy rainfall",
]

# Filtering out routine news, regulatory penalties, and policy news
IGNORE_WORDS = [
    "imposes fine", "slaps fine", "fined", "fine on", "geo-fencing breach",
    "sim geo-fencing", "marital status", "app mobile", "pakid",
    "air force one", "decoy", "assassination threat", "according to data",
    "official data", "weather data", "economic data", "data analysis",
    "file a report", "public record", "data collection", "data entry",
    "categorically rejected", "taken notice of", "denies claims",
    "false reports", "breach of international", "breach of law",
    "breach of obligations", "breach of contract", "ceasefire breach",
    "ceasefire breaches", "lab leak", "super injunction", "crude oil",
    "oil pipeline", "pipeline leak", "gas leak", "water leak", "video leak",
    "pics leak", "movie leak", "spoiler",
]


def analyze_text(text: str):
    """Classify a post. Returns (is_alert, domains, entities, severity)."""
    if not text:
        return False, [], [], "Low"

    text_lower = text.lower()

    # 1. Immediate rejection of false-positive noise and news advisories
    if any(exclude in text_lower for exclude in EXCLUDE_WORDS):
        return False, [], [], "Low"
    if any(ignore in text_lower for ignore in IGNORE_WORDS):
        return False, [], [], "Low"

    # 2. Require a specific cyber action.
    has_cyber_action = any(
        action in text_lower for action in EXPLICIT_CYBER_ACTIONS
    )

    # Single-word terms qualify only when paired with technical exposure data.
    if not has_cyber_action and (
        "breach" in text_lower or "hacked" in text_lower
    ):
        has_cyber_action = any(
            tech in text_lower
            for tech in [
                ".gov.pk", ".mil.pk", "server", "credentials", "admin access",
            ]
        )

    if not has_cyber_action:
        return False, [], [], "Low"

    # 3. Match target domains and entities.
    domain_pattern = r"\b[a-zA-Z0-9.-]+\.(?:gov|pk|gov\.pk|mil\.pk)\b"
    matched_domains = re.findall(domain_pattern, text_lower)
    matched_entities = [
        e for e in PAKISTAN_ENTITY_INDICATORS if e in text_lower
    ]
    # Rule: Must reference Pakistan, a Pakistani entity, or a .pk domain
    if not (matched_domains or matched_entities or "pakistan" in text_lower):
        return False, [], [], "Low"

    # 4. Determine priority level
    is_govt_related = (
        any(
            d.endswith((".gov.pk", ".gop.pk", ".gov", ".mil.pk"))
            for d in matched_domains
        )
        or any(e in GOVT_ENTITY_INDICATORS for e in matched_entities)
        or "government" in text_lower
        or "govt" in text_lower
        or "cnic" in text_lower
    )

    if is_govt_related:
        severity = "High"
    elif any(e in BIG_PRIVATE_ENTITY_INDICATORS for e in matched_entities):
        severity = "Moderate"
    else:
        severity = "Low"

    return True, list(set(matched_domains)), list(set(matched_entities)), severity
