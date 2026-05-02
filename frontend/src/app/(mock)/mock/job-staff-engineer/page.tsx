import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Staff Engineer — Vercel',
  robots: { index: false, follow: false },
}

export default function MockJobStaffEngineer() {
  return (
    <main className="max-w-2xl mx-auto px-6 py-12 prose prose-sm text-text-primary prose-headings:text-text-primary prose-headings:font-semibold prose-p:text-text-secondary prose-p:leading-relaxed prose-li:text-text-secondary prose-strong:text-text-primary prose-a:text-text-link">

      <p className="text-text-tertiary text-xs mb-6 not-prose">
        Mock job posting — for testing only
      </p>

      <h1>Staff Engineer</h1>
      <p className="text-text-tertiary not-prose text-sm mb-8">Vercel · Remote · Full-time</p>

      <h2>About the role</h2>
      <p>
        Vercel is the platform for frontend developers. We run one of the largest edge networks in the
        world, serving millions of deployments per day for teams at companies of every size. We are
        looking for a Staff Engineer to help define the future of our edge infrastructure and runtime
        environments.
      </p>
      <p>
        This is a technical leadership role. You will set architectural direction, drive initiatives
        across multiple engineering teams, and have a measurable impact on the reliability and
        performance of our global platform. You will be a multiplier — making the engineers around
        you more effective and helping Vercel stay ahead of the frontier.
      </p>

      <h2>Responsibilities</h2>
      <ul>
        <li>Define and own the technical roadmap for edge compute and runtime infrastructure</li>
        <li>Drive architectural decisions that span multiple teams and affect the entire platform</li>
        <li>Lead cross-functional technical initiatives from inception to production</li>
        <li>Mentor and develop senior engineers across the organisation</li>
        <li>Represent engineering in product strategy and external technical communications</li>
        <li>Identify systemic risks and lead efforts to address them before they become incidents</li>
      </ul>

      <h2>Requirements</h2>

      <h3>Required</h3>
      <ul>
        <li>8+ years of software engineering experience</li>
        <li>Proven technical leadership across multiple teams or engineering organisations</li>
        <li>Deep experience with Next.js or edge runtime environments</li>
        <li>CDN, caching, or edge compute infrastructure design</li>
        <li>Ownership of engineering org-wide technical roadmap or architecture decisions</li>
        <li>Strong distributed systems or infrastructure background</li>
        <li>Mentorship and development of senior engineers</li>
      </ul>

      <h3>Nice to have</h3>
      <ul>
        <li>Experience with serverless or stateless compute patterns (Deno, Cloudflare Workers, Lambda@Edge)</li>
        <li>Contributions to frontend performance or Core Web Vitals at scale</li>
        <li>Open source contributions or public technical writing</li>
      </ul>

    </main>
  )
}
