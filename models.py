from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    role = Column(String(20), nullable=False)  # CREATOR, REVIEWER, ADMIN
    avatar_color = Column(String(10), default="#4F46E5")

    drafts = relationship("Draft", back_populates="creator", foreign_keys="Draft.creator_id")
    comments = relationship("ReviewComment", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")


class BrandRule(Base):
    __tablename__ = "brand_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    rule_type = Column(String(50), nullable=False)  # BANNED_TERM, PREFERRED_TERM, REGEX_CLAIM, MANDATORY_DISCLAIMER, TONE
    pattern = Column(String(255), nullable=False)
    preferred_term = Column(String(255), nullable=True)
    severity = Column(String(20), default="medium")  # high, medium, low
    explanation = Column(Text, nullable=False)
    disclaimer_text = Column(Text, nullable=True)
    source_reference = Column(String(255), nullable=False)
    version = Column(String(20), default="v1.0")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    findings = relationship("Finding", back_populates="rule")


class ApprovedFact(Base):
    __tablename__ = "approved_facts"

    id = Column(Integer, primary_key=True, index=True)
    fact_text = Column(Text, nullable=False)
    claim_type = Column(String(50), default="SUPERLATIVE")  # SUPERLATIVE, METRIC, CERTIFICATION, GUARANTEE
    keywords = Column(String(255), nullable=False)  # comma separated keywords/claims
    source_reference = Column(Text, nullable=False)
    version = Column(String(20), default="v1.0")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Draft(Base):
    __tablename__ = "drafts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    status = Column(String(30), default="DRAFT")  # DRAFT, IN_REVIEW, CHANGES_REQUESTED, APPROVED, REJECTED
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    current_version_num = Column(Integer, default=1)
    compliance_score = Column(Float, default=100.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    creator = relationship("User", foreign_keys=[creator_id], back_populates="drafts")
    reviewer = relationship("User", foreign_keys=[reviewer_id])
    versions = relationship("DraftVersion", back_populates="draft", cascade="all, delete-orphan", order_by="DraftVersion.version_num.asc()")
    comments = relationship("ReviewComment", back_populates="draft", cascade="all, delete-orphan", order_by="ReviewComment.created_at.asc()")
    audit_logs = relationship("AuditLog", back_populates="draft", cascade="all, delete-orphan", order_by="AuditLog.timestamp.desc()")


class DraftVersion(Base):
    __tablename__ = "draft_versions"

    id = Column(Integer, primary_key=True, index=True)
    draft_id = Column(Integer, ForeignKey("drafts.id"), nullable=False)
    version_num = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    change_summary = Column(String(255), default="Draft updated")
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    draft = relationship("Draft", back_populates="versions")
    created_by = relationship("User")
    findings = relationship("Finding", back_populates="version", cascade="all, delete-orphan")


class Finding(Base):
    __tablename__ = "findings"

    id = Column(Integer, primary_key=True, index=True)
    draft_version_id = Column(Integer, ForeignKey("draft_versions.id"), nullable=False)
    rule_id = Column(Integer, ForeignKey("brand_rules.id"), nullable=True)
    matched_text = Column(String(255), nullable=False)
    start_pos = Column(Integer, default=-1)
    end_pos = Column(Integer, default=-1)
    severity = Column(String(20), default="medium")  # high, medium, low
    status = Column(String(30), default="violation")  # violation, needs verification
    explanation = Column(Text, nullable=False)
    rule_source = Column(String(255), nullable=False)
    suggested_rewrite = Column(Text, nullable=False)
    action_taken = Column(String(20), default="pending")  # pending, accepted, ignored, edited
    engine_source = Column(String(30), default="rule_engine")  # rule_engine, gemini_llm

    version = relationship("DraftVersion", back_populates="findings")
    rule = relationship("BrandRule", back_populates="findings")


class ReviewComment(Base):
    __tablename__ = "review_comments"

    id = Column(Integer, primary_key=True, index=True)
    draft_id = Column(Integer, ForeignKey("drafts.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(50), default="COMMENT")  # COMMENT, SUBMITTED, CHANGES_REQUESTED, APPROVED, REJECTED
    comment_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    draft = relationship("Draft", back_populates="comments")
    user = relationship("User", back_populates="comments")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    draft_id = Column(Integer, ForeignKey("drafts.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(50), nullable=False)
    details = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    draft = relationship("Draft", back_populates="audit_logs")
    user = relationship("User", back_populates="audit_logs")
