'use client';

import Link from 'next/link';
import { Lock, Settings, ChevronDown, AlignLeft } from 'lucide-react';
import { cn } from '@/lib/utils';
import { ProfileSidebar } from '@/components/profile/ProfileSidebar';
import {
  SectionHeader, ExperienceSection, EducationSection, SkillsSection, ProjectsSection, ContactSection,
} from '@/components/profile/ProfileSections';
import { getMockUser, getMockExperience } from '@/mock/loader';

const textBtnCls =
  'inline-flex items-center gap-1.5 h-8 px-2.5 rounded-[10px] ' +
  'bg-surface-elevated border border-border-default text-text-secondary ' +
  'text-sm font-normal tracking-[-0.1px] ' +
  'transition-colors disabled:opacity-40 disabled:cursor-not-allowed';

export default function DemoProfilePage() {
  const user = getMockUser();
  const experience = getMockExperience();
  const resume = experience.extracted_profile?.resume;
  const githubUsername = experience.github_app_login ?? null;

  const displayName = [user.preferred_first_name, user.preferred_last_name].filter(Boolean).join(' ') || user.name || null;

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

      {/* Toolbar */}
      <div className="shrink-0 grid grid-cols-[1fr_auto_1fr] items-center h-12 px-6 gap-2 bg-surface-elevated border-b border-border-subtle">
        <div className="flex items-center gap-1.5 min-w-0">
          <span className="text-sm font-medium text-text-primary tracking-[-0.1px]">My Profile</span>
        </div>
        <div />
        <div className="flex items-center justify-end gap-1">
          <button type="button" disabled className={textBtnCls}>
            <Lock className="h-3.5 w-3.5" />
            <span>Profile</span>
            <ChevronDown className="h-3.5 w-3.5 text-text-disabled" />
          </button>
        </div>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto min-h-0">
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

            <main className="pb-20 pt-2 lg:w-7/12 lg:py-20">
              {!resume ? (
                <p className="text-sm text-text-secondary mt-8">No profile content available.</p>
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
                    <SkillsSection skills={resume.skills} certifications={resume.certifications ?? []} />
                  )}
                  {hasProjects && <ProjectsSection projects={resume.projects} />}
                  {(resume.email || resume.phone) && (
                    <ContactSection email={resume.email} phone={resume.phone} />
                  )}
                </>
              )}

              {/* Sign-up prompt */}
              <div className={cn(
                'mt-4 px-4 py-3 rounded-xl border border-border-subtle bg-surface-base',
                'flex items-center justify-between gap-4',
              )}>
                <div>
                  <p className="text-sm font-medium text-text-primary">Want to share your own profile?</p>
                  <p className="text-xs text-text-tertiary mt-0.5">Sign in to set up a public profile page.</p>
                </div>
                <Link
                  href="/login"
                  className="shrink-0 inline-flex items-center gap-1.5 h-8 px-3 rounded-[10px] text-sm font-normal bg-zinc-950 dark:bg-white text-white dark:text-zinc-950 hover:opacity-90 transition-opacity"
                >
                  <Settings className="h-3.5 w-3.5" strokeWidth={1.8} />
                  Get started
                </Link>
              </div>
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
      </div>
    </div>
  );
}
