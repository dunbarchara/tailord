"""
Pydantic schema for eval candidate profiles.

Profiles stored in tests/eval/profiles/*.json are validated against
EvalCandidateProfile at load time. If app/schemas/llm_outputs.py changes
(e.g. new fields on ExtractedProfile), loading will fail loudly rather than
silently producing wrong eval results.

EvalGitHubRepo mirrors the enriched repo shape written by github_enricher.py
into extracted_profile["github"]["repos"].
"""

from pydantic import BaseModel

from app.schemas.llm_outputs import ExtractedProfile, GitHubRepoEnrichment


class EvalGitHubRepo(GitHubRepoEnrichment):
    """Enriched GitHub repo as it appears in extracted_profile["github"]["repos"]."""

    name: str
    url: str
    description: str | None = None


class EvalGitHubProfile(BaseModel):
    repos: list[EvalGitHubRepo] = []


class EvalExtractedProfile(BaseModel):
    resume: ExtractedProfile = ExtractedProfile()
    github: EvalGitHubProfile | None = None
    user_input: dict | None = None


class EvalCandidateProfile(BaseModel):
    candidate_name: str
    pronouns: str | None = None
    description: str
    extracted_profile: EvalExtractedProfile

    def to_profile_dict(self) -> dict:
        """Return the dict form that _format_sourced_profile expects."""
        d: dict = {"resume": self.extracted_profile.resume.model_dump()}
        if self.extracted_profile.github is not None:
            d["github"] = {"repos": [r.model_dump() for r in self.extracted_profile.github.repos]}
        if self.extracted_profile.user_input is not None:
            d["user_input"] = self.extracted_profile.user_input
        return d
