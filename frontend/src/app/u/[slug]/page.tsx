import { cache } from 'react'
import Link from 'next/link'
import type { Metadata } from 'next'
import { AlignLeft, Briefcase, GraduationCap, Layers, FolderOpen, Mail, Phone } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { ProfileSidebar } from '@/components/profile/ProfileSidebar'
import type { ExtractedProfile } from '@/types'

interface PublicProfile {
  name: string | null
  avatar_url: string | null
  username_slug: string
  github_username: string | null
  profile: ExtractedProfile | null
}

// cache() deduplicates the fetch across generateMetadata + the page component
const fetchPublicProfile = cache(async (slug: string): Promise<PublicProfile | null> => {
  const baseUrl = process.env.NEXTAUTH_URL ?? 'http://localhost:3000'
  try {
    const res = await fetch(`${baseUrl}/api/users/public/${slug}`, { cache: 'no-store' })
    if (!res.ok) return null
    return res.json()
  } catch {
    return null
  }
})

// ─── Metadata ─────────────────────────────────────────────────────────────────

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>
}): Promise<Metadata> {
  const { slug } = await params
  const data = await fetchPublicProfile(slug)

  if (!data) {
    return { title: 'Profile Not Found — Tailord' }
  }

  const name = data.name ?? slug
  const description = data.profile?.headline
    ?? data.profile?.summary?.slice(0, 160)
    ?? `View ${name}'s professional profile on Tailord.`

  return {
    title: `${name} — Profile — Tailord`,
    description,
    openGraph: {
      title: `${name} — Profile — Tailord`,
      description,
      url: `https://tailord.app/u/${slug}`,
      type: 'profile',
      ...(data.avatar_url && { images: [{ url: data.avatar_url }] }),
    },
    twitter: {
      card: 'summary',
      title: `${name} — Tailord`,
      description,
      ...(data.avatar_url && { images: [data.avatar_url] }),
    },
  }
}

// ─── Section primitives ────────────────────────────────────────────────────────

function SectionHeader({ icon: Icon, label }: { icon: LucideIcon; label: string }) {
  return (
    <div className="flex items-center gap-3 mb-8">
      <Icon className="h-4 w-4 text-text-tertiary flex-shrink-0" />
      <span className="text-[10px] uppercase tracking-widest text-text-tertiary font-medium flex-shrink-0">{label}</span>
      <div className="flex-1 h-px bg-border-subtle" />
    </div>
  )
}

function SkillGroupLabel({ children }: { children: string }) {
  return (
    <p className="text-[10px] uppercase tracking-widest text-text-disabled mb-2">{children}</p>
  )
}

// ─── Section components ────────────────────────────────────────────────────────

