export interface Tailoring {
  id: string
  jobTitle: string
  company: string
  jobDescription: string
  generatedOutput: string
  createdAt: string
  updatedAt: string
}

export interface Experience {
  resumeText?: string
  githubRepos?: string[]
  manualEntries?: string[]
}

export interface UserProfile {
  id: string
  email: string
  name?: string
  experience?: Experience
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

export type ResumeStatus = 'pending' | 'processing' | 'ready' | 'error'

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

export interface ResumeRecord {
  id: string
  filename: string
  status: ResumeStatus
  extracted_profile: ExtractedProfile | null
  error_message: string | null
  uploaded_at: string | null
  processed_at: string | null
}
