import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { JobAnalysis } from '@/types';

interface AnalysisResultProps {
  analysis: JobAnalysis;
}

export function AnalysisResult({ analysis }: AnalysisResultProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {analysis.title ?? 'Job Analysis'}
          {analysis.company && (
            <span className="text-text-secondary font-normal ml-2">at {analysis.company}</span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {analysis.requirements && analysis.requirements.length > 0 && (
          <div>
            <h3 className="text-sm font-medium text-text-secondary mb-2">Requirements</h3>
            <div className="flex flex-wrap gap-2">
              {analysis.requirements.map((req, i) => (
                <Badge key={i} variant="secondary">{req}</Badge>
              ))}
            </div>
          </div>
        )}
        {analysis.skills && analysis.skills.length > 0 && (
          <div>
            <h3 className="text-sm font-medium text-text-secondary mb-2">Skills</h3>
            <div className="flex flex-wrap gap-2">
              {analysis.skills.map((skill, i) => (
                <Badge key={i} variant="outline">{skill}</Badge>
              ))}
            </div>
          </div>
        )}
        {analysis.responsibilities && analysis.responsibilities.length > 0 && (
          <div>
            <h3 className="text-sm font-medium text-text-secondary mb-2">Responsibilities</h3>
            <ul className="space-y-1">
              {analysis.responsibilities.map((r, i) => (
                <li key={i} className="text-sm text-text-secondary flex gap-2">
                  <span className="text-text-tertiary">•</span>
                  <span>{r}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
