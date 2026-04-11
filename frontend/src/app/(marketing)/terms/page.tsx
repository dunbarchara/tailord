import fs from 'fs'
import path from 'path'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Terms of Use — Tailord',
}

export default function TermsPage() {
  const html = fs.readFileSync(
    path.join(process.cwd(), 'src/content/terms-of-use.html'),
    'utf-8'
  )

  return (
    <div className="min-h-screen bg-white">
      <div
        className="max-w-3xl mx-auto px-6 py-12"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  )
}
