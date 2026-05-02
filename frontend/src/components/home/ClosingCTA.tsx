import Link from 'next/link';
import { ArrowRight } from 'lucide-react';

export function ClosingCTA() {
  return (
    <section className="px-6 py-20 lg:px-8 lg:py-28 border-t border-border-subtle bg-surface-elevated">
      <div className="mx-auto max-w-2xl text-center">
        <h2
          className="text-2xl font-semibold text-text-primary tracking-tight sm:text-3xl mb-4"
          style={{ letterSpacing: '-0.02em' }}
        >
          Ready to see how you fit?
        </h2>
        <p className="text-text-secondary leading-relaxed mb-8 text-sm">
          Bring your resume and a job URL. Tailord does the rest.
        </p>
        <Link
          href="/demo/dashboard"
          className="group inline-flex items-center gap-2 rounded-full px-6 py-2.5 text-sm font-medium bg-text-primary text-surface-base hover:opacity-90 transition-opacity"
        >
          View demo dashboard
          <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
        </Link>
      </div>
    </section>
  );
}
