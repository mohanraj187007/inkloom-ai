import re
from typing import List, Dict, Any, Optional


def check_draft_rules(
    text: str,
    rules: Optional[List[Any]] = None,
    approved_facts: Optional[List[Any]] = None
) -> List[Dict[str, Any]]:
    """
    Deterministic rule-based brand governance engine.
    Evaluates text against brand rules and approved facts.
    Guaranteed not to crash on empty or whitespace-only text.
    """
    if not text or not text.strip():
        return []

    findings: List[Dict[str, Any]] = []

    # Map approved facts for quick keyword matching
    facts_list = approved_facts or []

    # 1. Banned and Preferred Terms
    # Check for "cheap" -> "affordable" and other banned terms
    banned_checks = [
        {
            "pattern": r"\b(dirt[\s-]cheap|cheap)\b",
            "name": "Banned Term: Cheap",
            "preferred": "affordable",
            "severity": "medium",
            "explanation": "The word 'cheap' devalues brand perception and connotes low quality. Use premium, value-focused terminology.",
            "rule_source": "Brand Voice Guide v2.4 (Sec 1.2)",
            "status": "violation"
        },
        {
            "pattern": r"\b(competitor\s+(is\s+)?inferior|worse\s+than\s+(all\s+)?competitors?|beat\s+our\s+rivals)\b",
            "name": "Competitor Disparagement",
            "preferred": "stands out for distinctive craftsmanship",
            "severity": "medium",
            "explanation": "Comparative disparagement violates advertising ethics standards and brand guidelines. Focus on our own value.",
            "rule_source": "Legal & Advertising Standards Council Code (Sec 4.1)",
            "status": "violation"
        }
    ]

    for item in banned_checks:
        for match in re.finditer(item["pattern"], text, flags=re.IGNORECASE):
            matched_str = match.group(0)
            # preserve original capitalization pattern if possible
            replacement = item["preferred"]
            if matched_str.isupper():
                replacement = replacement.upper()
            elif matched_str[0].isupper():
                replacement = replacement.capitalize()

            findings.append({
                "matched_text": matched_str,
                "start_pos": match.start(),
                "end_pos": match.end(),
                "severity": item["severity"],
                "status": item["status"],
                "explanation": item["explanation"],
                "rule_source": item["rule_source"],
                "suggested_rewrite": replacement,
                "engine_source": "rule_engine"
            })

    # 2. Medical / Health / Cure Absolute Claims (High Severity)
    medical_patterns = [
        (
            r"\b(cures?|heals?|remedies|eradicates?)\b",
            "Absolute Medical Claim",
            "promotes wellness and supports overall vitality",
            "high",
            "Claiming to 'cure' or 'heal' conditions triggers strict drug/medical compliance liabilities without clinical drug license certification.",
            "Pharma & Consumer Health Act, Rule 14"
        ),
        (
            r"\b(cures?\s+all\s+\w+|cures?\s+\w+)\b",
            "Absolute Medical Claim",
            "supports wellness and vitality",
            "high",
            "Medical claims promising disease elimination without pharmaceutical validation are illegal and brand violations.",
            "Pharma & Consumer Health Act, Rule 14"
        )
    ]

    # Deduplicate cure matches
    for pat, name, rewrite, sev, expl, src in medical_patterns:
        for match in re.finditer(pat, text, flags=re.IGNORECASE):
            # Check if already covered by an earlier match overlapping
            if not any(f["start_pos"] <= match.start() < f["end_pos"] for f in findings):
                findings.append({
                    "matched_text": match.group(0),
                    "start_pos": match.start(),
                    "end_pos": match.end(),
                    "severity": sev,
                    "status": "violation",
                    "explanation": expl,
                    "rule_source": src,
                    "suggested_rewrite": rewrite,
                    "engine_source": "rule_engine"
                })

    # 3. Absolute Guarantee Claims (High Severity)
    guarantee_pat = r"\b(100%\s*guarantee[d]?|guaranteed|guarantee)\b"
    for match in re.finditer(guarantee_pat, text, flags=re.IGNORECASE):
        if not any(f["start_pos"] <= match.start() < f["end_pos"] for f in findings):
            findings.append({
                "matched_text": match.group(0),
                "start_pos": match.start(),
                "end_pos": match.end(),
                "severity": "high",
                "status": "violation",
                "explanation": "Absolute guarantee promises create binding consumer warranty obligations. Rephrase with confidence without legal guarantees.",
                "rule_source": "Consumer Protection Guidelines 2024 (Sec 7.3)",
                "suggested_rewrite": "backed by our customer satisfaction promise",
                "engine_source": "rule_engine"
            })

    # 4. Superlative & Market Leadership Claims ("best in India", "No. 1", "first ever")
    superlative_patterns = [
        (r"\b(best\s+in\s+India|No\.?\s*1\s+in\s+India|India'?s\s+(#1|No\.?\s*1|best))\b", "best in India"),
        (r"\b(No\.?\s*1|#1|market\s+leader|industry\s+first)\b", "market leader"),
        (r"\b(zero\s+carbon|100%\s*eco-friendly|completely\s+green)\b", "zero carbon")
    ]

    for pat, claim_key in superlative_patterns:
        for match in re.finditer(pat, text, flags=re.IGNORECASE):
            matched_text = match.group(0)
            if any(f["start_pos"] <= match.start() < f["end_pos"] for f in findings):
                continue

            # Cross reference against approved facts
            verified_fact = None
            for fact in facts_list:
                fact_keywords = getattr(fact, "keywords", "") or ""
                fact_text = getattr(fact, "fact_text", "") or ""
                kw_tokens = [k.strip().lower() for k in fact_keywords.split(",") if k.strip()]
                if any(kw in matched_text.lower() or kw in text.lower() for kw in kw_tokens):
                    verified_fact = fact
                    break

            if verified_fact:
                # If verified, we can either skip or attach an informational note
                # But requirement says: "If a factual claim has no approved source, mark it 'needs verification' and say evidence is missing."
                # Since it has an approved source, it is verified!
                pass
            else:
                findings.append({
                    "matched_text": matched_text,
                    "start_pos": match.start(),
                    "end_pos": match.end(),
                    "severity": "medium",
                    "status": "needs verification",
                    "explanation": f"Factual superlative claim '{matched_text}' has no approved source or substantiation on file. Evidence is missing.",
                    "rule_source": "Advertising Standards Council of India (ASCI) Truthfulness Code (Rule 1.4)",
                    "suggested_rewrite": f"one of India's most loved tea selections [Source: Pending verification]",
                    "engine_source": "rule_engine"
                })

    # 5. Mandatory Disclaimer Rule for Discounts and Promotions
    discount_match = re.search(r"\b(\d+%\s*off|discount|special\s+offer|sale)\b", text, flags=re.IGNORECASE)
    if discount_match:
        disclaimer_pat = r"(\*?T&C\s*apply|terms\s*&\s*conditions|limited\s*period\s*offer)"
        if not re.search(disclaimer_pat, text, flags=re.IGNORECASE):
            findings.append({
                "matched_text": discount_match.group(0),
                "start_pos": discount_match.start(),
                "end_pos": discount_match.end(),
                "severity": "medium",
                "status": "violation",
                "explanation": "Discount or promotional offer detected without mandatory disclaimer statement (*T&C apply. Limited period offer).",
                "rule_source": "Promotional Disclosure Policy 2025 (Sec 2.2)",
                "suggested_rewrite": f"{discount_match.group(0)}* (*T&C apply. Limited period offer)",
                "engine_source": "rule_engine"
            })

    # 6. Tone Rule: ALL CAPS Hype & Excessive Exclamation
    # Detect 2 or more consecutive uppercase words of length >= 3 or excessive exclamation marks (>= 2)
    caps_hype_match = re.search(r"\b[A-Z]{3,}(?:\s+[A-Z]{3,})+\b", text)
    if caps_hype_match:
        matched_caps = caps_hype_match.group(0)
        findings.append({
            "matched_text": matched_caps,
            "start_pos": caps_hype_match.start(),
            "end_pos": caps_hype_match.end(),
            "severity": "low",
            "status": "violation",
            "explanation": "ALL CAPS text sounds aggressive and spammy. Inkloom brand tone is calm, thoughtful, and articulate.",
            "rule_source": "Inkloom Editorial Tone Guide (Sec 4: Nuance & Elegance)",
            "suggested_rewrite": matched_caps.capitalize(),
            "engine_source": "rule_engine"
        })

    exclamation_match = re.search(r"!{2,}", text)
    if exclamation_match:
        findings.append({
            "matched_text": exclamation_match.group(0),
            "start_pos": exclamation_match.start(),
            "end_pos": exclamation_match.end(),
            "severity": "low",
            "status": "violation",
            "explanation": "Multiple exclamation marks violate professional editorial voice.",
            "rule_source": "Inkloom Editorial Tone Guide (Sec 4)",
            "suggested_rewrite": ".",
            "engine_source": "rule_engine"
        })

    # 7. Also evaluate dynamic rules from DB if passed
    if rules:
        for r in rules:
            if not getattr(r, "is_active", True):
                continue
            rule_pattern = getattr(r, "pattern", "")
            if not rule_pattern:
                continue

            # If rule is already one of the built-ins above, avoid exact duplicate finding
            rule_name = getattr(r, "name", "")
            already_flagged = any(f["rule_source"] == getattr(r, "source_reference", "") or f["matched_text"].lower() in rule_pattern.lower() for f in findings)
            if already_flagged:
                continue

            try:
                for match in re.finditer(r"\b" + re.escape(rule_pattern) + r"\b", text, flags=re.IGNORECASE):
                    # Check overlap
                    if not any(f["start_pos"] <= match.start() < f["end_pos"] for f in findings):
                        findings.append({
                            "matched_text": match.group(0),
                            "start_pos": match.start(),
                            "end_pos": match.end(),
                            "severity": getattr(r, "severity", "medium"),
                            "status": "violation" if getattr(r, "rule_type", "") != "CLAIM" else "needs verification",
                            "explanation": getattr(r, "explanation", f"Matched brand rule {rule_name}"),
                            "rule_source": getattr(r, "source_reference", rule_name),
                            "suggested_rewrite": getattr(r, "preferred_term", "") or "[Revise phrase]",
                            "engine_source": "rule_engine"
                        })
            except Exception:
                # If regex fails, skip gracefully
                pass

    # Sort findings by start_pos ascending
    findings.sort(key=lambda x: x["start_pos"])
    return findings


def calculate_compliance_score(findings: List[Dict[str, Any]]) -> float:
    """
    Computes a 0 to 100 brand compliance score based on findings severity.
    High violation: -25 pts
    Medium violation / needs verification: -15 pts
    Low violation: -5 pts
    """
    if not findings:
        return 100.0

    deductions = 0
    for f in findings:
        sev = (f.get("severity") or "medium").lower()
        if sev == "high":
            deductions += 25
        elif sev == "medium":
            deductions += 15
        elif sev == "low":
            deductions += 5
        else:
            deductions += 10

    score = max(0.0, min(100.0, 100.0 - deductions))
    return round(score, 1)
