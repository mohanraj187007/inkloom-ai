from sqlalchemy.orm import Session
from datetime import datetime
from models import User, BrandRule, ApprovedFact, Draft, DraftVersion, Finding, AuditLog
from engine.rules import check_draft_rules, calculate_compliance_score


def seed_database(db: Session):
    """
    Preload seed data on first application start if empty.
    Creates 3 demo users, 8 brand rules, 5 approved facts, and 3 demo drafts with deliberate issues.
    """
    # 1. Users
    if db.query(User).count() == 0:
        demo_users = [
            User(username="creator_priya", name="Priya Sharma", role="CREATOR", avatar_color="#4F46E5"),
            User(username="reviewer_arjun", name="Arjun Mehta", role="REVIEWER", avatar_color="#059669"),
            User(username="admin_vikram", name="Vikram Patel", role="ADMIN", avatar_color="#DC2626"),
        ]
        db.add_all(demo_users)
        db.commit()

    priya = db.query(User).filter_by(role="CREATOR").first()
    arjun = db.query(User).filter_by(role="REVIEWER").first()
    vikram = db.query(User).filter_by(role="ADMIN").first()

    # 2. Brand Rules (8 sample rules)
    if db.query(BrandRule).count() == 0:
        sample_rules = [
            BrandRule(
                name="Banned Term: Cheap",
                rule_type="BANNED_TERM",
                pattern="cheap",
                preferred_term="affordable",
                severity="medium",
                explanation="The word 'cheap' devalues the brand. Inkloom products are premium yet accessible.",
                disclaimer_text=None,
                source_reference="Brand Voice Guide v2.4 (Sec 1.2)",
                version="v2.4",
                is_active=True
            ),
            BrandRule(
                name="Medical & Health Cure Claims",
                rule_type="REGEX_CLAIM",
                pattern=r"\b(cures?|heals?|eradicates?)\b",
                preferred_term="promotes wellness and vitality",
                severity="high",
                explanation="Claiming to cure ailments triggers strict drug compliance violations without clinical drug licensing.",
                disclaimer_text=None,
                source_reference="Pharma & Health Advertising Guidelines 2024 (Rule 14)",
                version="v1.8",
                is_active=True
            ),
            BrandRule(
                name="Absolute Guarantee Claims",
                rule_type="REGEX_CLAIM",
                pattern=r"\b(100%\s*guarantee[d]?|guaranteed|guarantee)\b",
                preferred_term="satisfaction promise",
                severity="high",
                explanation="Absolute guarantees create binding legal liabilities. Inkloom uses confident yet realistic promises.",
                disclaimer_text=None,
                source_reference="Consumer Protection Act & Brand Policy (Sec 7.3)",
                version="v2.1",
                is_active=True
            ),
            BrandRule(
                name="Superlative & Leadership Verification",
                rule_type="REGEX_CLAIM",
                pattern=r"\b(best\s+in\s+India|No\.?\s*1|market\s+leader)\b",
                preferred_term="widely recognized",
                severity="medium",
                explanation="Superlative market leadership claims require audited 3rd-party source evidence on file.",
                disclaimer_text=None,
                source_reference="ASCI Truthfulness & Substantiation Code (Sec 1.4)",
                version="v2.0",
                is_active=True
            ),
            BrandRule(
                name="Mandatory Promotional Disclaimer",
                rule_type="MANDATORY_DISCLAIMER",
                pattern=r"\b(\d+%\s*off|discount|sale|special\s+offer)\b",
                preferred_term="*T&C apply. Limited period offer.",
                severity="medium",
                explanation="All percentage discounts and seasonal promotions must carry the mandatory terms disclaimer.",
                disclaimer_text="*T&C apply. Limited period offer.",
                source_reference="Promotional Disclosure Policy 2025 (Sec 2.2)",
                version="v1.5",
                is_active=True
            ),
            BrandRule(
                name="Tone: Avoid ALL CAPS Hype",
                rule_type="TONE",
                pattern=r"\b[A-Z]{3,}(?:\s+[A-Z]{3,})+\b",
                preferred_term="Title Case or lowercase conversational phrasing",
                severity="low",
                explanation="ALL CAPS hype text degrades brand sophistication and triggers spam filters.",
                disclaimer_text=None,
                source_reference="Inkloom Editorial Tone Guide (Sec 4: Nuance & Elegance)",
                version="v1.2",
                is_active=True
            ),
            BrandRule(
                name="Competitor Disparagement",
                rule_type="BANNED_TERM",
                pattern=r"\b(competitor\s+(is\s+)?inferior|worse\s+than\s+(all\s+)?competitors?|beat\s+our\s+rivals)\b",
                preferred_term="stands out with distinctive craftsmanship",
                severity="medium",
                explanation="Disparaging competitors directly harms reputation and invites unfair competition claims.",
                source_reference="Legal & Advertising Standards Council Code (Sec 4.1)",
                version="v1.0",
                is_active=True
            ),
            BrandRule(
                name="Unverified Environmental Claims",
                rule_type="REGEX_CLAIM",
                pattern=r"\b(zero\s+carbon|100%\s*eco-friendly|completely\s+green)\b",
                preferred_term="responsibly produced",
                severity="medium",
                explanation="Green claims must have lifecycle certification to prevent greenwashing penalties.",
                source_reference="Environmental Claims Governance Standard 2025",
                version="v1.1",
                is_active=True
            ),
        ]
        db.add_all(sample_rules)
        db.commit()

    # 3. Approved Facts (5 approved facts with sources)
    if db.query(ApprovedFact).count() == 0:
        sample_facts = [
            ApprovedFact(
                fact_text="Ranked #1 organic tea brand by Consumer Voice in 2025 national survey.",
                claim_type="SUPERLATIVE",
                keywords="best in india, #1, no. 1, ranked #1, consumer voice",
                source_reference="Consumer Voice National Tea Quality Report 2025, Ref #CV-771",
                version="v2.1",
                is_active=True
            ),
            ApprovedFact(
                fact_text="Over 100,000 satisfied customers served across India.",
                claim_type="METRIC",
                keywords="100,000 customers, 100k customers, customers served",
                source_reference="Inkloom ERP & Verified Order Registry Q3 2025",
                version="v1.4",
                is_active=True
            ),
            ApprovedFact(
                fact_text="Clinically tested 94% user satisfaction in 30-day independent wellness trial.",
                claim_type="METRIC",
                keywords="94% satisfaction, clinically tested, 30-day trial",
                source_reference="BioDerm Independent Labs Clinical Study Report #TR-4091",
                version="v1.0",
                is_active=True
            ),
            ApprovedFact(
                fact_text="Sustainably sourced from Fair Trade certified estates in Darjeeling.",
                claim_type="CERTIFICATION",
                keywords="sustainably sourced, Fair Trade, certified estates, Darjeeling",
                source_reference="Fair Trade India Certification #FT-2024-IN-889",
                version="v2.0",
                is_active=True
            ),
            ApprovedFact(
                fact_text="Free shipping on all domestic orders above ₹499.",
                claim_type="PROMOTION",
                keywords="free shipping, above 499, shipping above 499",
                source_reference="Inkloom Standard Shipping Policy & Terms (Updated Jan 2025)",
                version="v1.1",
                is_active=True
            ),
        ]
        db.add_all(sample_facts)
        db.commit()

    # 4. Demo Drafts (3 sample drafts with deliberate issues)
    if db.query(Draft).count() == 0 and priya:
        drafts_info = [
            {
                "title": "Demo Draft 1: Organic Herbal Tea Launch",
                "content": "Our cheap organic green tea is guaranteed to cure all gut issues! It's the best in India. BUY NOW OR MISS OUT!!!",
                "summary": "Initial marketing copy for tea launch with deliberate governance issues",
                "status": "DRAFT"
            },
            {
                "title": "Demo Draft 2: Festive Flash Promotion",
                "content": "Get 50% off on all products! Better than all inferior competitor brands. Our zero carbon products will change your life.",
                "summary": "Festival campaign copy with missing disclaimers and competitor attacks",
                "status": "DRAFT"
            },
            {
                "title": "Demo Draft 3: Customer Proof & Wellness Blend",
                "content": "Over 100,000 customers served across India trust Inkloom. 100% guarantee that you will never look back. It cures fatigue instantly.",
                "summary": "Copy combining verified customer metrics with unauthorized cure guarantees",
                "status": "DRAFT"
            }
        ]

        rules = db.query(BrandRule).filter_by(is_active=True).all()
        approved_facts = db.query(ApprovedFact).filter_by(is_active=True).all()

        for d_info in drafts_info:
            draft = Draft(
                title=d_info["title"],
                creator_id=priya.id,
                status=d_info["status"],
                current_version_num=1,
            )
            db.add(draft)
            db.flush()

            version = DraftVersion(
                draft_id=draft.id,
                version_num=1,
                content=d_info["content"],
                change_summary=d_info["summary"],
                created_by_id=priya.id,
            )
            db.add(version)
            db.flush()

            # Pre-evaluate findings
            findings_data = check_draft_rules(d_info["content"], rules=rules, approved_facts=approved_facts)
            score = calculate_compliance_score(findings_data)
            draft.compliance_score = score

            for f in findings_data:
                finding = Finding(
                    draft_version_id=version.id,
                    matched_text=f["matched_text"],
                    start_pos=f["start_pos"],
                    end_pos=f["end_pos"],
                    severity=f["severity"],
                    status=f["status"],
                    explanation=f["explanation"],
                    rule_source=f["rule_source"],
                    suggested_rewrite=f["suggested_rewrite"],
                    action_taken="pending",
                    engine_source=f["engine_source"],
                )
                db.add(finding)

            # Audit log
            log = AuditLog(
                draft_id=draft.id,
                user_id=priya.id,
                action="DRAFT_CREATED",
                details=f"Draft '{draft.title}' created with initial review completed ({len(findings_data)} findings identified, score: {score}%)."
            )
            db.add(log)

        db.commit()
