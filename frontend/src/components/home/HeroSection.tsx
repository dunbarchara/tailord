import Link from 'next/link';
import { ArrowRight } from 'lucide-react';

export function HeroSection() {
  return (
    <section className="relative overflow-hidden px-6 pt-20 pb-16 lg:px-8 lg:pt-32 lg:pb-24">

      {/* Accent glow — radial gradient using the dynamic accent-subtle token */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-[32rem]"
        style={{
          background: 'radial-gradient(ellipse 80% 55% at 50% -5%, var(--color-hp-accent-subtle), transparent)',
        }}
      />

      <div className="relative mx-auto max-w-3xl text-center">
        <h1 className="text-5xl font-semibold tracking-tight text-text-primary sm:text-6xl lg:text-7xl leading-[1.1] animate-slide-up">
          You have the experience.
          <br />
          <span className="transition-colors duration-300" style={{ color: 'var(--color-hp-accent)' }}>
            We&apos;ll show you how to prove it.
          </span>
        </h1>

        <p
          className="mt-7 text-lg leading-8 text-text-secondary max-w-xl mx-auto animate-slide-up"
          style={{ animationDelay: '0.1s' }}
        >
          Tailord maps your background against any job description — requirement by requirement —
          and tells you where you&apos;re strong, where you&apos;re close, and how to make your case.
        </p>

        <div className="mt-10 animate-slide-up" style={{ animationDelay: '0.2s' }}>
          <Link
            href="/register"
            className="group btn-hp-accent inline-flex items-center gap-2 rounded-md px-7 py-3.5 text-sm font-semibold shadow-sm hover:shadow-md"
          >
            Start your first tailoring
            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </div>
      </div>
    </section>
  );
}
