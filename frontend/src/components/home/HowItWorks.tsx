const STEPS = [
  {
    number: '01',
    title: 'Bring your experience',
    description:
      'Upload your resume, connect GitHub, or add context in your own words. Tailord builds a complete picture of your background from every source you provide.',
  },
  {
    number: '02',
    title: 'Paste a job posting',
    description:
      'Provide a job URL. Tailord extracts what the role is really asking for — skills, responsibilities, and signals — and structures it for analysis.',
  },
  {
    number: '03',
    title: 'See exactly where you fit',
    description:
      'Every requirement scored against your background. A tailoring document written in your voice. Ready to use in applications and interviews.',
  },
];

export function HowItWorks() {
  return (
    <section className="px-6 py-16 lg:px-8 lg:py-24 bg-surface-elevated border-y border-border-subtle">
      <div className="mx-auto max-w-4xl">
        <p
          className="font-mono text-xs font-medium uppercase tracking-[0.6px] text-center mb-3"
          style={{ color: 'var(--color-brand-accent)' }}
        >
          How it works
        </p>
        <h2 className="text-2xl font-semibold text-text-primary text-center tracking-tight mb-14" style={{ letterSpacing: '-0.015em' }}>
          From background to argument in minutes
        </h2>

        <div className="grid gap-10 sm:grid-cols-3">
          {STEPS.map((step) => (
            <div key={step.number}>
              <p
                className="text-4xl font-semibold mb-4 leading-none select-none tabular-nums"
                style={{ color: 'var(--color-brand-accent)', opacity: 0.2 }}
              >
                {step.number}
              </p>
              <h3 className="text-sm font-semibold text-text-primary mb-2 tracking-tight">{step.title}</h3>
              <p className="text-sm text-text-secondary leading-relaxed">{step.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
