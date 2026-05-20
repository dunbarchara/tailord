from pydantic import BaseModel, model_validator


class TailoringCreate(BaseModel):
    job_url: str | None = None
    company: str | None = None
    title: str | None = None
    description: str | None = None
    skip_validation: bool = False

    @model_validator(mode="after")
    def check_input(self) -> "TailoringCreate":
        has_url = bool(self.job_url and self.job_url.strip())
        has_manual = bool(self.company and self.title and self.description)
        if not has_url and not has_manual:
            raise ValueError("Provide a job URL or fill in company, title, and description.")
        return self
