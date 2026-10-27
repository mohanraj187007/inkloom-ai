import pytest
from engine.rules import check_draft_rules, calculate_compliance_score


class DummyFact:
    def __init__(self, keywords, fact_text, source_reference):
        self.keywords = keywords
        self.fact_text = fact_text
        self.source_reference = source_reference


def test_empty_and_whitespace_text_handling():
    """Ensure engine never crashes on empty or whitespace strings."""
    assert check_draft_rules("") == []
    assert check_draft_rules("   \n\t  ") == []
    assert check_draft_rules(None) == []
    assert calculate_compliance_score([]) == 100.0


def test_banned_term_cheap_detection():
    """Banned term 'cheap' should be flagged and rewritten to 'affordable'."""
    text = "We offer a cheap organic tea for daily health."
    findings = check_draft_rules(text)
    matched = [f for f in findings if f["matched_text"].lower() == "cheap"]
    assert len(matched) == 1
    assert matched[0]["suggested_rewrite"].lower() == "affordable"
    assert matched[0]["severity"] == "medium"
    assert matched[0]["status"] == "violation"


def test_medical_cure_claims_detection():
    """Medical claims like 'cures all gut issues' must be flagged as high severity violation."""
    text = "Our blend cures gut disease within 2 days."
    findings = check_draft_rules(text)
    cure_findings = [f for f in findings if "cure" in f["matched_text"].lower()]
    assert len(cure_findings) >= 1
    assert cure_findings[0]["severity"] == "high"
    assert cure_findings[0]["status"] == "violation"


def test_absolute_guarantee_detection():
    """Absolute guarantee promises should be flagged as high severity."""
    text = "It is guaranteed to work 100% of the time."
    findings = check_draft_rules(text)
    guarantee_findings = [f for f in findings if "guarantee" in f["matched_text"].lower()]
    assert len(guarantee_findings) >= 1
    assert guarantee_findings[0]["severity"] == "high"


def test_unsubstantiated_superlative_needs_verification():
    """Superlative claims without approved facts must be marked 'needs verification'."""
    text = "Inkloom is the best in India."
    # Without approved facts
    findings = check_draft_rules(text, approved_facts=[])
    superlatives = [f for f in findings if "best in india" in f["matched_text"].lower()]
    assert len(superlatives) == 1
    assert superlatives[0]["status"] == "needs verification"
    assert "missing" in superlatives[0]["explanation"].lower()


def test_mandatory_promotional_disclaimer():
    """Discount claims without mandatory T&C disclaimer must be flagged."""
    text_without_tc = "Special 50% off on all gift boxes this week."
    findings_1 = check_draft_rules(text_without_tc)
    tc_findings = [f for f in findings_1 if "50% off" in f["matched_text"].lower()]
    assert len(tc_findings) == 1
    assert "*T&C apply" in tc_findings[0]["suggested_rewrite"]

    # With disclaimer present
    text_with_tc = "Special 50% off on all gift boxes this week. *T&C apply. Limited period offer."
    findings_2 = check_draft_rules(text_with_tc)
    tc_findings_2 = [f for f in findings_2 if "50% off" in f["matched_text"].lower()]
    assert len(tc_findings_2) == 0


def test_all_caps_tone_violation():
    """ALL CAPS hype phrases should be flagged under tone rules."""
    text = "Organic tea leaves. BUY NOW OR MISS OUT."
    findings = check_draft_rules(text)
    caps_findings = [f for f in findings if "BUY NOW" in f["matched_text"]]
    assert len(caps_findings) == 1
    assert caps_findings[0]["severity"] == "low"


def test_compliance_score_deductions():
    """Verify that compliance score reflects severity of issues."""
    dummy_findings = [
        {"severity": "high"},
        {"severity": "medium"},
        {"severity": "low"}
    ]
    # 100 - 25 - 15 - 5 = 55.0
    score = calculate_compliance_score(dummy_findings)
    assert score == 55.0
