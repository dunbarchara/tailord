import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Tailord — Why We\'re Building This',
  description:
    'Tailord generates structured, role-specific documents that map your experience to any job. Here\'s why that matters.',
}

export default function YCPage() {
  return (
    <div className="min-h-screen bg-surface-base">
      <div className="max-w-5xl mx-auto px-6 py-16 md:py-24">

        {/* Header */}
        <header className="mb-16">
          <p className="text-sm font-medium text-text-tertiary tracking-widest uppercase mb-6">
            Tailord
          </p>
          <h1 className="text-3xl font-semibold text-text-primary leading-snug mb-4">
            Why we&rsquo;re building this
          </h1>
          <p className="text-text-secondary leading-relaxed">
            Tailord generates structured, role-specific documents that map a
            candidate&rsquo;s experience to a specific job. Here&rsquo;s the
            problem it solves, and where it&rsquo;s going.
          </p>
        </header>

        <div className="space-y-14">

          {/* The Problem */}
          <section>
            <h2 className="text-xs font-semibold text-text-tertiary tracking-widest uppercase mb-4">
              The Problem
            </h2>
            <div className="space-y-4 text-text-secondary leading-relaxed">
              <p>
                Applying well for a specific role is high-value, high-effort
                work — and the job market has made it unreasonable to do it at
                scale.
              </p>
              <p>
                Every application requires the same underlying analysis: read
                the job description carefully, identify which requirements you
                actually meet, map your specific experience to each one, and
                write something that argues your fit for{' '}
                <em>this role specifically</em>. Done properly, that takes real
                time per application. And in today&rsquo;s hiring landscape,
                that investment is hard to justify: response rates have fallen,
                application volumes have soared, and ATS filters often mean a
                thoughtful, specific application is never read by a human at
                all.
              </p>
              <p>
                Of course candidates adapt. When the return on time invested is
                this uncertain, applying broadly and quickly is the rational
                response to an irrational system. The problem isn&rsquo;t
                candidate effort — it&rsquo;s a system that has made quality
                feel unrewarded.
              </p>
              <p>
                Tailord changes that calculus. It does the mapping work —
                turning your experience into a specific, grounded argument for
                this role — in minutes instead of hours. The investment in
                quality becomes accessible again.
              </p>
            </div>
          </section>

          <hr className="border-border-subtle" />

          {/* Individual Value */}
          <section>
            <h2 className="text-xs font-semibold text-text-tertiary tracking-widest uppercase mb-4">
              For the Candidate
            </h2>
            <div className="space-y-4 text-text-secondary leading-relaxed">
              <p>
                Tailord generates a <strong className="text-text-primary font-medium">Tailoring</strong>:
                a structured, role-specific document that maps your experience
                to a job description, requirement by requirement. It answers
                the question hiring managers actually need answered:{' '}
                <em>
                  &ldquo;Why is this person a strong fit for this
                  role?&rdquo;
                </em>
              </p>
              <p>
                You upload your resume (or connect GitHub, or write a summary).
                Tailord extracts a structured profile of your experience. When
                you paste a job URL, Tailord scrapes the job description, scores
                each requirement against your experience — STRONG, PARTIAL, or
                gap — and generates a targeted document grounded in your actual
                background. Not a rewritten resume, but a role-specific
                argument.
              </p>
              <p>
                After generating a Tailoring, Tailord detects gaps —
                requirements where your experience is PARTIAL or missing — and
                surfaces targeted follow-up questions. Not generic prompts, but
                specific ones:{' '}
                <em>
                  &ldquo;You listed React, but this role emphasizes performance
                  optimization — do you have a concrete example?&rdquo;
                </em>{' '}
                Answers feed back into your experience profile and improve every
                future Tailoring.
              </p>
              <p>
                Over time, Tailord becomes a{' '}
                <strong className="text-text-primary font-medium">
                  structured repository of your sourced, articulated experience
                </strong>{' '}
                — atomic, high-quality, and reusable across every application.
                Value compounds with each role you pursue. This is
                &ldquo;Scale AI but for an individual&rsquo;s experience&rdquo;:
                the same way Scale AI built high-quality labeled training data
                at scale, Tailord builds high-quality structured experience data
                for individuals.
              </p>
            </div>
          </section>

          <hr className="border-border-subtle" />

          {/* Shared Value */}
          <section>
            <h2 className="text-xs font-semibold text-text-tertiary tracking-widest uppercase mb-4">
              For the Hiring Team
            </h2>
            <div className="space-y-4 text-text-secondary leading-relaxed">
              <p>
                The Tailoring is not just a candidate artifact — it&rsquo;s a
                communication artifact.
              </p>
              <p>
                When a candidate shares a Tailoring with a hiring team, it
                creates a common language grounded in the job&rsquo;s own
                requirements. The hiring team can self-serve into
                role-specific candidate context without reading a sea of
                variable resumes. Relevant experience is surfaced by
                requirement, not buried in a chronological document optimized
                for no particular role.
              </p>
              <p>
                For the candidate: a clear, confident argument for their fit.
                For the hiring team: faster signal, less context-switching,
                better structured conversations before the first interview.
              </p>
              <p>
                Sharing is candidate-controlled — they decide when and what
                to share. The shared Tailoring becomes a common reference point
                before the conversation begins.
              </p>
            </div>
          </section>

          <hr className="border-border-subtle" />

          {/* Platform Value */}
          <section>
            <h2 className="text-xs font-semibold text-text-tertiary tracking-widest uppercase mb-4">
              For Platforms
            </h2>
            <div className="space-y-4 text-text-secondary leading-relaxed">
              <p>
                When the individual and shared value of Tailorings is
                recognized, platforms want it natively.
              </p>
              <p>
                Job boards and ATS platforms (Ashby, Greenhouse, Lever) already
                sit in the candidate + job data flow. The enrichment
                they&rsquo;re missing: structured fit analysis, requirement
                scoring, gap identification — surfaced inside their own UI,
                invisible to the job seeker.
              </p>
              <p>
                The model: an ATS platform passes candidate data and a job URL
                to Tailord&rsquo;s enrichment API. Tailord returns structured
                fit data. The platform renders it in their own interface.
                Tailord is never seen.
              </p>
              <p>
                This is the Clearbit model — invisible infrastructure that
                makes every application smarter. The platform gets richer
                candidate intelligence. The enrichment scales with platform
                volume, not individual consumer acquisition.
              </p>
            </div>
          </section>

          <hr className="border-border-subtle" />

          {/* Meta-Insight */}
          <section>
            <h2 className="text-xs font-semibold text-text-tertiary tracking-widest uppercase mb-4">
              The Bigger Picture
            </h2>
            <div className="space-y-4 text-text-secondary leading-relaxed">
              <p>
                As AI-generated content floods hiring pipelines,{' '}
                <strong className="text-text-primary font-medium">
                  structured, sourced human experience data becomes more
                  valuable, not less.
                </strong>
              </p>
              <p>
                Generic AI cover letters are already indistinguishable noise.
                The response to that noise isn&rsquo;t more AI-generated text
                — it&rsquo;s higher-quality, grounded, specific representation
                of real experience. Tailord builds that data layer.
              </p>
              <p>
                The moat is not the LLM. The moat is not the generation. The
                moat is the structured experience profile that compounds with
                every Tailoring, every enrichment loop, every targeted question
                answered. Competitors can generate a document. They
                can&rsquo;t replicate years of sourced, articulated experience
                data built through an ongoing feedback loop.
              </p>
            </div>
          </section>

        </div>

        {/* Footer */}
        <footer className="mt-20 pt-8 border-t border-border-subtle">
          <p className="text-sm text-text-tertiary">
            <a
              href="https://tailord.app"
              className="text-text-link hover:underline"
            >
              tailord.app
            </a>
          </p>
        </footer>

      </div>
    </div>
  )
}
