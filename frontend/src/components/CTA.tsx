'use client';

import Link from 'next/link';
import { ArrowRight } from 'lucide-react';

export function CTA() {
  return (
    <section className="relative isolate overflow-hidden bg-surface-elevated">
      <div className="px-6 py-24 sm:px-6 sm:py-32 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-semibold tracking-tight text-text-primary sm:text-4xl">
            Ready to get started?
          </h2>
          <p className="mx-auto mt-6 max-w-xl text-lg leading-8 text-text-secondary">
            Join thousands of teams using Tailord to enhance their productivity and creativity.
          </p>
          <div className="mt-10 flex items-center justify-center gap-x-6">
            <Link
              href="/signup"
              className="group inline-flex items-center gap-2 rounded-md bg-brand-primary px-6 py-3 text-sm font-semibold text-text-inverse shadow-sm hover:bg-brand-primary-hover transition-all hover:shadow-md"
            >
              Start using Tailord
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
            <Link
              href="/pricing"
              className="text-sm font-semibold leading-6 text-text-primary hover:text-brand-primary transition-colors"
            >
              View pricing <span aria-hidden="true">→</span>
            </Link>
          </div>
        </div>
      </div>
      
      {/* Background decoration */}
      <svg
        className="absolute inset-0 -z-10 h-full w-full stroke-border-subtle/50 mask-[radial-gradient(100%_100%_at_top_right,white,transparent)]"
        aria-hidden="true"
      >
        <defs>
          <pattern
            id="grid-pattern"
            width={200}
            height={200}
            x="50%"
            y={-1}
            patternUnits="userSpaceOnUse"
          >
            <path d="M.5 200V.5H200" fill="none" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" strokeWidth={0} fill="url(#grid-pattern)" />
      </svg>
    </section>
  );
}
