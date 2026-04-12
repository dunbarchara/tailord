import fs from 'fs'
import path from 'path'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Privacy Policy — Tailord',
}

export default function PrivacyPage() {
  const html = fs.readFileSync(
    path.join(process.cwd(), 'src/content/privacy-policy.html'),
    'utf-8'
  )

  return (
    <div className="min-h-screen bg-surface-base">
      <div
        className="max-w-3xl mx-auto px-6 py-12 prose prose-sm text-text-primary prose-headings:text-text-primary prose-headings:font-semibold prose-p:text-text-secondary prose-p:leading-relaxed prose-strong:text-text-primary prose-a:text-text-link prose-a:underline prose-li:text-text-secondary"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  )
}
