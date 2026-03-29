const POINTS = [
  {
    heading: 'Sourced, not generated',
    body: "Every match is grounded in what you've actually done. Tailord surfaces and contextualizes your existing experience — it doesn't invent qualifications you don't have.",
  },
  {
    heading: 'Honest about the gaps',
    body: "Partial matches are called partial. Gaps are called gaps. That honesty is what makes the strong matches credible — to you and to a recruiter.",
  },
  {
    heading: 'Specific to the role',
    body: "This isn't a generic resume polish. Every tailoring is derived from a real job description matched against your real background. The output is different every time because the role is different every time.",
  },
];

export function DifferentiatorSection() {
  return (
    <section className="px-6 py-16 lg:px-8 lg:py-24">
      <div className="mx-auto max-w-4xl">
        <div className="grid gap-16 lg:grid-cols-2 lg:gap-20 items-start">

          {/* Left: heading block */}
          <div className="lg:sticky lg:top-28">
            <p
              className="font-mono text-xs font-medium uppercase tracking-[0.6px] mb-3"
              style={{ color: 'var(--color-brand-accent)' }}
            >
              The difference
            </p>
            <h2
              className="text-2xl font-semibold text-text-primary tracking-tight leading-snug mb-5"
              style={{ letterSpacing: '-0.015em' }}
            >
              Built to advocate.
              <br />
              Not to inflate.
            </h2>
            <p className="text-text-secondary leading-relaxed text-sm">
              Most tools stuff your resume with keywords and hope for the best.
              Tailord builds a specific, sourced case for your fit — grounded in what
              you&apos;ve actually done.
            </p>
          </div>

          {/* Right: points */}
          <div className="flex flex-col gap-8">
            {POINTS.map((point) => (
              <div
                key={point.heading}
                className="pl-5"
                style={{ borderLeft: '2px solid var(--color-brand-accent)' }}
              >
                <h3 className="text-sm font-semibold text-text-primary mb-1.5 tracking-tight">{point.heading}</h3>
                <p className="text-sm text-text-secondary leading-relaxed">{point.body}</p>
              </div>
            ))}
          </div>

        </div>
      </div>
    </section>
  );
}
