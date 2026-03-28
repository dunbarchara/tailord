import Link from 'next/link';
import { ArrowRight } from 'lucide-react';

export function ClosingCTA() {
  return (
    <section className="px-6 py-20 lg:px-8 lg:py-28 bg-surface-elevated border-t border-border-subtle">
      <div className="mx-auto max-w-2xl text-center">
        <h2 className="text-2xl font-semibold text-text-primary sm:text-3xl mb-4">
          Ready to see how you fit?
        </h2>
        <p className="text-text-secondary leading-relaxed mb-8">
          Bring your resume and a job URL. Tailord does the rest.
        </p>
        <Link
          href="/register"
          className="group inline-flex items-center gap-2 rounded-md bg-brand-primary px-7 py-3.5 text-sm font-semibold text-text-inverse shadow-sm hover:bg-brand-primary-hover transition-all hover:shadow-md"
        >
          Start your first tailoring
          <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
        </Link>
      </div>
    </section>
  );
}
