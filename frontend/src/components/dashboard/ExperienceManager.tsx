'use client';

import { useState } from 'react';
import { Upload, Github, FileText, Plus, Trash2, Eye } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

type ExperienceSource = 'resume' | 'github' | 'manual';

interface Experience {
  id: string;
  type: ExperienceSource;
  title: string;
  date: string;
  status: 'active' | 'processing';
}

const getIcon = (type: ExperienceSource) => {
  switch (type) {
    case 'resume': return FileText;
    case 'github': return Github;
    case 'manual': return Plus;
  }
};

export function ExperienceManager() {
  const [experiences, setExperiences] = useState<Experience[]>([]);

  const handleDelete = (id: string) => {
    setExperiences((prev) => prev.filter((exp) => exp.id !== id));
  };

  const uploadOptions: { type: ExperienceSource; icon: typeof Upload; title: string; desc: string }[] = [
    { type: 'resume', icon: Upload, title: 'Upload Resume', desc: 'PDF, DOCX, or TXT' },
    { type: 'github', icon: Github, title: 'Connect GitHub', desc: 'Import from profile' },
    { type: 'manual', icon: Plus, title: 'Direct Input', desc: 'Type manually' },
  ];

  return (
    <div className="h-full overflow-y-auto custom-scrollbar">
      <div className="max-w-5xl mx-auto p-6 lg:p-8 space-y-8">
        <div>
          <h1 className="text-2xl font-semibold text-text-primary mb-2">My Experience</h1>
          <p className="text-text-secondary">
            Manage your professional experience used to generate tailored applications
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-4">
          {uploadOptions.map(({ type, icon: Icon, title, desc }) => (
            <button
              key={type}
              className="group p-6 rounded-xl border border-border-default hover:border-brand-primary/50 bg-surface-elevated hover:shadow-md transition-all text-left"
            >
              <div className="flex items-start gap-4">
                <div className="h-12 w-12 rounded-lg bg-surface-overlay group-hover:bg-brand-primary/10 flex items-center justify-center flex-shrink-0 transition-colors">
                  <Icon className="h-6 w-6 text-text-tertiary group-hover:text-brand-primary transition-colors" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-text-primary mb-1">{title}</h3>
                  <p className="text-sm text-text-secondary">{desc}</p>
                </div>
              </div>
            </button>
          ))}
        </div>

        {experiences.length > 0 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-text-primary">Your Experiences</h2>
            <div className="space-y-3">
              {experiences.map((exp) => {
                const Icon = getIcon(exp.type);
                return (
                  <Card key={exp.id} className="border-border-subtle">
                    <CardContent className="p-4">
                      <div className="flex items-start gap-4">
                        <div className="h-10 w-10 rounded-lg bg-surface-overlay flex items-center justify-center flex-shrink-0">
                          <Icon className="h-5 w-5 text-brand-primary" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between gap-4">
                            <div className="min-w-0">
                              <h3 className="font-medium text-text-primary truncate">{exp.title}</h3>
                              <p className="text-sm text-text-tertiary mt-0.5">Added {exp.date}</p>
                            </div>
                            {exp.status === 'processing' && (
                              <Badge variant="secondary">Processing</Badge>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0">
                          <Button variant="ghost" size="icon" title="View details">
                            <Eye className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleDelete(exp.id)}
                            title="Delete"
                            className="hover:bg-error-bg hover:text-error"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          </div>
        )}

        <div className="p-6 rounded-xl bg-surface-overlay border border-border-subtle">
          <h3 className="font-semibold text-text-primary mb-2">Tips for better results</h3>
          <ul className="space-y-2 text-sm text-text-secondary">
            <li className="flex items-start gap-2">
              <span className="text-brand-primary mt-0.5">•</span>
              <span>Include all relevant work experience, even if not on your resume</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-brand-primary mt-0.5">•</span>
              <span>Keep your GitHub profile updated with your best projects</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-brand-primary mt-0.5">•</span>
              <span>Add specific achievements and metrics when possible</span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}
