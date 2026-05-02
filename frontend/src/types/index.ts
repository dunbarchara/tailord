export type GenerationStatus = 'pending' | 'generating' | 'ready' | 'error'

export interface ProfileGap {
  job_requirement: string
  question_for_candidate: string
  context: string
  source_searched: string
  chunk_id: string | null
}

export interface GapAnalysis {
  gaps: ProfileGap[]
  sourced_claim_count: number
  unsourced_claim_count: number
}

export interface Tailoring {
  id: string
  title: string | null
  company: string | null
  job_url: string
  generated_output: string | null
  generation_status: GenerationStatus
  generation_stage: string | null
  generation_error: string | null
  generation_started_at: string | null
  letter_public: boolean
  posting_public: boolean
  is_public: boolean
  public_slug: string | null
  author_username_slug: string | null
  notion_page_url: string | null
  notion_posting_page_url: string | null
  generation_duration_ms: number | null
  chunk_batch_count: number | null
  chunk_error_count: number | null
  gap_analysis?: GapAnalysis | null
  gap_analysis_status?: 'pending' | 'complete'
  created_at: string
}

export interface TailoringListItem {
  id: string
  title: string | null
  company: string | null
  job_url: string | null
  generation_status: GenerationStatus
  letter_public: boolean
  posting_public: boolean
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
  scanned_at: string | null
  scanning_started_at: string | null
}

export interface GitHubEnrichedRepo {
  name: string
  owner: string
  url: string
  description: string | null
  readme_summary: string | null
  detected_stack: string[]
  project_domain: string | null
  confidence: 'high' | 'medium' | 'low'
  language_breakdown: Record<string, number>
  topics: string[]
  stars: number
  last_pushed_at: string | null
}

export interface GitHubRepoDetails {
  enriched_at: string
  repos: GitHubEnrichedRepo[]
  request_count: number
  error_count: number
}

export interface SourcedProfile {
  resume?: ExtractedProfile
  github?: { repos: GitHubRepo[] }
  user_input?: { text: string }
}

export interface ExtractedProfile {
  email?: string | null
  phone?: string | null
  linkedin?: string | null
  location?: string | null
  title?: string | null
  headline?: string | null
  summary: string
  work_experience: Array<{
    title: string
    company: string
    location?: string | null
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
    location?: string | null
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
  advocacy_blurb: string | null
  experience_source: 'resume' | 'github' | 'user_input' | null  // legacy, kept for backward compat
  experience_sources: string[] | null  // new: prefer over experience_source; may be null for old records
  source_label: string | null
  should_render?: boolean  // undefined = treat as true (pre-enrichment or legacy records)
  display_ready: boolean   // computed by backend: not a header, has a section, not noise
}

export interface ChunksResponse {
  enrichment_status: EnrichmentStatus
  chunks: JobChunk[]
}

export interface ExperienceChunk {
  id: string
  source_type: 'resume' | 'github' | 'user_input' | 'gap_response' | 'additional_experience'
  source_ref: string | null
  claim_type: 'work_experience' | 'skill' | 'project' | 'education' | 'other'
  content: string
  group_key: string | null
  date_range: string | null
  technologies: string[] | null
  chunk_metadata: Record<string, string> | null
  position: number
  updated_at: string | null
}

export interface WorkExperienceGroup {
  group_key: string | null
  date_range: string | null
  chunks: ExperienceChunk[]
}

export interface ProjectGroup {
  group_key: string | null
  chunks: ExperienceChunk[]
}

export interface GitHubRepoGroup {
  group_key: string | null
  chunks: ExperienceChunk[]
}

export interface ResumeChunksSection {
  work_experience: WorkExperienceGroup[]
  skills: ExperienceChunk[]
  projects: ProjectGroup[]
  education: ExperienceChunk[]
  other: ExperienceChunk[]
}

export interface GitHubChunksSection {
  repos: GitHubRepoGroup[]
}

export interface ExperienceChunksResponse {
  resume: ResumeChunksSection | null
  github: GitHubChunksSection | null
  user_input: ExperienceChunk[] | null
  gap_response: ExperienceChunk[] | null
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
  github_repo_details: GitHubRepoDetails | null
  user_input_text: string | null
  uploaded_at: string | null
  processed_at: string | null
  last_process_requested_at: string | null
}
