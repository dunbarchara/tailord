import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Senior Software Engineer — Stripe',
  robots: { index: false, follow: false },
}

export default function MockJobMidLevelEngineer() {
  return (
    <main className="max-w-2xl mx-auto px-6 py-12 prose prose-sm text-text-primary prose-headings:text-text-primary prose-headings:font-semibold prose-p:text-text-secondary prose-p:leading-relaxed prose-li:text-text-secondary prose-strong:text-text-primary prose-a:text-text-link">

      <p className="text-text-tertiary text-xs mb-6 not-prose">
        Mock job posting — for testing only
      </p>

      <h1>Senior Software Engineer</h1>
      <p className="text-text-tertiary not-prose text-sm mb-8">Stripe · San Francisco, CA · Full-time</p>

      <h2>About the role</h2>
      <p>
        We are looking for a Senior Software Engineer to join our Payments Infrastructure team.
        You will build and scale the systems that move money reliably for millions of businesses
        around the world. This is a high-ownership role: you will be responsible for the full
        lifecycle of the services you build, from design through production.
      </p>

      <h2>Responsibilities</h2>
      <ul>
        <li>Design, build, and operate backend services for payment processing and financial infrastructure</li>
        <li>Improve reliability, latency, and scalability of critical payments systems</li>
        <li>Collaborate closely with product, data, and platform teams to define technical direction</li>
        <li>Review code, mentor engineers, and raise the engineering bar across the team</li>
        <li>Participate in on-call rotations and lead incident resolution when they arise</li>
      </ul>

      <h2>Requirements</h2>

      <h3>Required</h3>
      <ul>
        <li>3–5 years of professional software engineering experience</li>
        <li>Proficiency in Python, TypeScript, or Go</li>
        <li>Experience building and operating REST APIs in production</li>
        <li>Strong PostgreSQL and relational database skills</li>
        <li>Payments or financial services domain experience</li>
        <li>Familiarity with containerisation and deployment pipelines</li>
        <li>Distributed systems or high-availability design</li>
      </ul>

      <h3>Nice to have</h3>
      <ul>
        <li>Ability to mentor and support junior engineers</li>
        <li>Open source contributions or public technical work</li>
        <li>React or modern frontend framework experience</li>
      </ul>

    </main>
  )
}
