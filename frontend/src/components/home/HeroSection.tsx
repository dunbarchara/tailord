'use client';

import Link from 'next/link';
import { ArrowRight } from 'lucide-react';

export function HeroSection() {
  return (
    <section className="relative overflow-hidden px-6 pt-20 pb-16 lg:px-8 lg:pt-28 lg:pb-20">
      <div className="mx-auto max-w-3xl text-center">
        <h1 className="text-4xl font-semibold tracking-tight text-text-primary sm:text-5xl lg:text-6xl animate-slide-up leading-tight">
          You have the experience.
          <br />
          <span className="text-brand-primary">We'll show you how to prove it.</span>
        </h1>

        <p className="mt-6 text-lg leading-8 text-text-secondary max-w-2xl mx-auto animate-slide-up" style={{ animationDelay: '0.1s' }}>
          Tailord maps your background against any job description — requirement by requirement —
          and tells you where you're strong, where you're close, and how to make your case.
        </p>

        <div className="mt-10 animate-slide-up" style={{ animationDelay: '0.2s' }}>
          <Link
            href="/register"
            className="group inline-flex items-center gap-2 rounded-md bg-brand-primary px-7 py-3.5 text-sm font-semibold text-text-inverse shadow-sm hover:bg-brand-primary-hover transition-all hover:shadow-md"
          >
            Start your first tailoring
            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </div>
      </div>
    </section>
  );
}
