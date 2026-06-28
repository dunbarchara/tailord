'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  Globe, Lock, Settings, Copy, CheckCircle2, ChevronDown, AlignLeft,
} from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Switch } from '@/components/ui/switch';
import { ProfileSidebar } from '@/components/profile/ProfileSidebar';
import {
  SectionHeader, ExperienceSection, EducationSection, SkillsSection, ProjectsSection, ContactSection,
} from '@/components/profile/ProfileSections';
import type { ExtractedProfile } from '@/types';

interface UserData {
  name: string | null;
  avatar_url: string | null;
  username_slug: string | null;
  profile_public: boolean;
  preferred_first_name: string | null;
  preferred_last_name: string | null;
}

interface ExperienceData {
  extracted_profile: { resume?: ExtractedProfile } | null;
  github_app_login?: string | null;
}

// ─── Page ──────────────────────────────────────────────────────────────────────

/* ─── Shared button styles (mirrors TailoringDetail) ─────────────────────── */

const textBtnCls =
  'inline-flex items-center gap-1.5 h-8 px-2.5 rounded-[10px] ' +
  'bg-surface-elevated border border-border-default text-text-secondary ' +
  'text-sm font-normal tracking-[-0.1px] ' +
  'hover:bg-surface-overlay hover:border-border-strong hover:text-text-primary ' +
  'transition-colors disabled:opacity-40 disabled:cursor-not-allowed';

/* ─── Page ──────────────────────────────────────────────────────────────── */

