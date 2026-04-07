import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Software Engineer, Platform — Acme Corp',
  robots: { index: false, follow: false },
}

/**
 * Mock job posting — used for manual parser testing and as a future demo surface
 * for unapproved users. Intentionally minimal: covers the structural elements the
 * scraper and chunk extractor need to handle (headings, paragraphs, required vs
 * preferred bullets) without ATS chrome, forms, or EEO boilerplate.
 *
 * Public and unauthenticated by design — static content, zero attack surface.
 * noindex keeps it out of search results.
 */
export default function MockJobSoftwareEngineer() {
  return (
    <main className="max-w-2xl mx-auto px-6 py-12 prose prose-sm text-text-primary prose-headings:text-text-primary prose-headings:font-semibold prose-p:text-text-secondary prose-p:leading-relaxed prose-li:text-text-secondary prose-strong:text-text-primary prose-a:text-text-link">

      <p className="text-text-tertiary text-xs mb-6 not-prose">
        Mock job posting — for testing only
      </p>

      <h1>Software Engineer, Platform</h1>
      <p className="text-text-tertiary not-prose text-sm mb-8">Acme Corp · San Francisco, CA · Full-time</p>

      <h2>About the role</h2>
      <p>
        We are looking for a Software Engineer to join our Platform team. You will build and
        maintain the core infrastructure that our product teams rely on — including internal
        APIs, developer tooling, and deployment pipelines. This is a hands-on role with broad
        impact across the engineering organisation.
      </p>

      <h2>Responsibilities</h2>
      <ul>
        <li>Design, build, and maintain backend services and APIs used across product teams</li>
        <li>Own reliability and performance of platform infrastructure end-to-end</li>
        <li>Collaborate with product engineers to define platform contracts and abstractions</li>
        <li>Contribute to on-call rotations and drive incident resolution</li>
      </ul>

      <h2>Requirements</h2>

      <h3>Required</h3>
      <ul>
        <li>3+ years of professional software engineering experience</li>
        <li>Proficiency in at least one backend language (Python, Go, or TypeScript)</li>
        <li>Experience designing and operating REST or gRPC APIs in production</li>
        <li>Familiarity with containerisation and cloud infrastructure (AWS, GCP, or Azure)</li>
      </ul>

      <h3>Preferred</h3>
      <ul>
        <li>Experience with Kubernetes or container orchestration at scale</li>
        <li>Prior work on internal developer platforms or infrastructure tooling</li>
      </ul>

    </main>
  )
}
