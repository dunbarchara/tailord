'use client';

import Link from 'next/link';
import {
  Lock, Settings, ChevronDown,
  AlignLeft, Briefcase, GraduationCap, Layers, FolderOpen, Mail,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { ProfileSidebar } from '@/components/profile/ProfileSidebar';
import { getMockUser, getMockExperience } from '@/mock/loader';

const textBtnCls =
  'inline-flex items-center gap-1.5 h-8 px-2.5 rounded-[10px] ' +
  'bg-surface-elevated border border-border-default text-text-secondary ' +
  'text-sm font-normal tracking-[-0.1px] ' +
  'transition-colors disabled:opacity-40 disabled:cursor-not-allowed';

function SectionHeader({ icon: Icon, label }: { icon: LucideIcon; label: string }) {
  return (
    <div className="flex items-center gap-3 mb-8">
      <Icon className="h-4 w-4 text-text-tertiary flex-shrink-0" />
      <span className="text-[10px] uppercase tracking-widest text-text-tertiary font-medium flex-shrink-0">{label}</span>
      <div className="flex-1 h-px bg-border-subtle" />
    </div>
  );
}

export default function DemoProfilePage() {
  const user = getMockUser();
  const experience = getMockExperience();
  const resume = experience.extracted_profile?.resume;
  const githubUsername = experience.github_username;

  const displayName = [user.preferred_first_name, user.preferred_last_name].filter(Boolean).join(' ') || user.name || null;

  const hasSummary = !!resume?.summary;
  const hasExperience = (resume?.work_experience?.length ?? 0) > 0;
  const hasEducation = (resume?.education?.length ?? 0) > 0;
  const hasSkills = (resume?.skills?.technical?.length ?? 0) > 0 || (resume?.skills?.soft?.length ?? 0) > 0;
  const hasProjects = (resume?.projects?.length ?? 0) > 0;

  const navSections = [
    hasSummary && { id: 'about', label: 'About' },
    hasExperience && { id: 'experience', label: 'Experience' },
    hasEducation && { id: 'education', label: 'Education' },
    hasSkills && { id: 'skills', label: 'Skills' },
    hasProjects && { id: 'projects', label: 'Projects' },
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

                  {hasExperience && (
                    <section id="experience" className="mb-16">
                      <SectionHeader icon={Briefcase} label="Experience" />
                      <div className="space-y-8">
                        {resume.work_experience.map((job, i) => (
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
                  )}

                  {hasEducation && (
                    <section id="education" className="mb-16">
                      <SectionHeader icon={GraduationCap} label="Education" />
                      <div className="space-y-5">
                        {resume.education.map((edu, i) => (
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
                          </div>
                        ))}
                      </div>
                    </section>
                  )}

                  {hasSkills && (
                    <section id="skills" className="mb-16">
                      <SectionHeader icon={Layers} label="Skills" />
                      <div className="space-y-5">
                        {resume.skills.technical?.length > 0 && (
                          <div>
                            <p className="text-[10px] uppercase tracking-widest text-text-disabled mb-2">Technical</p>
                            <div className="flex flex-wrap gap-1.5">
                              {resume.skills.technical.map((s, i) => (
                                <span key={i} className="px-2.5 py-1 rounded-full text-xs bg-surface-elevated border border-border-subtle text-text-secondary">
                                  {s}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                        {resume.skills.soft?.length > 0 && (
                          <div>
                            <p className="text-[10px] uppercase tracking-widest text-text-disabled mb-2">Soft Skills</p>
                            <div className="flex flex-wrap gap-1.5">
                              {resume.skills.soft.map((s, i) => (
                                <span key={i} className="px-2.5 py-1 rounded-full text-xs bg-surface-sunken border border-border-subtle text-text-tertiary">
                                  {s}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </section>
                  )}

                  {hasProjects && (
                    <section id="projects" className="mb-16">
                      <SectionHeader icon={FolderOpen} label="Projects" />
                      <div className="space-y-6">
                        {resume.projects.map((project, i) => (
                          <div key={i}>
                            <p className="text-sm font-semibold text-text-primary">{project.name}</p>
                            {project.description && (
                              <p className="text-xs text-text-secondary mt-1 leading-relaxed">{project.description}</p>
                            )}
                            {project.technologies?.length > 0 && (
                              <div className="flex flex-wrap gap-1.5 mt-2">
                                {project.technologies.map((t, j) => (
                                  <span key={j} className="px-2 py-0.5 rounded text-xs bg-surface-sunken border border-border-subtle text-text-tertiary font-mono">
                                    {t}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </section>
                  )}

                  {resume.email && (
                    <section id="contact" className="mb-16">
                      <SectionHeader icon={Mail} label="Contact" />
                      <a href={`mailto:${resume.email}`} className="flex items-center gap-3 text-sm text-text-secondary hover:text-text-primary transition-colors group">
                        <Mail className="h-4 w-4 text-text-tertiary flex-shrink-0" />
                        <span>{resume.email}</span>
                      </a>
                    </section>
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
