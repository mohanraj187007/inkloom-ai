import os
import re
from datetime import datetime
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, Header, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from database import engine, Base, get_db
import models
from models import User, BrandRule, ApprovedFact, Draft, DraftVersion, Finding, ReviewComment, AuditLog
from engine.rules import check_draft_rules, calculate_compliance_score
from engine.gemini import check_with_gemini
from seed_data import seed_database

# Create DB tables
Base.metadata.create_all(bind=engine)

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = next(get_db())
    try:
        seed_database(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="Inkloom AI",
    description="Brand-governance web app for real-time copy compliance, claim verification, and review workflows",
    version="1.0.0",
    lifespan=lifespan
)

# Static files setup
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


# Pydantic schemas
class DraftCreate(BaseModel):
    title: str
    content: str


class DraftUpdateText(BaseModel):
    content: str
    change_summary: Optional[str] = "Manual edit"


class FindingEditRequest(BaseModel):
    custom_text: str


class SubmitReviewRequest(BaseModel):
    comment: Optional[str] = "Ready for compliance review"


class ReviewerActionRequest(BaseModel):
    action: str  # "APPROVE", "REQUEST_CHANGES", "REJECT"
    comment: Optional[str] = ""


class RuleCreate(BaseModel):
    name: str
    rule_type: str
    pattern: str
    preferred_term: Optional[str] = ""
    severity: str = "medium"
    explanation: str
    disclaimer_text: Optional[str] = None
    source_reference: str
    version: str = "v1.0"


class FactCreate(BaseModel):
    fact_text: str
    claim_type: str = "SUPERLATIVE"
    keywords: str
    source_reference: str
    version: str = "v1.0"


# Helper for active user
def get_current_user(
    x_user_id: Optional[int] = Header(None),
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
) -> User:
    target_id = x_user_id or user_id
    if target_id:
        user = db.query(User).filter(User.id == target_id).first()
        if user:
            return user
    # Default to creator Priya if not specified
    creator = db.query(User).filter_by(role="CREATOR").first()
    return creator


# --- USER & AUTH ENDPOINTS ---
@app.get("/api/users")
def list_demo_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "name": u.name,
            "role": u.role,
            "avatar_color": u.avatar_color
        }
        for u in users
    ]


@app.get("/api/me")
def get_current_user_profile(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "username": user.username,
        "name": user.name,
        "role": user.role,
        "avatar_color": user.avatar_color
    }


# --- DRAFTS & WORKFLOW ENDPOINTS ---
@app.get("/api/drafts")
def get_drafts(
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Draft).order_by(Draft.updated_at.desc())
    if status and status.upper() != "ALL":
        query = query.filter(Draft.status == status.upper())
    drafts = query.all()

    result = []
    for d in drafts:
        # Get latest version
        latest_ver = db.query(DraftVersion).filter_by(draft_id=d.id, version_num=d.current_version_num).first()
        pending_findings = 0
        if latest_ver:
            pending_findings = db.query(Finding).filter_by(draft_version_id=latest_ver.id, action_taken="pending").count()

        result.append({
            "id": d.id,
            "title": d.title,
            "status": d.status,
            "current_version_num": d.current_version_num,
            "compliance_score": d.compliance_score,
            "creator": {"id": d.creator.id, "name": d.creator.name, "role": d.creator.role} if d.creator else None,
            "reviewer": {"id": d.reviewer.id, "name": d.reviewer.name, "role": d.reviewer.role} if d.reviewer else None,
            "pending_findings_count": pending_findings,
            "created_at": d.created_at.isoformat(),
            "updated_at": d.updated_at.isoformat(),
            "preview_snippet": (latest_ver.content[:140] + "...") if latest_ver and len(latest_ver.content) > 140 else (latest_ver.content if latest_ver else "")
        })
    return result


