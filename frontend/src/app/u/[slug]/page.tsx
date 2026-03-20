import Link from 'next/link'
import type { ExtractedProfile } from '@/types'

interface PublicTailoringItem {
  title: string | null
  company: string | null
  public_slug: string
  letter_public: boolean
  posting_public: boolean
  created_at: string
}

interface PublicProfile {
  name: string | null
  avatar_url: string | null
  username_slug: string
  profile: ExtractedProfile | null
  tailorings: PublicTailoringItem[]
}

async function fetchPublicProfile(slug: string): Promise<PublicProfile | null> {
  const baseUrl = process.env.NEXTAUTH_URL ?? 'http://localhost:3000'
  try {
    const res = await fetch(`${baseUrl}/api/users/public/${slug}`, {
      cache: 'no-store',
    })
    if (!res.ok) return null
    return res.json()
  } catch {
    return null
  }
}

function TailoringCard({ tailoring }: { tailoring: PublicTailoringItem }) {
  const date = new Date(tailoring.created_at).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
  })
  const views = [
    tailoring.letter_public && 'Letter',
    tailoring.posting_public && 'Posting',
  ].filter(Boolean).join(' · ')

  return (
    <Link
      href={`/t/${tailoring.public_slug}`}
      className="block px-4 py-3.5 rounded-lg border border-border-subtle bg-surface-elevated hover:bg-surface-overlay transition-colors"
    >
      <p className="text-sm font-medium text-text-primary truncate">
        {tailoring.title ?? 'Untitled'}
      </p>
      <div className="flex items-center gap-2 mt-0.5">
        {tailoring.company && (
          <p className="text-xs text-text-secondary truncate">{tailoring.company}</p>
        )}
        {tailoring.company && <span className="text-text-tertiary text-xs">·</span>}
        <p className="text-xs text-text-tertiary flex-shrink-0">{date}</p>
        {views && <span className="text-text-tertiary text-xs">·</span>}
        {views && <p className="text-xs text-text-tertiary flex-shrink-0">{views}</p>}
      </div>
    </Link>
  )
}

