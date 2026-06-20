"""
github_pr_processor.py — background task for processing github_pr CaptureSignals.

Triggered by the webhook handler after a PR is merged. Fetches PR commits, calls
the LLM to extract experience claims, deduplicates semantically, and inserts pending
ExperienceClaim rows for user review in the PendingReviewPanel.
"""

import uuid
from datetime import datetime, timezone

import structlog

logger = structlog.get_logger(__name__)


def process_github_pr_signal(signal_id: uuid.UUID) -> None:
    """Background task: extract ExperienceClaims from a merged PR signal.

    Creates its own database session. Marks the signal failed on any unhandled error
    so the record is never silently lost.
    """
    from sqlalchemy import func

    from app.clients.database import SessionLocal
    from app.clients.embedding_client import embed_text
    from app.clients.github_client import get_github_client
    from app.clients.llm_client import get_llm_client
    from app.config import settings
    from app.core.llm_utils import llm_parse_with_retry
    from app.models.database import CaptureSignal, ExperienceClaim, ExperienceSource
    from app.prompts.github_pr_extraction import (
        PROMPT_NAME,
        SYSTEM,
        TEMPERATURE,
        USER_TEMPLATE,
        PRClaimExtractionResult,
    )
    from app.services.claim_dedup import is_duplicate_claim
    from app.services.experience_chunker import _get_or_create_group

    db = SessionLocal()
    try:
        _process(
            signal_id=signal_id,
            db=db,
            embed_text=embed_text,
            get_github_client=get_github_client,
            get_llm_client=get_llm_client,
            llm_parse_with_retry=llm_parse_with_retry,
            settings=settings,
            SYSTEM=SYSTEM,
            USER_TEMPLATE=USER_TEMPLATE,
            TEMPERATURE=TEMPERATURE,
            PROMPT_NAME=PROMPT_NAME,
            PRClaimExtractionResult=PRClaimExtractionResult,
            CaptureSignal=CaptureSignal,
            ExperienceClaim=ExperienceClaim,
            ExperienceSource=ExperienceSource,
            is_duplicate_claim=is_duplicate_claim,
            _get_or_create_group=_get_or_create_group,
            func=func,
        )
    except Exception:
        logger.exception("github_pr_processor: unhandled error", signal_id=str(signal_id))
        try:
            from app.models.database import CaptureSignal as CS

            sig = db.query(CS).filter(CS.id == signal_id).first()
            if sig:
                sig.status = "failed"
                sig.skip_reason = "unhandled_error"
                db.commit()
        except Exception:
            logger.exception("github_pr_processor: failed to mark signal failed")
    finally:
        db.close()


