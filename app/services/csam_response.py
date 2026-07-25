"""
Handles the Tier 1 CSAM response path. Deliberately isolated from general
moderation/media code so this critical path has its own tight audit trail
and can't be accidentally weakened by unrelated refactors.

Two entry points call into this module:
  - media_pipeline.upload_media() -> _handle_flagged_upload() when the
    synchronous Thorn Safer / PhotoDNA scan hits on upload, before the
    content is ever stored normally or shown to anyone.
  - moderation router -> "remove_ban_and_report_ncmec" action, for cases
    that surface via user report rather than automated scan.

Actual reporting to NCMEC's CyberTipline requires registering as a
mandated/voluntary reporter and using their API or manual submission
portal — https://report.cybertip.org. The account owner/company needs
to complete that registration before this module can be wired to a
live endpoint. Until then, calls here should route to manual review by
a designated compliance contact, not silently no-op.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base
from app.config import settings


class EvidenceRecord(Base):
    """
    Secured, access-logged, NEVER auto-purged. Separate table from normal
    media/message storage specifically so it isn't touched by the
    disappearing-content lifecycle or general data-retention cleanup.
    """
    __tablename__ = "evidence_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_type = Column(String(32), nullable=False)  # "media_upload_scan" | "user_report"
    reference_id = Column(UUID(as_uuid=True), nullable=False)  # media.id or report.id

    uploader_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    storage_key = Column(String(256), nullable=True)  # kept in a restricted, non-public bucket

    scan_provider = Column(String(32), nullable=True)
    scan_result_summary = Column(Text, nullable=True)

    ncmec_report_status = Column(String(32), default="pending")  # pending | filed | not_applicable
    ncmec_report_id = Column(String(128), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    filed_at = Column(DateTime, nullable=True)


async def preserve_evidence_and_report(db, media, scan_result):
    """Called synchronously when an upload-time scan flags content."""
    evidence = EvidenceRecord(
        source_type="media_upload_scan",
        reference_id=media.id,
        uploader_user_id=None,  # resolved via media.message_id -> Message.sender_id upstream if needed
        storage_key=media.storage_key,
        scan_provider=media.scan_provider,
        scan_result_summary=str(scan_result),
    )
    db.add(evidence)
    db.commit()

    # Suspend the uploading account immediately, pending compliance review.
    # (Account resolution/ban handled by caller with access to message_id -> sender.)

    await _notify_compliance_contact(evidence)


async def file_ncmec_report(db, report):
    """Called from the moderation router's remove_ban_and_report_ncmec action."""
    evidence = EvidenceRecord(
        source_type="user_report",
        reference_id=report.id,
        uploader_user_id=report.reported_user_id,
        scan_result_summary=f"User report: {report.reason} - {report.detail_text or ''}",
    )
    db.add(evidence)
    db.commit()

    await _notify_compliance_contact(evidence)


async def _notify_compliance_contact(evidence: EvidenceRecord):
    """
    Until NCMEC API registration (https://report.cybertip.org) is
    complete, route directly to a human compliance contact rather than
    attempting automated submission. Replace with a real API call once
    registered as a reporting entity.
    """
    # TODO: replace with actual notification (email/Slack/PagerDuty) to
    # whoever is the designated compliance contact for LiberChat.
    print(f"[COMPLIANCE ALERT] Evidence record {evidence.id} requires NCMEC review.")
