'use client';

import { Code, FileText, Lightbulb, TrendingUp } from 'lucide-react';

const useCases = [
  {
    title: 'Research & Analysis',
    description: 'Quickly synthesize information from documents, summarize reports, and uncover insights from data.',
    icon: TrendingUp,
    color: 'from-blue-500/20 to-blue-600/20',
  },
  {
    title: 'Content Creation',
    description: 'Write articles, create marketing copy, draft emails, and generate creative content with ease.',
    icon: FileText,
    color: 'from-purple-500/20 to-purple-600/20',
  },
  {
    title: 'Coding & Development',
    description: 'Debug code, write functions, explain technical concepts, and accelerate your development workflow.',
    icon: Code,
    color: 'from-green-500/20 to-green-600/20',
  },
  {
    title: 'Brainstorming',
    description: 'Generate ideas, explore creative solutions, and think through complex problems collaboratively.',
    icon: Lightbulb,
    color: 'from-orange-500/20 to-orange-600/20',
  },
];

export function UseCases() {
  return (
    <section className="py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-semibold tracking-tight text-text-primary sm:text-4xl">
            Built for the way you work
          </h2>
          <p className="mt-6 text-lg leading-8 text-text-secondary">
            Whether you're writing, coding, researching, or creating, Tailord adapts to your needs.
          </p>
        </div>

        <div className="mx-auto mt-16 grid max-w-7xl grid-cols-1 gap-6 sm:mt-20 lg:grid-cols-2 lg:gap-8">
          {useCases.map((useCase, index) => {
            const Icon = useCase.icon;
            return (
              <div
                key={useCase.title}
                className="relative overflow-hidden rounded-2xl border border-border-subtle bg-surface-elevated p-8 hover:shadow-lg transition-all duration-300 animate-slide-up group"
                style={{ animationDelay: `${index * 0.1}s` }}
              >
                <div className={`absolute inset-0 bg-linear-to-br ${useCase.color} opacity-0 group-hover:opacity-100 transition-opacity duration-300`} />
                <div className="relative">
                  <div className="flex items-center gap-4 mb-4">
                    <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-brand-primary/10 ring-1 ring-brand-primary/20">
                      <Icon className="h-6 w-6 text-brand-primary" />
                    </div>
                    <h3 className="text-xl font-semibold text-text-primary">
                      {useCase.title}
                    </h3>
                  </div>
                  <p className="text-base leading-7 text-text-secondary">
                    {useCase.description}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
