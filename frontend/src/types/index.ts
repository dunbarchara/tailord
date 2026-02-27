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
