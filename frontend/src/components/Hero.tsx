'use client';

import Link from 'next/link';
import { ArrowRight } from 'lucide-react';

export function Hero() {
  return (
    <section className="relative overflow-hidden px-6 pt-14 lg:px-8 lg:pt-20">
      <div className="mx-auto max-w-4xl text-center pb-24 lg:pb-32">
        {/* Main heading */}
        <h1 className="text-5xl font-semibold tracking-tight text-text-primary sm:text-6xl lg:text-7xl animate-slide-up">
          Talk with Tailord,
          <br />
          an AI assistant
          <br />
          from Anthropic
        </h1>

        {/* Subheading */}
        <p className="mt-6 text-lg leading-8 text-text-secondary max-w-2xl mx-auto animate-slide-up" style={{ animationDelay: '0.1s' }}>
          Tailord is a next generation AI assistant built for work and trained to be safe, accurate, and secure.
        </p>

        {/* CTA buttons */}
        <div className="mt-10 flex items-center justify-center gap-x-4 animate-slide-up" style={{ animationDelay: '0.2s' }}>
          <Link
            href="/chat"
            className="group inline-flex items-center gap-2 rounded-md bg-brand-primary px-6 py-3 text-sm font-semibold text-text-inverse shadow-sm hover:bg-brand-primary-hover transition-all hover:shadow-md"
          >
            Try Tailord
            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
          </Link>
          <Link
            href="/contact-sales"
            className="inline-flex items-center rounded-md bg-surface-elevated px-6 py-3 text-sm font-semibold text-text-primary shadow-sm ring-1 ring-inset ring-border-default hover:bg-surface-overlay transition-colors"
          >
            Contact sales
          </Link>
        </div>

        {/* Trust indicators */}
        <div className="mt-16 flex flex-col items-center gap-4 animate-fade-in" style={{ animationDelay: '0.3s' }}>
          <p className="text-sm text-text-tertiary">Trusted by teams at</p>
          <div className="flex flex-wrap items-center justify-center gap-x-8 gap-y-4 opacity-60">
            {/* Placeholder for company logos */}
            {['Company 1', 'Company 2', 'Company 3', 'Company 4'].map((company, i) => (
              <div
                key={company}
                className="h-8 w-24 bg-text-tertiary/20 rounded"
                style={{ animationDelay: `${0.4 + i * 0.1}s` }}
              />
            ))}
          </div>
        </div>
      </div>

      {/* Feature preview image/graphic area */}
      <div className="mx-auto max-w-6xl pb-24 lg:pb-32 animate-fade-in" style={{ animationDelay: '0.4s' }}>
        <div className="relative rounded-xl bg-surface-elevated shadow-2xl ring-1 ring-border-subtle overflow-hidden">
          {/* Mock chat interface */}
          <div className="bg-surface-base p-8 lg:p-12">
            {/* Chat header */}
            <div className="flex items-center justify-between mb-8 pb-4 border-b border-border-subtle">
              <div className="flex items-center gap-3">
                <div className="h-8 w-8 rounded-full bg-brand-primary flex items-center justify-center">
                  <span className="text-text-inverse text-sm font-semibold">T</span>
                </div>
                <div>
                  <div className="text-sm font-medium text-text-primary">Tailord</div>
                  <div className="text-xs text-text-tertiary">Online</div>
                </div>
              </div>
            </div>

            {/* Sample messages */}
            <div className="space-y-6">
              {/* User message */}
              <div className="flex justify-end">
                <div className="max-w-[80%] rounded-lg bg-surface-elevated px-4 py-3 border border-border-subtle">
                  <p className="text-sm text-text-primary">
                    Can you help me understand how machine learning works?
                  </p>
                </div>
              </div>

              {/* Tailord response */}
              <div className="flex justify-start">
                <div className="max-w-[85%] rounded-lg bg-surface-overlay px-4 py-3">
                  <p className="text-sm text-text-primary leading-relaxed">
                    I'd be happy to help explain machine learning! At its core, machine learning is about enabling computers to learn from data and improve their performance on tasks without being explicitly programmed for each scenario.
                  </p>
                  <p className="text-sm text-text-primary leading-relaxed mt-3">
                    Think of it like teaching a child to recognize animals...
                  </p>
                </div>
              </div>
            </div>

            {/* Input area */}
            <div className="mt-8 pt-6 border-t border-border-subtle">
              <div className="flex items-center gap-3 p-3 rounded-lg bg-surface-elevated border border-border-default">
                <input
                  type="text"
                  placeholder="Talk with Tailord..."
                  className="flex-1 bg-transparent text-sm text-text-secondary outline-hidden"
                  disabled
                />
                <button className="p-2 rounded-md bg-brand-primary text-text-inverse opacity-50 cursor-not-allowed">
                  <ArrowRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
