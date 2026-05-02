import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Software Engineer — Linear',
  robots: { index: false, follow: false },
}

export default function MockJobSoftwareEngineerLinear() {
  return (
    <main className="max-w-2xl mx-auto px-6 py-12 prose prose-sm text-text-primary prose-headings:text-text-primary prose-headings:font-semibold prose-p:text-text-secondary prose-p:leading-relaxed prose-li:text-text-secondary prose-strong:text-text-primary prose-a:text-text-link">

      <p className="text-text-tertiary text-xs mb-6 not-prose">
        Mock job posting — for testing only
      </p>

      <h1>Software Engineer</h1>
      <p className="text-text-tertiary not-prose text-sm mb-8">Linear · Remote (US/EU) · Full-time</p>

      <h2>About the role</h2>
      <p>
        Linear is building the next generation of project management software. We care deeply about
        product quality, performance, and developer experience. We&apos;re looking for a Software
        Engineer who sweats the details, ships fast, and wants to work on a product used by tens of
        thousands of engineering teams worldwide.
      </p>
      <p>
        This is a full-stack role. You&apos;ll work across our TypeScript backend and React frontend,
        contribute to our public GraphQL API, and help shape how Linear evolves as a product.
      </p>

      <h2>Responsibilities</h2>
      <ul>
        <li>Build and maintain features across the Linear product — from API to UI</li>
        <li>Contribute to the public GraphQL API and developer platform</li>
        <li>Improve application performance, reliability, and scalability</li>
        <li>Work closely with design to ship polished, high-quality interfaces</li>
        <li>Help define technical direction as the team scales</li>
      </ul>

      <h2>Requirements</h2>

      <h3>Required</h3>
      <ul>
        <li>2–4 years of professional software engineering experience</li>
        <li>TypeScript proficiency (frontend and backend)</li>
        <li>PostgreSQL or relational database experience</li>
        <li>Experience building or consuming REST or GraphQL APIs</li>
        <li>React experience with component-driven UI development</li>
        <li>Attention to product quality and design detail</li>
      </ul>

      <h3>Nice to have</h3>
      <ul>
        <li>Experience with project management or productivity tooling</li>
        <li>GraphQL API design and implementation</li>
        <li>Electron or desktop application experience</li>
      </ul>

    </main>
  )
}
