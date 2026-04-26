import logging
import uuid
from datetime import datetime, timezone

from app.clients.github_client import GitHubClient
from app.clients.llm_client import get_llm_client
from app.config import settings
from app.core.llm_utils import llm_parse_with_retry
from app.prompts.github_enrichment import SYSTEM, TEMPERATURE, USER_TEMPLATE
from app.schemas.llm_outputs import GitHubRepoEnrichment

logger = logging.getLogger(__name__)


def _format_languages(languages: dict[str, int]) -> str:
    if not languages:
        return "None detected"
    total = sum(languages.values()) or 1
    parts = [
        f"{lang} ({count / total:.0%})"
        for lang, count in sorted(languages.items(), key=lambda x: -x[1])
    ]
    return ", ".join(parts[:6])


def _format_manifests(manifests: dict[str, str]) -> str:
    if not manifests:
        return "None found"
    return "\n\n".join(f"--- {name} ---\n{content}" for name, content in manifests.items())


def _llm_enrich_repo(
    owner: str,
    repo_name: str,
    description: str | None,
    languages: dict[str, int],
    topics: list[str],
    readme: str | None,
    manifests: dict[str, str],
) -> GitHubRepoEnrichment:
    user_prompt = USER_TEMPLATE.format(
        owner=owner,
        repo_name=repo_name,
        description=description or "No description provided.",
        languages=_format_languages(languages),
        topics=", ".join(topics) if topics else "None",
        readme=readme or "No README found.",
        manifests=_format_manifests(manifests),
    )
    return llm_parse_with_retry(
        get_llm_client(),
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        response_model=GitHubRepoEnrichment,
        temperature=TEMPERATURE,
    )


def enrich_github_repos(
    github_username: str,
    experience_id: uuid.UUID,
    repo_names: list[str] | None = None,
) -> None:
    """
    Background task: fetches authenticated repo data for each of the user's repos,
    runs per-repo LLM enrichment, and stores structured results in
    experience.github_repo_details.

    Creates its own DB session — safe to call after the request context closes.
    Silently skips enrichment if GitHub App credentials are not configured.
    """
    if not settings.github_app_id:
        logger.warning("github_enricher: GITHUB_APP_ID not set — skipping enrichment")
        return

    from app.clients.database import SessionLocal
    from app.models.database import Experience

    db = SessionLocal()
    try:
        github = GitHubClient()
        repos = github.get_user_repos(github_username)
        if repo_names is not None:
            name_filter = set(repo_names)
            repos = [r for r in repos if r["name"] in name_filter]
        enriched = []
        errors = 0

        for repo in repos:
            name = repo["name"]
            try:
                languages = github.get_languages(github_username, name)
                topics = github.get_topics(github_username, name)
                readme = github.get_readme(github_username, name)
                manifests = github.get_manifests(github_username, name)
                workflow = github.get_first_workflow(github_username, name)
                if workflow:
                    manifests[".github/workflows"] = workflow

                llm_result = _llm_enrich_repo(
                    owner=github_username,
                    repo_name=name,
                    description=repo.get("description"),
                    languages=languages,
                    topics=topics,
                    readme=readme,
                    manifests=manifests,
                )

                total_bytes = sum(languages.values()) or 1
                enriched.append(
                    {
                        "name": name,
                        "owner": github_username,
                        "url": f"https://github.com/{github_username}/{name}",
                        "description": repo.get("description"),
                        "readme_summary": llm_result.readme_summary,
                        "detected_stack": llm_result.detected_stack,
                        "project_domain": llm_result.project_domain,
                        "confidence": llm_result.confidence,
                        "language_breakdown": {
                            lang: round(count / total_bytes, 3) for lang, count in languages.items()
                        },
                        "topics": topics,
                        "stars": repo.get("stargazers_count", 0),
                        "last_pushed_at": repo.get("pushed_at"),
                    }
                )
                logger.debug("github_enricher: enriched %s/%s", github_username, name)
            except Exception:
                logger.exception("github_enricher: failed to enrich %s/%s", github_username, name)
                errors += 1

        experience = db.query(Experience).filter(Experience.id == experience_id).first()
        if not experience:
            logger.error("github_enricher: experience %s not found after enrichment", experience_id)
            return

        experience.github_repo_details = {
            "enriched_at": datetime.now(timezone.utc).isoformat(),
            "repos": enriched,
            "request_count": github.request_count,
            "error_count": errors,
        }

        # Merge enriched fields into extracted_profile["github"]["repos"] so the
        # tailoring generator and requirement matcher see the enriched data.
        enriched_by_name = {r["name"]: r for r in enriched}
        existing_profile = experience.extracted_profile or {}
        github_profile = existing_profile.get("github") or {}
        merged_repos = []
        for repo in github_profile.get("repos") or []:
            name = repo.get("name")
            if name and name in enriched_by_name:
                merged_repos.append({**repo, **enriched_by_name[name]})
            else:
                merged_repos.append(repo)
        experience.extracted_profile = {
            **existing_profile,
            "github": {**github_profile, "repos": merged_repos},
        }

        db.commit()

        from app.services.experience_chunker import chunk_github_repo

        total_chunks = 0
        for repo_data in enriched:
            total_chunks += chunk_github_repo(db, experience, repo_data["name"])
        db.commit()

        logger.info(
            "github_enricher: complete experience=%s repos=%d errors=%d requests=%d chunks=%d",
            experience_id,
            len(enriched),
            errors,
            github.request_count,
            total_chunks,
        )
    finally:
        db.close()
