import json
import logging
import uuid
from datetime import datetime, timezone

from app.clients.github_client import GitHubClient
from app.clients.llm_client import get_llm_client
from app.config import settings
from app.prompts.github_enrichment import SYSTEM, TEMPERATURE, USER_TEMPLATE

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
) -> dict:
    client = get_llm_client()
    user_prompt = USER_TEMPLATE.format(
        owner=owner,
        repo_name=repo_name,
        description=description or "No description provided.",
        languages=_format_languages(languages),
        topics=", ".join(topics) if topics else "None",
        readme=readme or "No README found.",
        manifests=_format_manifests(manifests),
    )
    response = client.chat.completions.create(
        model=settings.llm_model,
        temperature=TEMPERATURE,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
    )
    raw = (response.choices[0].message.content or "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning(
            "github_enricher: LLM returned non-JSON for %s/%s — using fallback", owner, repo_name
        )
        return {
            "readme_summary": (readme or "")[:200] or "Unable to summarize.",
            "detected_stack": list(languages.keys())[:5],
            "project_domain": "unknown",
            "confidence": "low",
        }


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
                        "readme_summary": llm_result.get("readme_summary"),
                        "detected_stack": llm_result.get("detected_stack", []),
                        "project_domain": llm_result.get("project_domain"),
                        "confidence": llm_result.get("confidence", "low"),
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
        db.commit()
        logger.info(
            "github_enricher: complete experience=%s repos=%d errors=%d requests=%d",
            experience_id,
            len(enriched),
            errors,
            github.request_count,
        )
    finally:
        db.close()
