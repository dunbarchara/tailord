'use client';

import { useState } from 'react';
import { Download, Copy, CheckCircle2, ExternalLink, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface TailoringDetailProps {
  tailoringId: string;
}

// Placeholder data — replace with real fetch when backend is wired
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

Best regards,
John Doe`,
  resumeHighlights: [
    'Led development of component library serving 15+ teams',
    'Reduced bundle size by 60% through code splitting and lazy loading',
    'Mentored 5 junior developers in React best practices',
  ],
};

// eslint-disable-next-line @typescript-eslint/no-unused-vars
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
            <Button variant="outline" size="sm" asChild>
              <a href={mockTailoring.url} target="_blank" rel="noopener noreferrer" className="gap-2">
                View Posting
                <ExternalLink className="h-4 w-4" />
              </a>
            </Button>
          </div>

          <div className="inline-flex items-center gap-3 px-4 py-2 rounded-lg bg-success-bg border border-success/20">
            <Sparkles className="h-5 w-5 text-success" />
            <span className="text-sm font-medium text-text-primary">
              {mockTailoring.matchScore}% Match
            </span>
            <span className="text-sm text-text-secondary">Strong fit for this role</span>
          </div>
        </div>

        {/* AI Analysis */}
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-text-primary">AI Analysis</h2>
          <div className="grid md:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <div className="h-2 w-2 rounded-full bg-success" />
                  Your Strengths
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-3">
                  {mockTailoring.analysis.strengths.map((strength, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-text-secondary">
                      <CheckCircle2 className="h-4 w-4 text-success flex-shrink-0 mt-0.5" />
                      <span>{strength}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <div className="h-2 w-2 rounded-full bg-warning" />
                  Potential Gaps
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-3">
                  {mockTailoring.analysis.gaps.map((gap, i) => (
                    <li key={i} className="text-sm text-text-secondary">• {gap}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          </div>

          <Card className="border-brand-primary/20 bg-brand-primary/5">
            <CardHeader>
              <CardTitle className="text-base">Recommendations</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2">
                {mockTailoring.analysis.recommendations.map((rec, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-text-secondary">
                    <span className="text-brand-primary mt-0.5">→</span>
                    <span>{rec}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </div>

        {/* Cover Letter */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-text-primary">Generated Cover Letter</h2>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleCopy(mockTailoring.coverLetter, 'cover-letter')}
                className="gap-2"
              >
                {copied === 'cover-letter' ? (
                  <><CheckCircle2 className="h-4 w-4 text-success" />Copied</>
                ) : (
                  <><Copy className="h-4 w-4" />Copy</>
                )}
              </Button>
              <Button variant="outline" size="sm" className="gap-2">
                <Download className="h-4 w-4" />
                Download
              </Button>
            </div>
          </div>
          <Card>
            <CardContent className="pt-6">
              <pre className="whitespace-pre-wrap font-sans text-sm text-text-secondary leading-relaxed">
                {mockTailoring.coverLetter}
              </pre>
            </CardContent>
          </Card>
        </div>

        {/* Resume Highlights */}
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-text-primary">Resume Highlights to Emphasize</h2>
          <Card>
            <CardContent className="pt-6 space-y-3">
              {mockTailoring.resumeHighlights.map((highlight, i) => (
                <div
                  key={i}
                  className="flex items-start gap-3 pb-3 border-b border-border-subtle last:border-0 last:pb-0"
                >
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-brand-primary/10 text-brand-primary flex items-center justify-center text-xs font-semibold mt-0.5">
                    {i + 1}
                  </div>
                  <p className="text-sm text-text-secondary flex-1">{highlight}</p>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>

        {/* Actions */}
        <div className="flex gap-3 pt-4 border-t border-border-subtle">
          <Button>Apply Now</Button>
          <Button variant="outline">Edit Content</Button>
        </div>
      </div>
    </div>
  );
}
