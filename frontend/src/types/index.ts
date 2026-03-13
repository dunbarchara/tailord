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
  email?: string | null
  linkedin?: string | null
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
    distinction?: string | null
  }>
  projects: Array<{
    name: string
    description: string
    technologies: string[]
  }>
  certifications: string[]
}

export type EnrichmentStatus = 'pending' | 'processing' | 'complete' | 'error'

export interface JobChunk {
  id: string
  chunk_type: 'header' | 'bullet' | 'paragraph'
  content: string
  position: number
  section: string | null
  match_score: number | null  // -1=n/a, 0=gap, 1=partial, 2=strong, null=pending
  match_rationale: string | null
  experience_source: 'resume' | 'github' | 'user_input' | null
}

export interface ChunksResponse {
  enrichment_status: EnrichmentStatus
  chunks: JobChunk[]
}

export interface ExperienceRecord {
  id: string
  filename: string | null
  status: ExperienceStatus
  extracted_profile: SourcedProfile | null
  raw_resume_text: string | null
  error_message: string | null
  github_username: string | null
  github_repos: GitHubRepo[] | null
  user_input_text: string | null
  uploaded_at: string | null
  processed_at: string | null
}