function ExperienceSection({ profile }: { profile: ExtractedProfile }) {
  const hasWork = profile.work_experience?.length > 0
  const hasEducation = profile.education?.length > 0
  const hasSkills = (profile.skills?.technical?.length ?? 0) > 0 || (profile.certifications?.length ?? 0) > 0

  if (!hasWork && !hasEducation && !hasSkills && !profile.summary) {
    return (
      <p className="text-sm text-text-tertiary italic">No experience details available yet.</p>
    )
  }

  return (
    <div className="space-y-10">
      {/* Summary */}
      {profile.summary && (
        <div>
          <p className="text-sm text-text-secondary leading-relaxed">{profile.summary}</p>
        </div>
      )}

      {/* Work Experience */}
      {hasWork && (
        <div>
          <p className="text-xs font-medium text-text-tertiary uppercase tracking-wider mb-5">
            Work Experience
          </p>
          <div className="space-y-7">
            {profile.work_experience.map((job, i) => (
              <div key={i}>
                <div className="mb-1">
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
                </div>
                {job.bullets?.length > 0 && (
                  <ul className="mt-2 space-y-1">
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
        </div>
      )}

      {/* Education */}
      {hasEducation && (
        <div>
          <p className="text-xs font-medium text-text-tertiary uppercase tracking-wider mb-5">
            Education
          </p>
          <div className="space-y-4">
            {profile.education.map((edu, i) => (
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
        </div>
      )}

      {/* Skills & Certifications */}
      {hasSkills && (
        <div>
          <p className="text-xs font-medium text-text-tertiary uppercase tracking-wider mb-5">
            Skills
          </p>
          <div className="space-y-2">
            {profile.skills?.technical?.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {profile.skills.technical.map((s, i) => (
                  <span
                    key={i}
                    className="px-2.5 py-1 rounded-full text-xs bg-surface-elevated border border-border-subtle text-text-secondary"
                  >
                    {s}
                  </span>
                ))}
              </div>
            )}
            {profile.certifications?.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {profile.certifications.map((c, i) => (
                  <span
                    key={i}
                    className="px-2.5 py-1 rounded-full text-xs bg-brand-primary/8 border border-brand-primary/20 text-brand-primary"
                  >
                    {c}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default async function PublicProfilePage({
  params,
}: {
  params: Promise<{ slug: string }>
}) {
  const { slug } = await params
  const profile = await fetchPublicProfile(slug)

  if (!profile) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface-base">
        <div className="text-center space-y-3">
          <p className="text-xl font-semibold text-text-primary">Not found</p>
          <p className="text-text-secondary text-sm">This profile doesn&apos;t exist or isn&apos;t public yet.</p>
        </div>
      </div>
    )
  }

  const initials = profile.name
    ? profile.name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
    : '?'

  const hasTailorings = profile.tailorings.length > 0
  const navItems = [
    { href: '#experience', label: 'Experience' },
    ...(hasTailorings ? [{ href: '#tailorings', label: 'Tailorings' }] : []),
  ]

  return (
    <div className="min-h-screen bg-surface-base">
      <div className="mx-auto min-h-screen max-w-screen-lg px-6 lg:flex lg:gap-12 lg:px-16">

        {/* Left sidebar */}
        <aside className="flex flex-col pt-12 pb-8 lg:sticky lg:top-0 lg:h-screen lg:w-5/12 lg:flex-shrink-0 lg:justify-between lg:overflow-y-auto lg:py-20">

          <div>
            {/* Avatar */}
            <div className="mb-6">
              {profile.avatar_url ? (
                <img
                  src={profile.avatar_url}
                  alt={profile.name ?? ''}
                  className="h-16 w-16 rounded-full"
                />
              ) : (
                <div className="h-16 w-16 rounded-full bg-brand-primary/10 flex items-center justify-center">
                  <span className="text-xl font-medium text-brand-primary">{initials}</span>
                </div>
              )}
            </div>

            {/* Identity */}
            <h1 className="text-2xl font-semibold text-text-primary leading-tight">
              {profile.name ?? slug}
            </h1>
            {profile.profile?.headline && (
              <p className="text-sm text-text-secondary mt-2 leading-snug">
                {profile.profile.headline}
              </p>
            )}
            {profile.profile?.location && (
              <p className="text-xs text-text-tertiary mt-1.5">{profile.profile.location}</p>
            )}
            <p className="text-xs text-text-tertiary mt-1.5 break-all">
              tailord.app/u/{profile.username_slug}
            </p>

            {/* Contact links */}
            {(profile.profile?.linkedin || profile.profile?.email) && (
              <div className="mt-4 space-y-1">
                {profile.profile.linkedin && (
                  <a
                    href={profile.profile.linkedin.startsWith('http') ? profile.profile.linkedin : `https://${profile.profile.linkedin}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block text-xs text-text-link hover:underline truncate"
                  >
                    {profile.profile.linkedin.replace(/^https?:\/\//, '')}
                  </a>
                )}
                {profile.profile.email && (
                  <a
                    href={`mailto:${profile.profile.email}`}
                    className="block text-xs text-text-link hover:underline truncate"
                  >
                    {profile.profile.email}
                  </a>
                )}
              </div>
            )}

            {/* Section nav */}
            <nav className="mt-10 space-y-1 hidden lg:block">
              {navItems.map(item => (
                <a
                  key={item.href}
                  href={item.href}
                  className="block text-sm text-text-secondary hover:text-text-primary transition-colors py-1"
                >
                  {item.label}
                </a>
              ))}
            </nav>
          </div>

          <p className="text-xs text-text-tertiary hidden lg:block">
            <Link href="/" className="hover:text-text-secondary transition-colors">
              Tailord
            </Link>
          </p>
        </aside>

        {/* Right content */}
        <main className="pb-20 pt-2 lg:w-7/12 lg:py-20">

          {/* Experience */}
          <section id="experience" className="mb-14">
            <p className="text-xs font-medium text-text-tertiary uppercase tracking-wider mb-5">
              Experience
            </p>
            {profile.profile
              ? <ExperienceSection profile={profile.profile} />
              : <p className="text-sm text-text-tertiary italic">No experience details available yet.</p>
            }
          </section>

          {/* Tailorings */}
          {hasTailorings && (
            <section id="tailorings">
              <p className="text-xs font-medium text-text-tertiary uppercase tracking-wider mb-5">
                Tailorings
              </p>
              <div className="space-y-2">
                {profile.tailorings.map(t => (
                  <TailoringCard key={t.public_slug} tailoring={t} />
                ))}
              </div>
            </section>
          )}

        </main>
      </div>

      {/* Mobile footer */}
      <footer className="lg:hidden px-6 py-6 border-t border-border-subtle text-center">
        <p className="text-xs text-text-tertiary">
          <Link href="/" className="hover:text-text-secondary transition-colors">
            Tailord
          </Link>
        </p>
      </footer>
    </div>
  )
}