function ExperienceSection({ jobs }: { jobs: ExtractedProfile['work_experience'] }) {
  return (
    <section id="experience" className="mb-16">
      <SectionHeader icon={Briefcase} label="Experience" />
      <div className="space-y-8">
        {jobs.map((job, i) => (
          <div key={i}>
            <p className="text-sm font-semibold text-text-primary">{job.title}</p>
            <p className="text-xs text-text-secondary mt-0.5">
              {job.company}
              {(job.location || job.duration) && (
                <span className="text-text-tertiary">
                  {job.location && ` · ${job.location}`}
                  {job.duration && ` · ${job.duration}`}
                </span>
              )}
            </p>
            {job.bullets?.length > 0 && (
              <ul className="mt-2.5 space-y-1.5">
                {job.bullets.map((b, j) => (
                  <li key={j} className="flex gap-2 text-xs text-text-secondary">
                    <span className="text-text-tertiary flex-shrink-0 mt-0.5">·</span>
                    <span>{b}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>
    </section>
  )
}

function EducationSection({ education }: { education: ExtractedProfile['education'] }) {
  return (
    <section id="education" className="mb-16">
      <SectionHeader icon={GraduationCap} label="Education" />
      <div className="space-y-5">
        {education.map((edu, i) => (
          <div key={i}>
            <p className="text-sm font-semibold text-text-primary">{edu.degree}</p>
            <p className="text-xs text-text-secondary mt-0.5">
              {edu.institution}
              {(edu.location || edu.year) && (
                <span className="text-text-tertiary">
                  {edu.location && `, ${edu.location}`}
                  {edu.year && ` · ${edu.year}`}
                </span>
              )}
            </p>
            {edu.distinction && (
              <p className="text-xs text-text-tertiary mt-0.5">{edu.distinction}</p>
            )}
          </div>
        ))}
      </div>
    </section>
  )
}

function SkillsSection({
  skills,
  certifications,
}: {
  skills: ExtractedProfile['skills']
  certifications: string[]
}) {
  return (
    <section id="skills" className="mb-16">
      <SectionHeader icon={Layers} label="Skills" />
      <div className="space-y-5">
        {skills.technical?.length > 0 && (
          <div>
            <SkillGroupLabel>Technical</SkillGroupLabel>
            <div className="flex flex-wrap gap-1.5">
              {skills.technical.map((s, i) => (
                <span
                  key={i}
                  className="px-2.5 py-1 rounded-full text-xs bg-surface-elevated border border-border-subtle text-text-secondary"
                >
                  {s}
                </span>
              ))}
            </div>
          </div>
        )}
        {skills.soft?.length > 0 && (
          <div>
            <SkillGroupLabel>Soft Skills</SkillGroupLabel>
            <div className="flex flex-wrap gap-1.5">
              {skills.soft.map((s, i) => (
                <span
                  key={i}
                  className="px-2.5 py-1 rounded-full text-xs bg-surface-sunken border border-border-subtle text-text-tertiary"
                >
                  {s}
                </span>
              ))}
            </div>
          </div>
        )}
        {certifications?.length > 0 && (
          <div>
            <SkillGroupLabel>Certifications</SkillGroupLabel>
            <div className="flex flex-wrap gap-1.5">
              {certifications.map((c, i) => (
                <span
                  key={i}
                  className="px-2.5 py-1 rounded-full text-xs bg-brand-primary/8 border border-brand-primary/20 text-brand-primary"
                >
                  {c}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  )
}

function ProjectsSection({ projects }: { projects: ExtractedProfile['projects'] }) {
  return (
    <section id="projects" className="mb-16">
      <SectionHeader icon={FolderOpen} label="Projects" />
      <div className="space-y-6">
        {projects.map((project, i) => (
          <div key={i}>
            <p className="text-sm font-semibold text-text-primary">{project.name}</p>
            {project.description && (
              <p className="text-xs text-text-secondary mt-1 leading-relaxed">{project.description}</p>
            )}
            {project.technologies?.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {project.technologies.map((t, j) => (
                  <span
                    key={j}
                    className="px-2 py-0.5 rounded text-xs bg-surface-sunken border border-border-subtle text-text-tertiary font-mono"
                  >
                    {t}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  )
}

function ContactSection({
  email,
  phone,
}: {
  email?: string | null
  phone?: string | null
}) {
  const items = [
    email && { label: email, href: `mailto:${email}`, icon: <Mail className="h-4 w-4 flex-shrink-0" /> },
    phone && { label: phone, href: `tel:${phone}`, icon: <Phone className="h-4 w-4 flex-shrink-0" /> },
  ].filter(Boolean) as Array<{ label: string; href: string; icon: React.ReactNode }>

  if (items.length === 0) return null

  return (
    <section id="contact" className="mb-16">
      <SectionHeader icon={Mail} label="Contact" />
      <div className="space-y-3">
        {items.map((item, i) => (
          <a
            key={i}
            href={item.href}
            className="flex items-center gap-3 text-sm text-text-secondary hover:text-text-primary transition-colors group"
          >
            <span className="text-text-tertiary group-hover:text-text-secondary transition-colors">
              {item.icon}
            </span>
            <span className="truncate">{item.label}</span>
          </a>
        ))}
      </div>
    </section>
  )
}

// ─── Page ──────────────────────────────────────────────────────────────────────

export default async function PublicProfilePage({
  params,
}: {
  params: Promise<{ slug: string }>
}) {
  const { slug } = await params
  const data = await fetchPublicProfile(slug)

  if (!data) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface-elevated">
        <div className="text-center space-y-3">
          <p className="text-xl font-semibold text-text-primary">Not found</p>
          <p className="text-text-secondary text-sm">This profile doesn&apos;t exist or isn&apos;t public yet.</p>
        </div>
      </div>
    )
  }

  const p = data.profile

  const hasSummary = !!p?.summary
  const hasExperience = (p?.work_experience?.length ?? 0) > 0
  const hasEducation = (p?.education?.length ?? 0) > 0
  const hasSkills =
    (p?.skills?.technical?.length ?? 0) > 0 ||
    (p?.skills?.soft?.length ?? 0) > 0 ||
    (p?.certifications?.length ?? 0) > 0
  const hasProjects = (p?.projects?.length ?? 0) > 0
  const hasContact = !!(p?.email || p?.phone)

  const navSections = [
    hasSummary && { id: 'about', label: 'About' },
    hasExperience && { id: 'experience', label: 'Experience' },
    hasEducation && { id: 'education', label: 'Education' },
    hasSkills && { id: 'skills', label: 'Skills' },
    hasProjects && { id: 'projects', label: 'Projects' },
    hasContact && { id: 'contact', label: 'Contact' },
  ].filter(Boolean) as Array<{ id: string; label: string }>

  return (
    <div className="bg-surface-elevated">
      <div className="mx-auto max-w-[1216px] px-6 lg:flex lg:gap-12 lg:px-16">
        <ProfileSidebar
          name={data.name}
          slugFallback={slug}
          title={p?.title}
          headline={p?.headline}
          location={p?.location}
          linkedin={p?.linkedin}
          githubUsername={data.github_username}
          navSections={navSections}
          showScrollToTop
        />

        <main className="pb-20 pt-2 lg:w-7/12 lg:py-20">
          {!p ? (
            <div className="mt-8">
              <p className="text-sm text-text-secondary">
                Experience details haven&apos;t been shared yet.
              </p>
            </div>
          ) : (
            <>
              {hasSummary && (
                <section id="about" className="mb-16">
                  <SectionHeader icon={AlignLeft} label="About" />
                  <p className="text-sm text-text-secondary leading-relaxed">{p.summary}</p>
                </section>
              )}
              {hasExperience && <ExperienceSection jobs={p.work_experience} />}
              {hasEducation && <EducationSection education={p.education} />}
              {hasSkills && <SkillsSection skills={p.skills} certifications={p.certifications} />}
              {hasProjects && <ProjectsSection projects={p.projects} />}
              {hasContact && <ContactSection email={p.email} phone={p.phone} />}
            </>
          )}
        </main>
      </div>

      <footer className="border-t border-border-subtle py-6 text-center">
        <p className="text-xs text-text-tertiary">
          Generated with{' '}
          <Link href="/" target="_blank" rel="noopener noreferrer" className="text-text-link hover:underline">
            Tailord
          </Link>
        </p>
      </footer>
    </div>
  )
}
