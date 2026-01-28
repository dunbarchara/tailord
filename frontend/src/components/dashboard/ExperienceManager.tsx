'use client';

import { useState } from 'react';
import { Upload, Github, FileText, Plus, Trash2, Eye } from 'lucide-react';

type ExperienceSource = 'resume' | 'github' | 'manual';

interface Experience {
  id: string;
  type: ExperienceSource;
  title: string;
  date: string;
  status: 'active' | 'processing';
}

// Mock data
const mockExperiences: Experience[] = [
  { id: '1', type: 'resume', title: 'Resume_2024.pdf', date: '2 days ago', status: 'active' },
  { id: '2', type: 'github', title: 'GitHub Profile (johndoe)', date: '1 week ago', status: 'active' },
];

export function ExperienceManager() {
  const [experiences, setExperiences] = useState<Experience[]>(mockExperiences);
  const [uploadMethod, setUploadMethod] = useState<ExperienceSource | null>(null);

  const handleUpload = (type: ExperienceSource) => {
    setUploadMethod(type);
    // In production, this would open a file picker or GitHub OAuth flow
  };

  const handleDelete = (id: string) => {
    setExperiences(experiences.filter(exp => exp.id !== id));
  };

  const getIcon = (type: ExperienceSource) => {
    switch (type) {
      case 'resume':
        return FileText;
      case 'github':
        return Github;
      case 'manual':
        return Plus;
    }
  };

  return (
    <div className="h-full overflow-y-auto custom-scrollbar">
      <div className="max-w-5xl mx-auto p-6 lg:p-8 space-y-8">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-semibold text-text-primary mb-2">
            My Experience
          </h1>
          <p className="text-text-secondary">
            Manage your professional experience that will be used to generate tailored applications
          </p>
        </div>

        {/* Upload methods */}
        <div className="grid md:grid-cols-3 gap-4">
          <button
            onClick={() => handleUpload('resume')}
            className="group p-6 rounded-xl border border-border-default hover:border-brand-primary/50 bg-surface-elevated hover:shadow-md transition-all text-left"
          >
            <div className="flex items-start gap-4">
              <div className="h-12 w-12 rounded-lg bg-surface-overlay group-hover:bg-brand-primary/10 flex items-center justify-center flex-shrink-0 transition-colors">
                <Upload className="h-6 w-6 text-text-tertiary group-hover:text-brand-primary transition-colors" />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="font-semibold text-text-primary mb-1">
                  Upload Resume
                </h3>
                <p className="text-sm text-text-secondary">
                  PDF, DOCX, or TXT
                </p>
              </div>
            </div>
          </button>

          <button
            onClick={() => handleUpload('github')}
            className="group p-6 rounded-xl border border-border-default hover:border-brand-primary/50 bg-surface-elevated hover:shadow-md transition-all text-left"
          >
            <div className="flex items-start gap-4">
              <div className="h-12 w-12 rounded-lg bg-surface-overlay group-hover:bg-brand-primary/10 flex items-center justify-center flex-shrink-0 transition-colors">
                <Github className="h-6 w-6 text-text-tertiary group-hover:text-brand-primary transition-colors" />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="font-semibold text-text-primary mb-1">
                  Connect GitHub
                </h3>
                <p className="text-sm text-text-secondary">
                  Import from profile
                </p>
              </div>
            </div>
          </button>

          <button
            onClick={() => handleUpload('manual')}
            className="group p-6 rounded-xl border border-border-default hover:border-brand-primary/50 bg-surface-elevated hover:shadow-md transition-all text-left"
          >
            <div className="flex items-start gap-4">
              <div className="h-12 w-12 rounded-lg bg-surface-overlay group-hover:bg-brand-primary/10 flex items-center justify-center flex-shrink-0 transition-colors">
                <Plus className="h-6 w-6 text-text-tertiary group-hover:text-brand-primary transition-colors" />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="font-semibold text-text-primary mb-1">
                  Direct Input
                </h3>
                <p className="text-sm text-text-secondary">
                  Type manually
                </p>
              </div>
            </div>
          </button>
        </div>

        {/* Existing experiences */}
        {experiences.length > 0 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-text-primary">
              Your Experiences
            </h2>
            
            <div className="space-y-3">
              {experiences.map((exp) => {
                const Icon = getIcon(exp.type);
                
                return (
                  <div
                    key={exp.id}
                    className="p-4 rounded-lg border border-border-subtle bg-surface-elevated hover:border-border-default transition-colors"
                  >
                    <div className="flex items-start gap-4">
                      <div className="h-10 w-10 rounded-lg bg-surface-overlay flex items-center justify-center flex-shrink-0">
                        <Icon className="h-5 w-5 text-brand-primary" />
                      </div>
                      
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-4">
                          <div className="min-w-0">
                            <h3 className="font-medium text-text-primary truncate">
                              {exp.title}
                            </h3>
                            <p className="text-sm text-text-tertiary mt-0.5">
                              Added {exp.date}
                            </p>
                          </div>
                          
                          {exp.status === 'processing' && (
                            <span className="px-2 py-1 rounded-md bg-brand-primary/10 text-brand-primary text-xs font-medium">
                              Processing
                            </span>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-2 flex-shrink-0">
                        <button
                          className="p-2 rounded-md hover:bg-surface-overlay transition-colors"
                          title="View details"
                        >
                          <Eye className="h-4 w-4 text-text-secondary" />
                        </button>
                        <button
                          onClick={() => handleDelete(exp.id)}
                          className="p-2 rounded-md hover:bg-error-bg transition-colors"
                          title="Delete"
                        >
                          <Trash2 className="h-4 w-4 text-text-secondary hover:text-error" />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Help section */}
        <div className="p-6 rounded-xl bg-surface-overlay border border-border-subtle">
          <h3 className="font-semibold text-text-primary mb-2">
            Tips for better results
          </h3>
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
