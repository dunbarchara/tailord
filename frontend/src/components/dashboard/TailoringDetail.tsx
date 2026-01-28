'use client';

import { Download, Copy, CheckCircle2, ExternalLink, Sparkles } from 'lucide-react';
import { useState } from 'react';

interface TailoringDetailProps {
  tailoringId: string;
}

// Mock data - in production, fetch based on tailoringId
const mockTailoring = {
  id: '1',
  jobTitle: 'Senior Frontend Engineer',
  company: 'TechCorp',
  url: 'https://techcorp.com/careers/senior-frontend',
  createdAt: '2 days ago',
  matchScore: 94,
  analysis: {
    strengths: [
      'Strong React experience (5 years)',
      'Leadership in component library development',
      'Experience with TypeScript and modern build tools',
      'Track record of performance optimization',
    ],
    gaps: [
      'Limited GraphQL experience (they use it extensively)',
      'No mention of WebGL (nice-to-have for their data viz)',
    ],
    recommendations: [
      'Highlight your component library work in the opening',
      'Emphasize scalability achievements from previous roles',
      'Mention your quick learning ability for GraphQL',
    ],
  },
  coverLetter: `Dear Hiring Manager,

I am writing to express my strong interest in the Senior Frontend Engineer position at TechCorp. With over 5 years of specialized experience in React development and a proven track record of building scalable component systems, I am confident I would be a valuable addition to your team.

In my current role at StartupXYZ, I led the development of a comprehensive component library that reduced development time by 40% and improved code consistency across 15+ product teams. This experience directly aligns with your need for someone who can architect robust, reusable frontend solutions.

My expertise in TypeScript, modern build tools, and performance optimization would allow me to contribute immediately to your team's goals. I'm particularly excited about TechCorp's focus on developer experience and would love to bring my component architecture knowledge to help scale your engineering organization.

While I notice GraphQL is a key technology in your stack, I'm a quick learner who has successfully adopted new technologies throughout my career. My strong foundation in REST APIs and state management would facilitate a smooth transition.

I would welcome the opportunity to discuss how my experience in building scalable frontend systems can contribute to TechCorp's continued success.

Best regards,
John Doe`,
  resumeHighlights: [
    'Led development of component library serving 15+ teams',
    'Reduced bundle size by 60% through code splitting and lazy loading',
    'Mentored 5 junior developers in React best practices',
    'Implemented automated visual regression testing',
    'Improved Lighthouse performance score from 65 to 95',
  ],
};

export function TailoringDetail({ tailoringId }: TailoringDetailProps) {
  const [copied, setCopied] = useState<string | null>(null);

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopied(id);
    setTimeout(() => setCopied(null), 2000);
  };

  return (
    <div className="h-full overflow-y-auto custom-scrollbar">
      <div className="max-w-5xl mx-auto p-6 lg:p-8 space-y-8">
        {/* Header */}
        <div className="space-y-4">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              <h1 className="text-2xl font-semibold text-text-primary truncate">
                {mockTailoring.jobTitle}
              </h1>
              <p className="text-text-secondary mt-1">
                {mockTailoring.company} • Created {mockTailoring.createdAt}
              </p>
            </div>
            
            <a
              href={mockTailoring.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border-default hover:bg-surface-overlay transition-colors text-sm font-medium text-text-primary flex-shrink-0"
            >
              View Posting
              <ExternalLink className="h-4 w-4" />
            </a>
          </div>

          {/* Match Score */}
          <div className="inline-flex items-center gap-3 px-4 py-2 rounded-lg bg-success-bg border border-success-border">
            <Sparkles className="h-5 w-5 text-success" />
            <div>
              <span className="text-sm font-medium text-text-primary">
                {mockTailoring.matchScore}% Match
              </span>
              <span className="text-sm text-text-secondary ml-2">
                Strong fit for this role
              </span>
            </div>
          </div>
        </div>

        {/* AI Analysis */}
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-text-primary">
            AI Analysis
          </h2>

          <div className="grid md:grid-cols-2 gap-4">
            {/* Strengths */}
            <div className="p-6 rounded-xl bg-surface-elevated border border-border-subtle">
              <h3 className="font-semibold text-text-primary mb-4 flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-success" />
                Your Strengths
              </h3>
              <ul className="space-y-3">
                {mockTailoring.analysis.strengths.map((strength, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-text-secondary">
                    <CheckCircle2 className="h-4 w-4 text-success flex-shrink-0 mt-0.5" />
                    <span>{strength}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Gaps */}
            <div className="p-6 rounded-xl bg-surface-elevated border border-border-subtle">
              <h3 className="font-semibold text-text-primary mb-4 flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-warning" />
                Potential Gaps
              </h3>
              <ul className="space-y-3">
                {mockTailoring.analysis.gaps.map((gap, i) => (
                  <li key={i} className="text-sm text-text-secondary">
                    • {gap}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Recommendations */}
          <div className="p-6 rounded-xl bg-brand-primary/5 border border-brand-primary/20">
            <h3 className="font-semibold text-text-primary mb-4">
              Recommendations
            </h3>
            <ul className="space-y-2">
              {mockTailoring.analysis.recommendations.map((rec, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-text-secondary">
                  <span className="text-brand-primary mt-0.5">→</span>
                  <span>{rec}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Cover Letter */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-text-primary">
              Generated Cover Letter
            </h2>
            <div className="flex gap-2">
              <button
                onClick={() => handleCopy(mockTailoring.coverLetter, 'cover-letter')}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-border-default hover:bg-surface-overlay transition-colors text-sm"
              >
                {copied === 'cover-letter' ? (
                  <>
                    <CheckCircle2 className="h-4 w-4 text-success" />
                    Copied
                  </>
                ) : (
                  <>
                    <Copy className="h-4 w-4" />
                    Copy
                  </>
                )}
              </button>
              <button className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-border-default hover:bg-surface-overlay transition-colors text-sm">
                <Download className="h-4 w-4" />
                Download
              </button>
            </div>
          </div>

          <div className="p-6 rounded-xl bg-surface-elevated border border-border-subtle">
            <pre className="whitespace-pre-wrap font-sans text-sm text-text-secondary leading-relaxed">
              {mockTailoring.coverLetter}
            </pre>
          </div>
        </div>

        {/* Resume Highlights */}
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-text-primary">
            Resume Highlights to Emphasize
          </h2>

          <div className="p-6 rounded-xl bg-surface-elevated border border-border-subtle space-y-3">
            {mockTailoring.resumeHighlights.map((highlight, i) => (
              <div
                key={i}
                className="flex items-start gap-3 pb-3 border-b border-border-subtle last:border-0 last:pb-0"
              >
                <div className="flex-shrink-0 w-6 h-6 rounded-full bg-brand-primary/10 text-brand-primary flex items-center justify-center text-xs font-semibold mt-0.5">
                  {i + 1}
                </div>
                <p className="text-sm text-text-secondary flex-1">
                  {highlight}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3 pt-4 border-t border-border-subtle">
          <button className="px-6 py-3 rounded-lg bg-brand-primary text-text-inverse font-medium hover:bg-brand-primary-hover transition-colors">
            Apply Now
          </button>
          <button className="px-6 py-3 rounded-lg border border-border-default text-text-primary font-medium hover:bg-surface-overlay transition-colors">
            Edit Content
          </button>
        </div>
      </div>
    </div>
  );
}
