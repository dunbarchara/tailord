export interface Tailoring {
  id: string
  title: string | null
  company: string | null
  job_url: string
  generated_output: string
  is_public: boolean
  public_slug: string | null
  created_at: string
}

export interface TailoringListItem {
  id: string
  title: string | null
  company: string | null
  job_url: string | null
  is_public: boolean
  public_slug: string | null
  created_at: string
}

export interface ExperienceInput {
  resumeText?: string
  githubRepos?: string[]
  manualEntries?: string[]
}

export interface UserProfile {
  id: string
  email: string
  name?: string
  experience?: ExperienceInput
  tailorings?: Tailoring[]
}

export interface JobAnalysis {
  title?: string
  company?: string
  requirements?: string[]
  responsibilities?: string[]
  skills?: string[]
}

export interface ApiError {
  message: string
  status: number
}

export type ExperienceStatus = 'pending' | 'processing' | 'ready' | 'error'

export interface GitHubRepo {
  name: string
  description: string | null
  language: string | null
  star_count: number
  pushed_at: string | null
}

export interface SourcedProfile {
  resume?: ExtractedProfile
  github?: { repos: GitHubRepo[] }
  user_input?: { text: string }
}

export interface ExtractedProfile {
  summary: string
  work_experience: Array<{
    title: string
    company: string
    duration: string
    bullets: string[]
  }>
  skills: {
    technical: string[]
    soft: string[]
  }
  education: Array<{
    degree: string
    institution: string
    year: string
  }>
  projects: Array<{
    name: string
    description: string
    technologies: string[]
  }>
  certifications: string[]
}

export interface ExperienceRecord {
  id: string
  filename: string | null
  status: ExperienceStatus
  extracted_profile: SourcedProfile | null
  error_message: string | null
  github_username: string | null
  github_repos: GitHubRepo[] | null
  user_input_text: string | null
  uploaded_at: string | null
  processed_at: string | null
}
