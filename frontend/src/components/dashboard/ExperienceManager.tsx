'use client';

import { useState, useRef } from 'react';
import { Upload, Github, FileText } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

type SaveState = 'idle' | 'saving' | 'saved';

export function ExperienceManager() {
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [resumeState, setResumeState] = useState<SaveState>('idle');

  const [githubUrl, setGithubUrl] = useState('');
  const [githubState, setGithubState] = useState<SaveState>('idle');

  const [directText, setDirectText] = useState('');
  const [directState, setDirectState] = useState<SaveState>('idle');

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleResumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setResumeFile(file);
    setResumeState('saving');
    // TODO: POST to /api/profile with file
    setTimeout(() => setResumeState('saved'), 800);
  };

  const handleGithubSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (!githubUrl.trim()) return;
    setGithubState('saving');
    // TODO: POST to /api/profile with github_url
    setTimeout(() => setGithubState('saved'), 800);
  };

  const handleDirectSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (!directText.trim()) return;
    setDirectState('saving');
    // TODO: POST to /api/profile with manual_text
    setTimeout(() => setDirectState('saved'), 800);
  };

  return (
    <div className="h-full overflow-y-auto custom-scrollbar">
      <div className="max-w-2xl mx-auto p-6 lg:p-8 space-y-8">
        <div>
          <h1 className="text-2xl font-semibold text-text-primary">My Experience</h1>
          <p className="mt-1 text-text-secondary">
            Add your background using one or more sources — we&apos;ll combine them.
          </p>
        </div>

        {/* Resume */}
        <section className="space-y-3">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-text-tertiary" />
            <h2 className="text-sm font-medium text-text-primary">Resume</h2>
            {resumeState === 'saved' && (
              <span className="text-xs text-success ml-auto">Saved</span>
            )}
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.doc,.docx,.txt"
            className="hidden"
            onChange={handleResumeChange}
          />
          {resumeFile ? (
            <div className="flex items-center justify-between px-4 py-3 rounded-lg border border-border-subtle bg-surface-elevated">
              <span className="text-sm text-text-primary truncate">{resumeFile.name}</span>
              <button
                onClick={() => { setResumeFile(null); setResumeState('idle'); }}
                className="text-xs text-text-tertiary hover:text-text-secondary ml-4 flex-shrink-0"
              >
                Remove
              </button>
            </div>
          ) : (
            <button
              onClick={() => fileInputRef.current?.click()}
              className="w-full px-4 py-8 rounded-lg border border-dashed border-border-default hover:border-brand-primary/50 bg-surface-elevated hover:bg-surface-overlay transition-colors text-center"
            >
              <Upload className="h-5 w-5 text-text-tertiary mx-auto mb-2" />
              <p className="text-sm text-text-secondary">Click to upload resume</p>
              <p className="text-xs text-text-tertiary mt-1">PDF, DOCX, or TXT</p>
            </button>
          )}
        </section>

        {/* GitHub */}
        <section className="space-y-3">
          <div className="flex items-center gap-2">
            <Github className="h-4 w-4 text-text-tertiary" />
            <h2 className="text-sm font-medium text-text-primary">GitHub Profile</h2>
            {githubState === 'saved' && (
              <span className="text-xs text-success ml-auto">Saved</span>
            )}
          </div>
          <form onSubmit={handleGithubSave} className="flex gap-2">
            <Input
              type="url"
              value={githubUrl}
              onChange={(e) => { setGithubUrl(e.target.value); setGithubState('idle'); }}
              placeholder="https://github.com/username"
            />
            <Button
              type="submit"
              variant="outline"
              size="sm"
              disabled={!githubUrl.trim() || githubState === 'saving'}
              className="flex-shrink-0"
            >
              {githubState === 'saving' ? 'Saving…' : 'Save'}
            </Button>
          </form>
        </section>

        {/* Direct input */}
        <section className="space-y-3">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-text-tertiary" />
            <h2 className="text-sm font-medium text-text-primary">Additional Context</h2>
            {directState === 'saved' && (
              <span className="text-xs text-success ml-auto">Saved</span>
            )}
          </div>
          <form onSubmit={handleDirectSave} className="space-y-2">
            <textarea
              value={directText}
              onChange={(e) => { setDirectText(e.target.value); setDirectState('idle'); }}
              placeholder="Describe your skills, projects, or achievements not captured in your resume…"
              rows={6}
              className="w-full px-3 py-2 rounded-md border border-input bg-background text-sm text-text-primary placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-none"
            />
            <div className="flex justify-end">
              <Button
                type="submit"
                variant="outline"
                size="sm"
                disabled={!directText.trim() || directState === 'saving'}
              >
                {directState === 'saving' ? 'Saving…' : 'Save'}
              </Button>
            </div>
          </form>
        </section>
      </div>
    </div>
  );
}