def _process(
    *,
    signal_id,
    db,
    embed_text,
    get_github_client,
    get_llm_client,
    llm_parse_with_retry,
    settings,
    SYSTEM,
    USER_TEMPLATE,
    TEMPERATURE,
    PROMPT_NAME,
    PRClaimExtractionResult,
    CaptureSignal,
    ExperienceClaim,
    ExperienceSource,
    is_duplicate_claim,
    _get_or_create_group,
    func,
):
    now = datetime.now(timezone.utc)

    # 1. Load signal
    signal = db.query(CaptureSignal).filter(CaptureSignal.id == signal_id).first()
    if not signal:
        logger.warning("github_pr_processor: signal not found", signal_id=str(signal_id))
        return

    raw = signal.raw_data
    pr = raw.get("pull_request", {})

    # 2. Extract PR fields
    pr_number = pr.get("number")
    pr_title = pr.get("title", "")
    pr_body = (pr.get("body") or "")[:2000]
    pr_url = signal.source_ref
    repo_info = raw.get("repository", {})
    repo_name = repo_info.get("name", "")
    repo_owner = repo_info.get("owner", {}).get("login", "")
    labels = [lbl.get("name", "") for lbl in pr.get("labels", [])]
    installation_id = str(raw.get("installation", {}).get("id", ""))

    # 3. Find ExperienceSource for this installation
    source = (
        db.query(ExperienceSource)
        .filter(
            ExperienceSource.source_type == "github",
            ExperienceSource.config["installation_id"].astext == installation_id,
        )
        .first()
    )
    if not source:
        logger.warning(
            "github_pr_processor: no ExperienceSource for installation",
            installation_id=installation_id,
            signal_id=str(signal_id),
        )
        signal.status = "failed"
        signal.skip_reason = "no_matched_source"
        db.commit()
        return

    github_username = (source.config or {}).get("username", "")

    # 4. Fetch PR commits via per-installation token
    try:
        commits = get_github_client().get_pr_commits(
            repo_owner, repo_name, pr_number, installation_id
        )
    except Exception:
        logger.exception(
            "github_pr_processor: failed to fetch PR commits",
            signal_id=str(signal_id),
            pr_number=pr_number,
        )
        signal.status = "failed"
        signal.skip_reason = "commit_fetch_error"
        db.commit()
        return

    # 5. Filter to user's commits — match by login or author name
    user_commits = []
    for c in commits:
        commit_author_login = (c.get("author") or {}).get("login", "").lower()
        commit_author_name = c.get("commit", {}).get("author", {}).get("name", "").lower()
        if github_username.lower() in (commit_author_login, commit_author_name):
            # Subject line only (first line of message)
            message = c.get("commit", {}).get("message", "")
            subject = message.splitlines()[0] if message else ""
            user_commits.append(subject)

    # 6. Call LLM
    messages = [
        {"role": "system", "content": SYSTEM},
        {
            "role": "user",
            "content": USER_TEMPLATE.format(
                repo=f"{repo_owner}/{repo_name}",
                pr_number=pr_number,
                pr_title=pr_title,
                pr_body=pr_body or "(no description)",
                commit_messages="\n".join(f"- {m}" for m in user_commits) or "(none)",
                labels=", ".join(labels) or "(none)",
            ),
        },
    ]

    result = llm_parse_with_retry(
        get_llm_client(),
        settings.llm_model,
        messages,
        PRClaimExtractionResult,
        TEMPERATURE,
        prompt_name=PROMPT_NAME,
    )

    # 7. Handle skip
    if result.skip_reason:
        logger.info(
            "github_pr_processor: signal skipped by LLM",
            signal_id=str(signal_id),
            skip_reason=result.skip_reason,
        )
        signal.status = "skipped"
        signal.skip_reason = result.skip_reason
        signal.processed_at = now
        db.commit()
        return

    # 8. Get base position for new claims
    max_pos = (
        db.query(func.max(ExperienceClaim.position))
        .filter(ExperienceClaim.user_id == signal.user_id)
        .scalar()
        or 0
    )

    # 9. Get/create repository group for these claims
    group = _get_or_create_group(
        user_id=signal.user_id,
        group_type="repository",
        name=repo_name,
        source_type="github",
        source_ref=repo_name,
        db=db,
    )

    # 10. Insert claims
    inserted = 0
    for draft in result.claims:
        # Semantic dedup
        try:
            if is_duplicate_claim(signal.user_id, draft.content, db):
                logger.info(
                    "github_pr_processor: duplicate claim skipped",
                    signal_id=str(signal_id),
                    content_preview=draft.content[:60],
                )
                continue
        except Exception:
            logger.warning(
                "github_pr_processor: dedup check failed, skipping claim",
                signal_id=str(signal_id),
            )
            continue

        # Embed
        embedding = None
        try:
            embedding = embed_text(draft.content, embed_context="claim_dedup")
        except Exception:
            logger.warning(
                "github_pr_processor: embed_text failed, inserting without embedding",
                signal_id=str(signal_id),
            )

        max_pos += 1
        claim = ExperienceClaim(
            user_id=signal.user_id,
            group_id=group.id,
            source_type="github_pr",
            source_ref=repo_name,
            claim_type=draft.claim_type,
            content=draft.content,
            keywords=draft.technologies,
            confidence=draft.confidence,
            status="pending",
            provenance_metadata={
                "url": pr_url,
                "label": f"PR #{pr_number} — {pr_title}",
            },
            position=max_pos,
            embedding=embedding,
            embedding_model=settings.embedding_model if embedding is not None else None,
        )
        db.add(claim)
        inserted += 1

    signal.status = "processed"
    signal.processed_at = now
    db.commit()

    logger.info(
        "github_pr_processor: signal processed",
        signal_id=str(signal_id),
        claims_inserted=inserted,
        claims_skipped=len(result.claims) - inserted,
    )
