import Link from 'next/link';
import { ArrowRight } from 'lucide-react';

export function HeroSection({ isSignedIn }: { isSignedIn: boolean }) {
  return (
    <section className="relative overflow-hidden px-6 pt-20 pb-16 lg:px-8 lg:pt-28 lg:pb-24 bg-surface-elevated dark:bg-surface-base">
      <div className="relative mx-auto max-w-[43rem] text-center">
        {/* Section label */}
        <p
          className="inline-flex items-center gap-1.5 font-mono text-xs font-medium uppercase tracking-[0.6px] mb-6 animate-fade-in"
          style={{ color: 'var(--color-brand-accent)' }}
        >
          <span
            className="inline-block h-1.5 w-1.5 rounded-full"
            style={{ backgroundColor: 'var(--color-brand-accent)' }}
          />
          Job matching, done right
        </p>

        <h1
          className="font-semibold text-text-primary leading-[1.1] text-balance animate-slide-up"
          style={{ fontSize: 'clamp(2.25rem, 5vw, 3.5rem)', letterSpacing: '-0.02em' }}
        >
          You have the experience.
          <br />
          <span style={{ color: 'var(--color-brand-accent)' }}>
            We&apos;ll show you how to prove it.
          </span>
        </h1>

        <p
          className="mt-6 text-base leading-[1.65] text-text-secondary max-w-lg mx-auto animate-slide-up"
          style={{ animationDelay: '0.08s' }}
        >
          Tailord maps your background against any job description — requirement by requirement —
          and tells you where you&apos;re strong, where you&apos;re close, and how to make your case.
        </p>

        <div className="mt-8 flex items-center justify-center animate-slide-up" style={{ animationDelay: '0.16s' }}>
          <Link
            href={isSignedIn ? '/dashboard/tailorings/new' : '/register'}
            className="group inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium bg-text-primary text-surface-base hover:opacity-90 transition-opacity"
          >
            {isSignedIn ? 'Create a tailoring' : 'Start your first tailoring'}
            <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </div>
      </div>
    </section>
  );
}
