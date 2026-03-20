import Link from 'next/link'

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
          <p className="text-text-secondary text-sm">This profile doesn&apos;t exist or has no public tailorings yet.</p>
        </div>
      </div>
    )
  }

  const initials = profile.name
    ? profile.name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
    : '?'

  return (
    <div className="min-h-screen bg-surface-base">
      <div className="max-w-2xl mx-auto px-6 py-16">

        {/* Profile header */}
        <header className="flex items-center gap-4 mb-10 pb-8 border-b border-border-subtle">
          {profile.avatar_url ? (
            <img
              src={profile.avatar_url}
              alt={profile.name ?? ''}
              className="h-14 w-14 rounded-full flex-shrink-0"
            />
          ) : (
            <div className="h-14 w-14 rounded-full bg-brand-primary/10 flex items-center justify-center flex-shrink-0">
              <span className="text-lg font-medium text-brand-primary">{initials}</span>
            </div>
          )}
          <div>
            <h1 className="text-xl font-semibold text-text-primary">{profile.name ?? slug}</h1>
            <p className="text-sm text-text-tertiary mt-0.5">tailord.app/u/{profile.username_slug}</p>
          </div>
        </header>

        {/* Tailorings */}
        {profile.tailorings.length === 0 ? (
          <p className="text-sm text-text-tertiary italic">No public tailorings yet.</p>
        ) : (
          <div className="space-y-2">
            <p className="text-xs font-medium text-text-tertiary uppercase tracking-wider mb-3">
              Tailorings
            </p>
            {profile.tailorings.map(t => (
              <TailoringCard key={t.public_slug} tailoring={t} />
            ))}
          </div>
        )}

        {/* Footer */}
        <footer className="mt-16 pt-6 border-t border-border-subtle text-center">
          <p className="text-xs text-text-tertiary">
            Generated with{' '}
            <Link href="/" className="text-text-link hover:underline">
              Tailord
            </Link>
          </p>
        </footer>
      </div>
    </div>
  )
}
