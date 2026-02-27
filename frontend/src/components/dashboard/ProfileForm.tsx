'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { submitProfile } from '@/lib/api';

export function ProfileForm() {
  const [resume, setResume] = useState('');
  const [github, setGithub] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!resume || !github) return;

    setLoading(true);
    setError(null);
    setSaved(false);

    try {
      await submitProfile(JSON.stringify({ resume_text: resume, github_username: github }));
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong');
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>User Profile</CardTitle>
        <CardDescription>Enter your resume and GitHub username</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <textarea
            className="w-full min-h-32 rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 resize-y"
            placeholder="Paste resume text..."
            value={resume}
            onChange={(e) => setResume(e.target.value)}
            disabled={loading}
          />
          <Input
            placeholder="GitHub username"
            value={github}
            onChange={(e) => setGithub(e.target.value)}
            disabled={loading}
          />
          {error && <p className="text-sm text-error">{error}</p>}
          {saved && <p className="text-sm text-success">Profile saved.</p>}
          <Button type="submit" disabled={!resume || !github || loading}>
            {loading ? 'Saving...' : 'Save Profile'}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
