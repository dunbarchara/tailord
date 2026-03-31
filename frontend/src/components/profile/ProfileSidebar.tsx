'use client';

import { useEffect, useState } from 'react';
import { FaLinkedin, FaGithub } from 'react-icons/fa';
import { ArrowUp } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface NavSection {
  id: string;
  label: string;
}

interface ProfileSidebarProps {
  name: string | null;
  slugFallback: string;
  title?: string | null;
  headline?: string | null;
  location?: string | null;
  linkedin?: string | null;
  githubUsername?: string | null;
  navSections: NavSection[];
  showScrollToTop?: boolean;
  bottomSlot?: React.ReactNode;
}

export function ProfileSidebar({
  name,
  slugFallback,
  title,
  headline,
  location,
  linkedin,
  githubUsername,
  navSections,
  showScrollToTop = false,
  bottomSlot,
}: ProfileSidebarProps) {
  const [activeId, setActiveId] = useState<string>(navSections[0]?.id ?? '');
  const [scrolled, setScrolled] = useState(false);

  // Track active section via scroll position
  useEffect(() => {
    if (navSections.length === 0) return;

    // A section becomes active when its top edge crosses this line
    // (60% down the viewport = activates shortly after entering from the bottom)
    // A section becomes active when its top edge crosses 60% down the viewport
    const THRESHOLD = 0.6;

    const getScrollState = (e?: Event) => {
      // For container scroll (dashboard), e.target is the Element that scrolled.
      // For window scroll (public profile), e.target is document — not an Element.
      if (e?.target instanceof Element) {
        const el = e.target;
        return { scrollTop: el.scrollTop, scrollMax: el.scrollHeight - el.clientHeight };
      }
      return {
        scrollTop: window.scrollY,
        scrollMax: document.documentElement.scrollHeight - window.innerHeight,
      };
    };

    const update = (e?: Event) => {
      // Ignore scroll events from containers that don't hold our section elements
      // (e.g. the sidebar tailorings list in the dashboard)
      if (e?.target instanceof Element) {
        const firstSection = document.getElementById(navSections[0]?.id ?? '');
        if (firstSection && !e.target.contains(firstSection)) return;
      }

      const { scrollTop, scrollMax } = getScrollState(e);

      if (scrollTop <= 0) {
        setActiveId(navSections[0].id);
        return;
      }
      if (scrollTop >= scrollMax - 1) {
        setActiveId(navSections[navSections.length - 1].id);
        return;
      }

      const line = window.innerHeight * THRESHOLD;
      let next = navSections[0].id;
      for (const { id } of navSections) {
        const el = document.getElementById(id);
        if (el && el.getBoundingClientRect().top <= line) next = id;
      }
      setActiveId(next);
    };

    update();
    // capture: true catches scroll from any container (window or dashboard main)
    document.addEventListener('scroll', update, { passive: true, capture: true });
    return () => document.removeEventListener('scroll', update, { capture: true });
  }, [navSections]);

  // Track scroll position for back-to-top button
  useEffect(() => {
    if (!showScrollToTop) return;

    const handler = () => setScrolled(window.scrollY > 300);
    window.addEventListener('scroll', handler, { passive: true });
    return () => window.removeEventListener('scroll', handler);
  }, [showScrollToTop]);

  const hasAnySocialLink = !!(linkedin || githubUsername);

  return (
    <aside className="flex flex-col pt-12 pb-8 lg:sticky lg:top-0 lg:h-screen lg:w-5/12 lg:flex-shrink-0 lg:overflow-y-auto lg:py-20">
      <div className="flex-1">
        <h1 className="text-2xl font-semibold text-text-primary leading-tight">
          {name ?? slugFallback}
        </h1>
        {title && (
          <p className="text-sm font-semibold text-text-primary mt-1">{title}</p>
        )}
        {headline && (
          <p className="text-sm text-text-secondary mt-1.5 leading-snug max-w-xs">{headline}</p>
        )}
        {location && (
          <p className="text-xs text-text-tertiary mt-1.5">{location}</p>
        )}

        {navSections.length > 0 && (
          <nav className="mt-10 space-y-1 hidden lg:block" aria-label="Page sections">
            {navSections.map(({ id, label }) => {
              const isActive = activeId === id;
              return (
                <a
                  key={id}
                  href={`#${id}`}
                  onClick={(e) => {
                    e.preventDefault();
                    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
                    setActiveId(id);
                  }}
                  className={cn(
                    'flex items-center gap-4 py-1.5 group transition-colors duration-200 w-fit',
                    isActive
                      ? 'text-text-primary'
                      : 'text-text-tertiary hover:text-text-secondary',
                  )}
                >
                  <span
                    className={cn(
                      'h-px bg-current transition-all duration-300 ease-in-out',
                      isActive ? 'w-14' : 'w-6 group-hover:w-10',
                    )}
                  />
                  <span className="text-xs font-medium tracking-widest uppercase">
                    {label}
                  </span>
                </a>
              );
            })}
          </nav>
        )}
      </div>

      {/* Bottom: social icons + back-to-top + optional slot */}
      <div className="mt-10 lg:mt-0 space-y-4">
        {hasAnySocialLink && (
          <div className="flex items-center gap-4">
            {linkedin && (
              <a
                href={linkedin.startsWith('http') ? linkedin : `https://${linkedin}`}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="LinkedIn"
                className="text-text-tertiary hover:text-text-primary transition-colors"
              >
                <FaLinkedin size={18} />
              </a>
            )}
            {githubUsername && (
              <a
                href={`https://github.com/${githubUsername}`}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="GitHub"
                className="text-text-tertiary hover:text-text-primary transition-colors"
              >
                <FaGithub size={18} />
              </a>
            )}
          </div>
        )}

        {showScrollToTop && (
          <button
            onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
            aria-label="Back to top"
            className={cn(
              'flex items-center gap-1.5 text-xs text-text-tertiary hover:text-text-primary transition-all duration-300',
              scrolled ? 'opacity-100' : 'opacity-0 pointer-events-none',
            )}
          >
            <ArrowUp className="h-3 w-3" />
            Back to top
          </button>
        )}

        {bottomSlot}
      </div>
    </aside>
  );
}