export default function ProfilePage() {
  const [user, setUser] = useState<UserData | null>(null);
  const [resume, setResume] = useState<ExtractedProfile | null>(null);
  const [githubUsername, setGithubUsername] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Profile popover state
  const [profileOpen, setProfileOpen] = useState(false);
  const [profilePublic, setProfilePublic] = useState(false);
  const [togglingVisibility, setTogglingVisibility] = useState(false);
  const [copiedUrl, setCopiedUrl] = useState(false);
  const [origin, setOrigin] = useState('https://tailord.app');

  useEffect(() => {
    setOrigin(window.location.origin);
  }, []);

  useEffect(() => {
    Promise.all([
      fetch('/api/users').then((r) => r.json()),
      fetch('/api/experience').then((r) => r.json()),
    ])
      .then(([userData, experienceData]: [UserData, ExperienceData]) => {
        setUser(userData);
        setProfilePublic(userData.profile_public ?? false);
        setResume(experienceData?.extracted_profile?.resume ?? null);
        setGithubUsername(experienceData?.github_app_login ?? null);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function handleToggleVisibility(value: boolean) {
    setTogglingVisibility(true);
    try {
      const res = await fetch('/api/users', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile_public: value }),
      });
      if (!res.ok) throw new Error();
      setProfilePublic(value);
      setUser((prev) => prev ? { ...prev, profile_public: value } : prev);
    } catch {
      toast.error('Failed to update visibility.');
    } finally {
      setTogglingVisibility(false);
    }
  }

  function handleCopyProfileUrl() {
    if (!user?.username_slug) return;
    navigator.clipboard.writeText(`${origin}/u/${user.username_slug}`);
    setCopiedUrl(true);
    setTimeout(() => setCopiedUrl(false), 2000);
  }

  if (loading) {
    return (
      <div className="h-full flex flex-col bg-surface-elevated">
        <div className="shrink-0 grid grid-cols-[1fr_auto_1fr] items-center h-12 px-6 gap-2 bg-surface-elevated border-b border-border-subtle">
          <span className="text-sm font-medium text-text-primary tracking-[-0.1px]">My Profile</span>
          <div />
          <div className="flex justify-end">
            <div className={cn(textBtnCls, 'opacity-40 pointer-events-none')}>
              <Lock className="h-3.5 w-3.5" />
              <span>Profile</span>
              <ChevronDown className="h-3.5 w-3.5 text-text-disabled" />
            </div>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="h-5 w-5 rounded-full border-2 border-brand-primary border-t-transparent animate-spin" />
        </div>
      </div>
    );
  }

  const displayName =
    [user?.preferred_first_name, user?.preferred_last_name].filter(Boolean).join(' ') ||
    user?.name ||
    null;

  const hasSummary = !!resume?.summary;
  const hasExperience = (resume?.work_experience?.length ?? 0) > 0;
  const hasEducation = (resume?.education?.length ?? 0) > 0;
  const hasSkills =
    (resume?.skills?.technical?.length ?? 0) > 0 ||
    (resume?.skills?.soft?.length ?? 0) > 0 ||
    (resume?.certifications?.length ?? 0) > 0;
  const hasProjects = (resume?.projects?.length ?? 0) > 0;
  const hasContact = !!(resume?.email || resume?.phone);

  const navSections = [
    hasSummary && { id: 'about', label: 'About' },
    hasExperience && { id: 'experience', label: 'Experience' },
    hasEducation && { id: 'education', label: 'Education' },
    hasSkills && { id: 'skills', label: 'Skills' },
    hasProjects && { id: 'projects', label: 'Projects' },
    hasContact && { id: 'contact', label: 'Contact' },
  ].filter(Boolean) as Array<{ id: string; label: string }>;

  return (
    <div className="h-full flex flex-col bg-surface-elevated">

      {/* ── Toolbar ──────────────────────────────────────────────────────── */}
      <div className="shrink-0 grid grid-cols-[1fr_auto_1fr] items-center h-12 px-6 gap-2 bg-surface-elevated border-b border-border-subtle">

        {/* Left: title */}
        <div className="flex items-center gap-1.5 min-w-0">
          <span className="text-sm font-medium text-text-primary tracking-[-0.1px]">
            My Profile
          </span>
        </div>

        {/* Center: empty */}
        <div />

        {/* Right: profile popover */}
        <div className="flex items-center justify-end gap-1">
          <Popover open={profileOpen} onOpenChange={setProfileOpen}>
            <PopoverTrigger asChild>
              <button type="button" className={textBtnCls}>
                {profilePublic
                  ? <Globe className="h-3.5 w-3.5 text-brand-accent" />
                  : <Lock className="h-3.5 w-3.5" />}
                <span>Profile</span>
                <ChevronDown className="h-3.5 w-3.5 text-text-disabled" />
              </button>
            </PopoverTrigger>

            <PopoverContent align="end" sideOffset={6} className="w-80 p-0 rounded-2xl border-border-subtle shadow-lg overflow-hidden">

              {/* Header */}
              <div className="px-4 pt-4 pb-3">
                <p className="text-sm font-medium text-text-primary tracking-[-0.1px]">
                  {profilePublic ? 'Profile is public' : 'Share your profile'}
                </p>
                <p className="text-sm text-text-secondary mt-0.5">
                  Anyone with the link can view your profile — no sign-in required.
                </p>
              </div>

              {/* Profile URL (when public + slug exists) */}
              {profilePublic && user?.username_slug && (
                <div className="border-t border-border-subtle px-4 py-3">
                  <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-surface-base border border-border-subtle">
                    <Globe className="h-3.5 w-3.5 text-text-tertiary shrink-0" />
                    <a
                      href={`/u/${user.username_slug}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex-1 text-xs text-text-link hover:underline truncate"
                    >
                      {origin}/u/{user.username_slug}
                    </a>
                    <button
                      type="button"
                      onClick={handleCopyProfileUrl}
                      className="shrink-0 text-text-tertiary hover:text-text-primary transition-colors"
                      title="Copy link"
                    >
                      {copiedUrl
                        ? <CheckCircle2 className="h-3.5 w-3.5 text-success" />
                        : <Copy className="h-3.5 w-3.5" />}
                    </button>
                  </div>
                </div>
              )}

              {/* Visibility toggle */}
              <div className="border-t border-border-subtle px-4 py-3">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium text-text-primary">Public profile</p>
                    <p className="text-xs text-text-tertiary mt-0.5">
                      {user?.username_slug
                        ? 'Anyone with the link can view'
                        : 'Set a username in Settings to share'}
                    </p>
                  </div>
                  <Switch
                    checked={profilePublic}
                    onCheckedChange={handleToggleVisibility}
                    disabled={togglingVisibility || !user?.username_slug}
                  />
                </div>
              </div>

              {/* Settings link */}
              <div className="border-t border-border-subtle px-4 py-3">
                <Link
                  href="/dashboard/settings"
                  onClick={() => setProfileOpen(false)}
                  className={cn(textBtnCls, 'w-full justify-center')}
                >
                  <Settings className="h-3.5 w-3.5" strokeWidth={1.8} />
                  Profile settings
                </Link>
              </div>

            </PopoverContent>
          </Popover>
        </div>

      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto min-h-0">
      {/* Profile preview */}
      <div className="flex-1">
        <div className="mx-auto max-w-[1216px] px-6 lg:flex lg:gap-12 lg:px-16">
          <ProfileSidebar
            name={displayName}
            slugFallback="Your Name"
            title={resume?.title}
            headline={resume?.headline}
            location={resume?.location}
            linkedin={resume?.linkedin}
            githubUsername={githubUsername}
            navSections={navSections}
          />

          {/* Content */}
          <main className="pb-20 pt-2 lg:w-7/12 lg:py-20">
            {!resume ? (
              <div className="mt-8 space-y-2">
                <p className="text-sm text-text-secondary">Your profile has no content yet.</p>
                <p className="text-xs text-text-tertiary">
                  Upload your resume in{' '}
                  <Link href="/dashboard/experience" className="text-text-link hover:underline">
                    My Experience
                  </Link>{' '}
                  to populate your profile.
                </p>
              </div>
            ) : (
              <>
                {hasSummary && (
                  <section id="about" className="mb-16">
                    <SectionHeader icon={AlignLeft} label="About" />
                    <p className="text-sm text-text-secondary leading-relaxed">{resume.summary}</p>
                  </section>
                )}
                {hasExperience && <ExperienceSection jobs={resume.work_experience} />}
                {hasEducation && <EducationSection education={resume.education} />}
                {hasSkills && (
                  <SkillsSection skills={resume.skills} certifications={resume.certifications} />
                )}
                {hasProjects && <ProjectsSection projects={resume.projects} />}
                {hasContact && <ContactSection email={resume.email} phone={resume.phone} />}
              </>
            )}
          </main>
        </div>

        {/* Footer */}
        <footer className="border-t border-border-subtle py-6 text-center">
          <p className="text-xs text-text-tertiary">
            Generated with{' '}
            <Link href="/" target="_blank" rel="noopener noreferrer" className="text-text-link hover:underline">
              Tailord
            </Link>
          </p>
        </footer>
      </div>
      </div>{/* end scrollable content */}
    </div>
  );
}
