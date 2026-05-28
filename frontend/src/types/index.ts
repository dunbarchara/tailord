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
  partials: ProfileGap[]
  sourced_claim_count: number
  unsourced_claim_count: number
}

export interface Tailoring {
  id: string
  title: string | null
  company: string | null
  job_url: string | null
  generated_output: string | null
  letter_content?: LetterContent | null
  author_email?: string | null
  author_title?: string | null
  author_linkedin?: string | null
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
  gap_analysis_status?: 'pending' | 'complete' | 'error'
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

export interface ProfileCorrections {
  yoe_override?: number | null
  headline?: string | null
  title?: string | null
  summary?: string | null
  location?: string | null
  email?: string | null
  phone?: string | null
  linkedin?: string | null
}

export interface AdvocacyStatement {
  header: string
  body: string
  sources: string[]
}

export interface LetterContent {
  advocacy_statements: AdvocacyStatement[]
  closing: string
}

export interface SourcedProfile {
  resume?: ExtractedProfile
  github?: { repos: GitHubRepo[] }
  user_input?: { text: string }
  corrections?: ProfileCorrections
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
  experience_sources: string[] | null  // prefer over experience_source; may be null for old records
  source_label: string | null
  should_render?: boolean  // undefined = treat as true (pre-enrichment or legacy records)
  include_in_scoring: boolean  // false = excluded from re-scoring (user-marked or semantic rule)
  semantic_type: string | null  // null for pre-migration records
  evaluation_status: string | null  // 'scored' | 'skipped' | 'error' | null
  display_ready: boolean   // computed by backend: not a header, has a section, not noise
  scored_content: string | null  // content at time of last scoring; null = scored before this field existed
}

export interface ChunksResponse {
  enrichment_status: EnrichmentStatus
  chunks: JobChunk[]
}

export interface ExperienceClaim {
  id: string
  source_type: 'resume' | 'github' | 'user_input' | 'gap_response' | 'partial_response' | 'additional_experience'
  source_ref: string | null
  claim_type: 'work_experience' | 'skill' | 'project' | 'education' | 'other'
  content: string
  group_key: string | null
  date_range: string | null
  keywords: string[] | null
  provenance_metadata: Record<string, string> | null
  original_content: string | null
  status: 'pending' | 'active' | 'archived'
  position: number
  updated_at: string | null
}

export interface WorkExperienceGroup {
  group_key: string | null
  date_range: string | null
  chunks: ExperienceClaim[]
}

export interface ProjectGroup {
  group_key: string | null
  chunks: ExperienceClaim[]
}

export interface GitHubRepoGroup {
  group_key: string | null
  chunks: ExperienceClaim[]
}

export interface ResumeClaimsSection {
  work_experience: WorkExperienceGroup[]
  skills: ExperienceClaim[]
  projects: ProjectGroup[]
  education: ExperienceClaim[]
  other: ExperienceClaim[]
}

export interface GitHubClaimsSection {
  repos: GitHubRepoGroup[]
}

export interface ExperienceClaimsResponse {
  resume: ResumeClaimsSection | null
  github: GitHubClaimsSection | null
  user_input: ExperienceClaim[] | null
  gap_response: ExperienceClaim[] | null
  partial_response: ExperienceClaim[] | null
}

export interface ExperienceSourceStatus {
  id: string
  source_type: 'resume' | 'github'
  connection_status: 'connected' | 'disconnected' | 'error'
  sync_status: 'idle' | 'syncing' | 'error'
  config: { filename?: string | null; username?: string | null }
  error_message: string | null
  last_synced_at: string | null
}

export interface ExperienceRecord {
  id: string | null
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
  // New: per-source status (alongside legacy flat fields for backward compat)
  sources?: ExperienceSourceStatus[]
}
