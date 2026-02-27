'use client';

import { useState } from 'react';
import { Copy, CheckCircle2, ExternalLink, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface TailoringDetailProps {
  tailoringId: string;
}

// Placeholder — replace with real fetch when backend is wired
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
};

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function TailoringDetail({ tailoringId }: TailoringDetailProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(mockTailoring.coverLetter);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="h-full overflow-y-auto custom-scrollbar">
      <div className="max-w-3xl mx-auto p-6 lg:p-8 space-y-8">
        {/* Header */}
        <div className="space-y-3">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              <h1 className="text-2xl font-semibold text-text-primary truncate">
                {mockTailoring.jobTitle}
              </h1>
              <p className="text-text-secondary mt-1">
                {mockTailoring.company} · {mockTailoring.createdAt}
              </p>
            </div>
            <Button variant="outline" size="sm" asChild>
              <a href={mockTailoring.url} target="_blank" rel="noopener noreferrer" className="gap-2">
                <ExternalLink className="h-4 w-4" />
                View Posting
              </a>
            </Button>
          </div>

          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-md bg-success-bg border border-success/20">
            <Sparkles className="h-4 w-4 text-success" />
            <span className="text-sm font-medium text-text-primary">{mockTailoring.matchScore}% match</span>
          </div>
        </div>

        {/* Analysis */}
        <div className="space-y-4">
          <h2 className="text-base font-semibold text-text-primary">Analysis</h2>
          <div className="grid md:grid-cols-2 gap-4">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-sm font-medium">
                  <div className="h-2 w-2 rounded-full bg-success" />
                  Strengths
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {mockTailoring.analysis.strengths.map((strength, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-text-secondary">
                      <CheckCircle2 className="h-4 w-4 text-success flex-shrink-0 mt-0.5" />
                      {strength}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-sm font-medium">
                  <div className="h-2 w-2 rounded-full bg-warning" />
                  Gaps
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {mockTailoring.analysis.gaps.map((gap, i) => (
                    <li key={i} className="text-sm text-text-secondary">· {gap}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Recommendations</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2">
                {mockTailoring.analysis.recommendations.map((rec, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-text-secondary">
                    <span className="text-brand-primary mt-0.5 flex-shrink-0">→</span>
                    {rec}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </div>

        {/* Cover Letter */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-text-primary">Cover Letter</h2>
            <Button
              variant="outline"
              size="sm"
              onClick={handleCopy}
              className="gap-2"
            >
              {copied ? (
                <><CheckCircle2 className="h-4 w-4 text-success" />Copied</>
              ) : (
                <><Copy className="h-4 w-4" />Copy</>
              )}
            </Button>
          </div>
          <Card>
            <CardContent className="pt-6">
              <pre className="whitespace-pre-wrap font-sans text-sm text-text-secondary leading-relaxed">
                {mockTailoring.coverLetter}
              </pre>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