@app.post("/api/drafts")
def create_draft(
    payload: DraftCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    draft = Draft(
        title=payload.title.strip() or "Untitled Copy Draft",
        creator_id=user.id,
        status="DRAFT",
        current_version_num=1,
    )
    db.add(draft)
    db.flush()

    version = DraftVersion(
        draft_id=draft.id,
        version_num=1,
        content=payload.content,
        change_summary="Initial draft created",
        created_by_id=user.id,
    )
    db.add(version)
    db.flush()

    # Run review engine on initial content
    rules = db.query(BrandRule).filter_by(is_active=True).all()
    facts = db.query(ApprovedFact).filter_by(is_active=True).all()
    findings = check_draft_rules(payload.content, rules=rules, approved_facts=facts)

    # Optional Gemini check
    llm_findings = check_with_gemini(payload.content)
    findings.extend(llm_findings)

    score = calculate_compliance_score(findings)
    draft.compliance_score = score

    for f in findings:
        finding = Finding(
            draft_version_id=version.id,
            matched_text=f["matched_text"],
            start_pos=f.get("start_pos", -1),
            end_pos=f.get("end_pos", -1),
            severity=f.get("severity", "medium"),
            status=f.get("status", "violation"),
            explanation=f["explanation"],
            rule_source=f["rule_source"],
            suggested_rewrite=f["suggested_rewrite"],
            action_taken="pending",
            engine_source=f.get("engine_source", "rule_engine"),
        )
        db.add(finding)

    # Audit log
    db.add(AuditLog(
        draft_id=draft.id,
        user_id=user.id,
        action="DRAFT_CREATED",
        details=f"Draft created by {user.name} ({len(findings)} initial findings identified, score: {score}%)."
    ))

    db.commit()
    db.refresh(draft)
    return {"id": draft.id, "message": "Draft created successfully"}


@app.get("/api/drafts/{draft_id}")
def get_draft_details(
    draft_id: int,
    db: Session = Depends(get_db)
):
    draft = db.query(Draft).filter(Draft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    # Current version
    current_version = db.query(DraftVersion).filter_by(draft_id=draft.id, version_num=draft.current_version_num).first()
    findings = []
    if current_version:
        v_findings = db.query(Finding).filter_by(draft_version_id=current_version.id).all()
        findings = [
            {
                "id": f.id,
                "matched_text": f.matched_text,
                "start_pos": f.start_pos,
                "end_pos": f.end_pos,
                "severity": f.severity,
                "status": f.status,
                "explanation": f.explanation,
                "rule_source": f.rule_source,
                "suggested_rewrite": f.suggested_rewrite,
                "action_taken": f.action_taken,
                "engine_source": f.engine_source
            }
            for f in v_findings
        ]

    # Versions list
    versions = []
    for v in draft.versions:
        versions.append({
            "id": v.id,
            "version_num": v.version_num,
            "content": v.content,
            "change_summary": v.change_summary,
            "created_by": v.created_by.name if v.created_by else "Unknown",
            "created_at": v.created_at.isoformat()
        })

    # Comments
    comments = []
    for c in draft.comments:
        comments.append({
            "id": c.id,
            "user": {"id": c.user.id, "name": c.user.name, "role": c.user.role},
            "action": c.action,
            "comment_text": c.comment_text,
            "created_at": c.created_at.isoformat()
        })

    # Audit logs
    audit_logs = []
    for a in draft.audit_logs:
        audit_logs.append({
            "id": a.id,
            "user": a.user.name if a.user else "System",
            "action": a.action,
            "details": a.details,
            "timestamp": a.timestamp.isoformat()
        })

    return {
        "id": draft.id,
        "title": draft.title,
        "status": draft.status,
        "current_version_num": draft.current_version_num,
        "compliance_score": draft.compliance_score,
        "creator": {"id": draft.creator.id, "name": draft.creator.name, "role": draft.creator.role} if draft.creator else None,
        "reviewer": {"id": draft.reviewer.id, "name": draft.reviewer.name, "role": draft.reviewer.role} if draft.reviewer else None,
        "created_at": draft.created_at.isoformat(),
        "updated_at": draft.updated_at.isoformat(),
        "current_content": current_version.content if current_version else "",
        "findings": findings,
        "versions": versions,
        "comments": comments,
        "audit_logs": audit_logs
    }


@app.post("/api/drafts/{draft_id}/review")
def re_evaluate_draft(
    draft_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Reruns the review engine on the draft's current version text.
    Deterministic checks + optional Gemini LLM tone/claim check.
    """
    draft = db.query(Draft).filter(Draft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    current_version = db.query(DraftVersion).filter_by(draft_id=draft.id, version_num=draft.current_version_num).first()
    if not current_version:
        raise HTTPException(status_code=400, detail="Current draft version missing")

    rules = db.query(BrandRule).filter_by(is_active=True).all()
    facts = db.query(ApprovedFact).filter_by(is_active=True).all()

    # 1. Deterministic rules
    deterministic_findings = check_draft_rules(current_version.content, rules=rules, approved_facts=facts)

    # 2. Optional Gemini check
    llm_findings = check_with_gemini(current_version.content)

    all_findings = deterministic_findings + llm_findings

    # Clear old findings for this version
    db.query(Finding).filter_by(draft_version_id=current_version.id).delete()

    for f in all_findings:
        finding = Finding(
            draft_version_id=current_version.id,
            matched_text=f["matched_text"],
            start_pos=f.get("start_pos", -1),
            end_pos=f.get("end_pos", -1),
            severity=f.get("severity", "medium"),
            status=f.get("status", "violation"),
            explanation=f["explanation"],
            rule_source=f["rule_source"],
            suggested_rewrite=f["suggested_rewrite"],
            action_taken="pending",
            engine_source=f.get("engine_source", "rule_engine"),
        )
        db.add(finding)

    score = calculate_compliance_score(all_findings)
    draft.compliance_score = score
    draft.updated_at = datetime.utcnow()

    db.add(AuditLog(
        draft_id=draft.id,
        user_id=user.id,
        action="REVIEW_RUN",
        details=f"Compliance review executed by {user.name} ({len(all_findings)} findings identified, compliance score: {score}%)."
    ))

    db.commit()
    return {"message": "Review completed successfully", "score": score, "findings_count": len(all_findings)}


@app.post("/api/drafts/{draft_id}/findings/{finding_id}/accept")
def accept_finding_fix(
    draft_id: int,
    finding_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Accepting a fix automatically substitutes the matched text with the suggested rewrite,
    creates a new version of the draft, and re-evaluates the copy.
    """
    draft = db.query(Draft).filter(Draft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    current_version = db.query(DraftVersion).filter_by(draft_id=draft.id, version_num=draft.current_version_num).first()
    if not current_version:
        raise HTTPException(status_code=400, detail="Current version not found")

    old_content = current_version.content
    matched = finding.matched_text
    replacement = finding.suggested_rewrite

    # Substitute the matched occurrence
    # If finding has positions, replace at positions; otherwise regex/string replace once
    if finding.start_pos >= 0 and finding.end_pos > finding.start_pos and old_content[finding.start_pos:finding.end_pos] == matched:
        new_content = old_content[:finding.start_pos] + replacement + old_content[finding.end_pos:]
    else:
        # Case insensitive replace single match
        pattern = re.compile(re.escape(matched), re.IGNORECASE)
        new_content = pattern.sub(replacement, old_content, count=1)

    # Mark this finding accepted
    finding.action_taken = "accepted"

    # Create new draft version
    new_version_num = draft.current_version_num + 1
    new_version = DraftVersion(
        draft_id=draft.id,
        version_num=new_version_num,
        content=new_content,
        change_summary=f"Accepted fix: '{matched}' -> '{replacement}'",
        created_by_id=user.id,
    )
    db.add(new_version)
    db.flush()

    draft.current_version_num = new_version_num
    draft.updated_at = datetime.utcnow()

    # Re-evaluate rules on the new version
    rules = db.query(BrandRule).filter_by(is_active=True).all()
    facts = db.query(ApprovedFact).filter_by(is_active=True).all()
    new_findings = check_draft_rules(new_content, rules=rules, approved_facts=facts)

    for nf in new_findings:
        f_obj = Finding(
            draft_version_id=new_version.id,
            matched_text=nf["matched_text"],
            start_pos=nf.get("start_pos", -1),
            end_pos=nf.get("end_pos", -1),
            severity=nf.get("severity", "medium"),
            status=nf.get("status", "violation"),
            explanation=nf["explanation"],
            rule_source=nf["rule_source"],
            suggested_rewrite=nf["suggested_rewrite"],
            action_taken="pending",
            engine_source=nf.get("engine_source", "rule_engine"),
        )
        db.add(f_obj)

    score = calculate_compliance_score(new_findings)
    draft.compliance_score = score

    # Audit log
    db.add(AuditLog(
        draft_id=draft.id,
        user_id=user.id,
        action="FINDING_ACCEPTED",
        details=f"{user.name} accepted fix for '{matched}'. Created Version {new_version_num}. New score: {score}%."
    ))

    db.commit()
    return {
        "message": "Fix accepted and new version created",
        "new_version_num": new_version_num,
        "score": score
    }


@app.post("/api/drafts/{draft_id}/findings/{finding_id}/ignore")
def ignore_finding(
    draft_id: int,
    finding_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Creator ignores finding. It remains on record for audit and rule analytics.
    """
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    finding.action_taken = "ignored"

    draft = db.query(Draft).filter(Draft.id == draft_id).first()
    if draft:
        draft.updated_at = datetime.utcnow()
        db.add(AuditLog(
            draft_id=draft.id,
            user_id=user.id,
            action="FINDING_IGNORED",
            details=f"{user.name} marked finding '{finding.matched_text}' as ignored ({finding.rule_source})."
        ))

    db.commit()
    return {"message": "Finding ignored"}


@app.post("/api/drafts/{draft_id}/findings/{finding_id}/edit")
def custom_edit_finding(
    draft_id: int,
    finding_id: int,
    payload: FindingEditRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Creator provides custom inline rewrite, creating a new version.
    """
    draft = db.query(Draft).filter(Draft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    current_version = db.query(DraftVersion).filter_by(draft_id=draft.id, version_num=draft.current_version_num).first()
    if not current_version:
        raise HTTPException(status_code=400, detail="Current version not found")

    old_content = current_version.content
    matched = finding.matched_text
    replacement = payload.custom_text.strip()

    pattern = re.compile(re.escape(matched), re.IGNORECASE)
    new_content = pattern.sub(replacement, old_content, count=1)

    finding.action_taken = "edited"

    new_version_num = draft.current_version_num + 1
    new_version = DraftVersion(
        draft_id=draft.id,
        version_num=new_version_num,
        content=new_content,
        change_summary=f"Custom edit: '{matched}' -> '{replacement}'",
        created_by_id=user.id,
    )
    db.add(new_version)
    db.flush()

    draft.current_version_num = new_version_num
    draft.updated_at = datetime.utcnow()

    # Re-evaluate
    rules = db.query(BrandRule).filter_by(is_active=True).all()
    facts = db.query(ApprovedFact).filter_by(is_active=True).all()
    new_findings = check_draft_rules(new_content, rules=rules, approved_facts=facts)

    for nf in new_findings:
        f_obj = Finding(
            draft_version_id=new_version.id,
            matched_text=nf["matched_text"],
            start_pos=nf.get("start_pos", -1),
            end_pos=nf.get("end_pos", -1),
            severity=nf.get("severity", "medium"),
            status=nf.get("status", "violation"),
            explanation=nf["explanation"],
            rule_source=nf["rule_source"],
            suggested_rewrite=nf["suggested_rewrite"],
            action_taken="pending",
            engine_source=nf.get("engine_source", "rule_engine"),
        )
        db.add(f_obj)

    score = calculate_compliance_score(new_findings)
    draft.compliance_score = score

    db.add(AuditLog(
        draft_id=draft.id,
        user_id=user.id,
        action="FINDING_EDITED",
        details=f"{user.name} applied custom edit '{replacement}' for '{matched}'. Version {new_version_num} created."
    ))

    db.commit()
    return {"message": "Custom edit saved as new version", "new_version_num": new_version_num, "score": score}


@app.post("/api/drafts/{draft_id}/update-text")
def update_draft_text(
    draft_id: int,
    payload: DraftUpdateText,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Manually edits the draft text and creates a new version.
    """
    draft = db.query(Draft).filter(Draft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    new_version_num = draft.current_version_num + 1
    new_version = DraftVersion(
        draft_id=draft.id,
        version_num=new_version_num,
        content=payload.content,
        change_summary=payload.change_summary or "Manual copy edit",
        created_by_id=user.id,
    )
    db.add(new_version)
    db.flush()

    draft.current_version_num = new_version_num
    draft.updated_at = datetime.utcnow()

    # Re-evaluate
    rules = db.query(BrandRule).filter_by(is_active=True).all()
    facts = db.query(ApprovedFact).filter_by(is_active=True).all()
    new_findings = check_draft_rules(payload.content, rules=rules, approved_facts=facts)

    for nf in new_findings:
        f_obj = Finding(
            draft_version_id=new_version.id,
            matched_text=nf["matched_text"],
            start_pos=nf.get("start_pos", -1),
            end_pos=nf.get("end_pos", -1),
            severity=nf.get("severity", "medium"),
            status=nf.get("status", "violation"),
            explanation=nf["explanation"],
            rule_source=nf["rule_source"],
            suggested_rewrite=nf["suggested_rewrite"],
            action_taken="pending",
            engine_source=nf.get("engine_source", "rule_engine"),
        )
        db.add(f_obj)

    score = calculate_compliance_score(new_findings)
    draft.compliance_score = score

    db.add(AuditLog(
        draft_id=draft.id,
        user_id=user.id,
        action="VERSION_CREATED",
        details=f"{user.name} updated draft content. Version {new_version_num} created ({score}% compliance)."
    ))

    db.commit()
    return {"message": "Text updated and version created", "new_version_num": new_version_num, "score": score}


@app.post("/api/drafts/{draft_id}/submit")
def submit_draft_for_review(
    draft_id: int,
    payload: SubmitReviewRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Creator submits draft for human review. Transitions status to IN_REVIEW.
    """
    draft = db.query(Draft).filter(Draft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    draft.status = "IN_REVIEW"
    draft.updated_at = datetime.utcnow()

    comment = ReviewComment(
        draft_id=draft.id,
        user_id=user.id,
        action="SUBMITTED",
        comment_text=payload.comment or "Submitted for brand governance sign-off."
    )
    db.add(comment)

    db.add(AuditLog(
        draft_id=draft.id,
        user_id=user.id,
        action="SUBMITTED_FOR_REVIEW",
        details=f"{user.name} submitted draft for reviewer sign-off (Version {draft.current_version_num}). Note: '{payload.comment}'"
    ))

    db.commit()
    return {"message": "Draft submitted for review", "status": draft.status}


@app.post("/api/drafts/{draft_id}/review-action")
def reviewer_decision(
    draft_id: int,
    payload: ReviewerActionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Reviewer actions: APPROVE, REQUEST_CHANGES, REJECT.
    AI never publishes anything automatically; strict human-in-the-loop governance.
    """
    draft = db.query(Draft).filter(Draft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    action_normalized = payload.action.upper()
    valid_actions = {
        "APPROVE": "APPROVED",
        "REQUEST_CHANGES": "CHANGES_REQUESTED",
        "REJECT": "REJECTED"
    }

    if action_normalized not in valid_actions:
        raise HTTPException(status_code=400, detail=f"Invalid action. Expected: {list(valid_actions.keys())}")

    new_status = valid_actions[action_normalized]
    draft.status = new_status
    draft.reviewer_id = user.id
    draft.updated_at = datetime.utcnow()

    # Log reviewer comment
    comment = ReviewComment(
        draft_id=draft.id,
        user_id=user.id,
        action=action_normalized,
        comment_text=payload.comment or f"Reviewer marked as {new_status}"
    )
    db.add(comment)

    db.add(AuditLog(
        draft_id=draft.id,
        user_id=user.id,
        action=new_status,
        details=f"Reviewer {user.name} set status to '{new_status}'. Comment: '{payload.comment}'"
    ))

    db.commit()
    return {"message": f"Draft status updated to {new_status}", "status": new_status}


# --- GUIDELINE LIBRARY (ADMIN) ENDPOINTS ---
@app.get("/api/guidelines/rules")
def list_brand_rules(db: Session = Depends(get_db)):
    rules = db.query(BrandRule).order_by(BrandRule.id.asc()).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "rule_type": r.rule_type,
            "pattern": r.pattern,
            "preferred_term": r.preferred_term,
            "severity": r.severity,
            "explanation": r.explanation,
            "disclaimer_text": r.disclaimer_text,
            "source_reference": r.source_reference,
            "version": r.version,
            "is_active": r.is_active,
            "updated_at": r.updated_at.isoformat()
        }
        for r in rules
    ]


@app.post("/api/guidelines/rules")
def create_brand_rule(
    payload: RuleCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    rule = BrandRule(
        name=payload.name,
        rule_type=payload.rule_type,
        pattern=payload.pattern,
        preferred_term=payload.preferred_term,
        severity=payload.severity,
        explanation=payload.explanation,
        disclaimer_text=payload.disclaimer_text,
        source_reference=payload.source_reference,
        version=payload.version,
        is_active=True
    )
    db.add(rule)
    db.flush()

    db.add(AuditLog(
        draft_id=None,
        user_id=user.id,
        action="RULE_CREATED",
        details=f"Brand rule '{rule.name}' ({rule.version}) created by {user.name}."
    ))

    db.commit()
    db.refresh(rule)
    return {"message": "Brand rule created", "id": rule.id}


@app.put("/api/guidelines/rules/{rule_id}")
def update_brand_rule(
    rule_id: int,
    payload: RuleCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    rule = db.query(BrandRule).filter(BrandRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    rule.name = payload.name
    rule.rule_type = payload.rule_type
    rule.pattern = payload.pattern
    rule.preferred_term = payload.preferred_term
    rule.severity = payload.severity
    rule.explanation = payload.explanation
    rule.disclaimer_text = payload.disclaimer_text
    rule.source_reference = payload.source_reference
    rule.version = payload.version
    rule.updated_at = datetime.utcnow()

    db.add(AuditLog(
        draft_id=None,
        user_id=user.id,
        action="RULE_UPDATED",
        details=f"Brand rule '{rule.name}' updated to {rule.version} by {user.name}."
    ))

    db.commit()
    return {"message": "Brand rule updated"}


@app.post("/api/guidelines/rules/{rule_id}/toggle")
def toggle_brand_rule(
    rule_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    rule = db.query(BrandRule).filter(BrandRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    rule.is_active = not rule.is_active
    rule.updated_at = datetime.utcnow()

    db.add(AuditLog(
        draft_id=None,
        user_id=user.id,
        action="RULE_TOGGLED",
        details=f"Brand rule '{rule.name}' set to {'Active' if rule.is_active else 'Inactive'} by {user.name}."
    ))

    db.commit()
    return {"message": "Rule toggled", "is_active": rule.is_active}


@app.get("/api/guidelines/facts")
def list_approved_facts(db: Session = Depends(get_db)):
    facts = db.query(ApprovedFact).order_by(ApprovedFact.id.asc()).all()
    return [
        {
            "id": f.id,
            "fact_text": f.fact_text,
            "claim_type": f.claim_type,
            "keywords": f.keywords,
            "source_reference": f.source_reference,
            "version": f.version,
            "is_active": f.is_active,
            "updated_at": f.updated_at.isoformat()
        }
        for f in facts
    ]


@app.post("/api/guidelines/facts")
def create_approved_fact(
    payload: FactCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    fact = ApprovedFact(
        fact_text=payload.fact_text,
        claim_type=payload.claim_type,
        keywords=payload.keywords,
        source_reference=payload.source_reference,
        version=payload.version,
        is_active=True
    )
    db.add(fact)
    db.flush()

    db.add(AuditLog(
        draft_id=None,
        user_id=user.id,
        action="FACT_CREATED",
        details=f"Approved fact '{fact.fact_text[:40]}...' created by {user.name}."
    ))

    db.commit()
    db.refresh(fact)
    return {"message": "Approved fact created", "id": fact.id}


# --- ANALYTICS ENDPOINT ---
@app.get("/api/analytics")
def get_governance_analytics(db: Session = Depends(get_db)):
    """
    Returns analytics:
    1. Recurring issue types (banned terms, guarantees, medical, disclaimers, superlatives, tone).
    2. Most-triggered rules.
    3. Rules that are often ignored (alerting to unclear/high-friction guidelines).
    4. Compliance summary & stats.
    """
    all_findings = db.query(Finding).all()

    issue_types_count = {
        "Medical / Cure Claims": 0,
        "Absolute Guarantees": 0,
        "Unverified Superlatives": 0,
        "Banned / Low-Value Words": 0,
        "Missing Disclaimers": 0,
        "Tone / Aggressive Hype": 0,
        "Competitor Disparagement": 0,
        "Other Brand Violations": 0
    }

    rule_trigger_counts = {}
    ignored_counts_by_rule = {}
    total_findings = len(all_findings)
    accepted_count = 0
    ignored_count = 0

    for f in all_findings:
        text_lower = f.matched_text.lower()
        src = f.rule_source or "General Guideline"

        rule_trigger_counts[src] = rule_trigger_counts.get(src, 0) + 1

        if f.action_taken == "accepted":
            accepted_count += 1
        elif f.action_taken == "ignored":
            ignored_count += 1
            ignored_counts_by_rule[src] = ignored_counts_by_rule.get(src, 0) + 1

        # Classify issue type
        if "cure" in text_lower or "pharma" in src.lower() or "heal" in text_lower:
            issue_types_count["Medical / Cure Claims"] += 1
        elif "guarantee" in text_lower:
            issue_types_count["Absolute Guarantees"] += 1
        elif "best" in text_lower or "#1" in text_lower or "superlative" in src.lower() or "asci" in src.lower():
            issue_types_count["Unverified Superlatives"] += 1
        elif "cheap" in text_lower or "dirt" in text_lower:
            issue_types_count["Banned / Low-Value Words"] += 1
        elif "% off" in text_lower or "discount" in text_lower or "disclaimer" in src.lower():
            issue_types_count["Missing Disclaimers"] += 1
        elif "tone" in src.lower() or "caps" in src.lower() or "!" in text_lower:
            issue_types_count["Tone / Aggressive Hype"] += 1
        elif "competitor" in text_lower or "rival" in text_lower:
            issue_types_count["Competitor Disparagement"] += 1
        else:
            issue_types_count["Other Brand Violations"] += 1

    # Most triggered rules
    sorted_triggered = sorted(
        [{"rule": k, "count": v} for k, v in rule_trigger_counts.items()],
        key=lambda x: x["count"],
        reverse=True
    )

    # Often ignored rules
    sorted_ignored = sorted(
        [
            {
                "rule": k,
                "ignored_count": v,
                "total_triggered": rule_trigger_counts.get(k, v),
                "ignore_rate": round((v / rule_trigger_counts.get(k, 1)) * 100, 1)
            }
            for k, v in ignored_counts_by_rule.items()
        ],
        key=lambda x: x["ignored_count"],
        reverse=True
    )

    # Draft counts
    total_drafts = db.query(Draft).count()
    approved_drafts = db.query(Draft).filter_by(status="APPROVED").count()
    in_review_drafts = db.query(Draft).filter_by(status="IN_REVIEW").count()
    draft_status = db.query(Draft).filter_by(status="DRAFT").count()

    avg_score = 0.0
    all_drafts = db.query(Draft).all()
    if all_drafts:
        avg_score = round(sum(d.compliance_score for d in all_drafts) / len(all_drafts), 1)

    return {
        "total_drafts": total_drafts,
        "approved_drafts": approved_drafts,
        "in_review_drafts": in_review_drafts,
        "draft_status": draft_status,
        "avg_compliance_score": avg_score,
        "total_findings": total_findings,
        "accepted_fixes": accepted_count,
        "ignored_findings": ignored_count,
        "issue_types": [{"name": k, "count": v} for k, v in issue_types_count.items() if v > 0],
        "most_triggered_rules": sorted_triggered[:6],
        "often_ignored_rules": sorted_ignored[:6]
    }


# --- AUDIT LOGS ENDPOINT ---
@app.get("/api/audit-logs")
def get_system_audit_logs(
    limit: int = 50,
    db: Session = Depends(get_db)
):
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit).all()
    return [
        {
            "id": l.id,
            "draft_id": l.draft_id,
            "draft_title": l.draft.title if l.draft else "System / Guideline",
            "user": l.user.name if l.user else "System",
            "action": l.action,
            "details": l.details,
            "timestamp": l.timestamp.isoformat()
        }
        for l in logs
    ]


# --- SERVE FRONTEND ---
@app.get("/", response_class=HTMLResponse)
def serve_index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()
