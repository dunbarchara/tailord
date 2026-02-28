'use client';

import { Brain, Shield, Zap, Users } from 'lucide-react';

const features = [
  {
    name: 'Advanced reasoning',
    description: 'Tailord can handle complex multi-step tasks with nuanced understanding and sophisticated reasoning capabilities.',
    icon: Brain,
  },
  {
    name: 'Vision capabilities',
    description: 'Upload images and PDFs to have Tailord analyze, interpret, and discuss visual content alongside text.',
    icon: Zap,
  },
  {
    name: 'Secure and trustworthy',
    description: 'Built with safety at the core. Tailord is designed to be helpful, harmless, and honest in all interactions.',
    icon: Shield,
  },
  {
    name: 'Team collaboration',
    description: 'Share conversations, create team workspaces, and collaborate on projects with your colleagues.',
    icon: Users,
  },
];

export function Features() {
  return (
    <section className="bg-surface-elevated py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-base font-semibold leading-7 text-brand-primary">
            Everything you need
          </h2>
          <p className="mt-2 text-3xl font-semibold tracking-tight text-text-primary sm:text-4xl">
            A powerful AI assistant for work
          </p>
          <p className="mt-6 text-lg leading-8 text-text-secondary">
            Tailord can help with a wide range of tasks, from research and analysis to coding and creative projects.
          </p>
        </div>

        <div className="mx-auto mt-16 max-w-7xl sm:mt-20 lg:mt-24">
          <dl className="grid grid-cols-1 gap-x-8 gap-y-12 lg:grid-cols-2 lg:gap-y-16">
            {features.map((feature, index) => {
              const Icon = feature.icon;
              return (
                <div
                  key={feature.name}
                  className="relative pl-16 animate-slide-up"
                  style={{ animationDelay: `${index * 0.1}s` }}
                >
                  <dt className="text-base font-semibold leading-7 text-text-primary">
                    <div className="absolute left-0 top-0 flex h-10 w-10 items-center justify-center rounded-lg bg-brand-primary">
                      <Icon className="h-5 w-5 text-text-inverse" />
                    </div>
                    {feature.name}
                  </dt>
                  <dd className="mt-2 text-base leading-7 text-text-secondary">
                    {feature.description}
                  </dd>
                </div>
              );
            })}
          </dl>
        </div>
      </div>
    </section>
  );
}
