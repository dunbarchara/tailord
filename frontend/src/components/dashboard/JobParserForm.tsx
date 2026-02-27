'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { submitJob, generateMatch } from '@/lib/api';

export function JobParserForm() {
  const [jobUrl, setJobUrl] = useState('');
  const [jobId, setJobId] = useState<string | null>(null);
  const [output, setOutput] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmitJob(e: React.FormEvent) {
    e.preventDefault();
    if (!jobUrl) return;

    setLoading(true);
    setError(null);
    setJobId(null);
    setOutput(null);

    try {
      const data = await submitJob(JSON.stringify({ job_url: jobUrl }));
      setJobId(data.job_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong');
    } finally {
      setLoading(false);
    }
  }

  async function handleGenerate() {
    if (!jobId) return;

    setLoading(true);
    setError(null);
    setOutput(null);

    try {
      const data = await generateMatch(JSON.stringify({ job_id: jobId }));
      setOutput(data.content);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong');
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Job Posting</CardTitle>
        <CardDescription>Paste a job posting URL to analyze it</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <form onSubmit={handleSubmitJob} className="flex gap-2">
          <Input
            type="url"
            placeholder="https://company.com/jobs/..."
            value={jobUrl}
            onChange={(e) => setJobUrl(e.target.value)}
            disabled={loading}
            className="flex-1"
          />
          <Button type="submit" disabled={!jobUrl || loading}>
            {loading && !jobId ? 'Analyzing...' : 'Analyze Job'}
          </Button>
        </form>

        {jobId && (
          <Button
            variant="secondary"
            onClick={handleGenerate}
            disabled={loading}
            className="w-full"
          >
            {loading && jobId ? 'Generating...' : 'Generate Match Statement'}
          </Button>
        )}

        {error && <p className="text-sm text-error">{error}</p>}

        {output && (
          <div className="rounded-lg border border-border-default bg-surface-overlay p-4">
            <p className="text-sm text-text-secondary leading-relaxed">{output}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
