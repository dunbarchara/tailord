// Stylized mockup of the job posting analysis output.
// Replace with a real screenshot once the UI is polished enough to capture.

const MOCK_REQUIREMENTS = [
  {
    score: 'strong' as const,
    content: '5+ years of backend engineering experience',
    advocacy: 'Alex brings six years of backend engineering across two companies, including owning a distributed API platform serving 40M requests per day.',
  },
  {
    score: 'strong' as const,
    content: 'Proficiency in containerization (Docker, Kubernetes)',
    advocacy: 'Alex has managed Kubernetes-based deployments on AKS at scale, including Docker, Helm, and Istio across 40+ microservices.',
  },
  {
    score: 'partial' as const,
    content: 'Experience with AWS or GCP cloud platforms',
    advocacy: 'Alex has deep Azure cloud experience — infrastructure ownership across two Microsoft IoT teams. Direct AWS or GCP exposure is not documented.',
  },
  {
    score: 'gap' as const,
    content: 'Open-source contributions',
    advocacy: null,
  },
];

const SCORE_CONFIG = {
  strong: {
    label: 'Strong',
    bar: 'bg-score-strong',
    dot: 'bg-score-strong',
    text: 'text-score-strong',
  },
  partial: {
    label: 'Partial',
    bar: 'bg-score-partial',
    dot: 'bg-score-partial',
    text: 'text-score-partial',
  },
  gap: {
    label: 'Gap',
    bar: 'bg-score-gap',
    dot: 'bg-score-gap',
    text: 'text-score-gap',
  },
};

export function ProductPreview() {
  return (
    <section className="px-6 py-16 lg:px-8 lg:py-24">
      <div className="mx-auto max-w-2xl">

        <p
          className="font-mono text-xs font-medium uppercase tracking-[0.6px] text-center mb-3"
          style={{ color: 'var(--color-brand-accent)' }}
        >
          What you get
        </p>

        <h2 className="text-2xl font-semibold text-text-primary text-center mb-2 tracking-tight" style={{ letterSpacing: '-0.015em' }}>
          Every requirement, scored against your background
        </h2>
        <p className="text-text-secondary text-center mb-10 max-w-lg mx-auto leading-relaxed text-sm">
          Not a percentage. Not a keyword list. A line-by-line breakdown of where you fit — and a clear explanation of why.
        </p>

        {/* Mockup card */}
        <div className="rounded-3xl border border-border-subtle bg-surface-elevated shadow-md overflow-hidden">

          {/* Card header */}
          <div
            className="px-5 py-4 border-b border-border-subtle flex items-center justify-between"
            style={{ backgroundColor: 'var(--color-brand-accent-subtle)' }}
          >
            <div>
              <p className="text-xs font-medium uppercase tracking-wider text-text-tertiary mb-0.5">Acme Corp</p>
              <p className="text-sm font-semibold text-text-primary">Senior Backend Engineer</p>
            </div>
            <div className="flex items-center gap-3 text-xs text-text-tertiary">
              <span className="flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-score-strong" />
                3 Strong
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-score-partial" />
                1 Partial
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-score-gap" />
                1 Gap
              </span>
            </div>
          </div>

          {/* Requirements */}
          <div className="divide-y divide-border-subtle">
            {MOCK_REQUIREMENTS.map((req, i) => {
              const config = SCORE_CONFIG[req.score];
              return (
                <div key={i} className="px-5 py-4 flex gap-4 items-start">
                  <div className={`mt-1.5 w-1 self-stretch rounded-full flex-shrink-0 min-h-[2rem] ${config.bar}`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className={`text-xs font-medium flex items-center gap-1.5 ${config.text}`}>
                        <span className={`h-1.5 w-1.5 rounded-full ${config.dot}`} />
                        {config.label}
                      </span>
                    </div>
                    <p className="text-sm text-text-primary leading-snug mb-2">{req.content}</p>
                    {req.advocacy && (
                      <p className="text-xs text-text-secondary leading-relaxed">{req.advocacy}</p>
                    )}
                    {!req.advocacy && req.score === 'gap' && (
                      <p className="text-xs text-text-tertiary italic leading-relaxed">No evidence of open-source contributions in the profile.</p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <p className="text-xs text-text-tertiary text-center mt-5 leading-relaxed">
          Partial matches are called partial. Gaps are called gaps.{' '}
          <span className="text-text-secondary">That honesty is what makes the strong matches mean something.</span>
        </p>
      </div>
    </section>
  );
}
