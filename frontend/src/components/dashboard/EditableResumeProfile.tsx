'use client';

import { useState } from 'react';
import type { ExtractedProfile } from '@/types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { X, Plus } from 'lucide-react';

interface Props {
  profile: ExtractedProfile;
  onSave: (profile: ExtractedProfile) => Promise<void>;
  onCancel: () => void;
}

// ─── Shared primitives ────────────────────────────────────────────────────────

function FieldRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2">
      <span className="text-xs text-text-tertiary w-20 flex-shrink-0 pt-1.5">{label}</span>
      <div className="flex-1">{children}</div>
    </div>
  );
}

function SmallInput({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <input
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className="w-full text-xs bg-transparent border-b border-border-subtle hover:border-border-default focus:border-brand-primary outline-none py-0.5 text-text-primary placeholder:text-text-disabled transition-colors"
    />
  );
}

function SmallTextarea({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      rows={3}
      className="w-full text-xs bg-transparent border border-border-subtle rounded px-2 py-1.5 hover:border-border-default focus:border-brand-primary outline-none text-text-primary placeholder:text-text-disabled transition-colors resize-none"
    />
  );
}

function TagInput({
  tags,
  onChange,
  placeholder = 'Add...',
}: {
  tags: string[];
  onChange: (t: string[]) => void;
  placeholder?: string;
}) {
  const [input, setInput] = useState('');

  const add = () => {
    const val = input.trim();
    if (val && !tags.includes(val)) onChange([...tags, val]);
    setInput('');
  };

  return (
    <div className="flex flex-wrap gap-1.5 items-center min-h-6">
      {tags.map((t, i) => (
        <span
          key={i}
          className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-surface-sunken border border-border-subtle text-xs text-text-secondary"
        >
          {t}
          <button
            type="button"
            onClick={() => onChange(tags.filter((_, j) => j !== i))}
            className="text-text-tertiary hover:text-error leading-none"
          >
            ×
          </button>
        </span>
      ))}
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') { e.preventDefault(); add(); }
          if (e.key === 'Backspace' && !input && tags.length > 0) {
            onChange(tags.slice(0, -1));
          }
        }}
        onBlur={add}
        placeholder={placeholder}
        className="text-xs border-none outline-none bg-transparent text-text-primary placeholder:text-text-disabled w-20 min-w-0"
      />
    </div>
  );
}

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h4 className="text-xs font-semibold uppercase tracking-wider text-text-tertiary mb-3 pb-1 border-b border-border-subtle">
      {children}
    </h4>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export function EditableResumeProfile({ profile, onSave, onCancel }: Props) {
  const [draft, setDraft] = useState<ExtractedProfile>(() =>
    JSON.parse(JSON.stringify(profile))
  );
  const [saving, setSaving] = useState(false);

  const set = <K extends keyof ExtractedProfile>(key: K, value: ExtractedProfile[K]) =>
    setDraft((prev) => ({ ...prev, [key]: value }));

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave(draft);
    } finally {
      setSaving(false);
    }
  };

  // ── Work experience helpers ──
  const updateJob = (i: number, field: string, value: string) => {
    const next = [...draft.work_experience];
    next[i] = { ...next[i], [field]: value };
    set('work_experience', next);
  };
  const updateBullets = (i: number, bullets: string[]) => {
    const next = [...draft.work_experience];
    next[i] = { ...next[i], bullets };
    set('work_experience', next);
  };
  const removeJob = (i: number) =>
    set('work_experience', draft.work_experience.filter((_, j) => j !== i));
  const addJob = () =>
    set('work_experience', [
      ...draft.work_experience,
      { title: '', company: '', location: null, duration: '', bullets: [] },
    ]);

  // ── Education helpers ──
  const updateEdu = (i: number, field: string, value: string) => {
    const next = [...draft.education];
    next[i] = { ...next[i], [field]: value };
    set('education', next);
  };
  const removeEdu = (i: number) =>
    set('education', draft.education.filter((_, j) => j !== i));
  const addEdu = () =>
    set('education', [
      ...draft.education,
      { degree: '', institution: '', location: null, year: '', distinction: null },
    ]);

  return (
    <div className="text-xs space-y-6">

      {/* Personal */}
      <div>
        <SectionHeading>Personal</SectionHeading>
        <div className="space-y-2">
          <FieldRow label="Title">
            <SmallInput
              value={draft.title ?? ''}
              onChange={(v) => set('title', v || null)}
              placeholder="e.g. Software Engineer"
            />
          </FieldRow>
          <FieldRow label="Headline">
            <SmallInput
              value={draft.headline ?? ''}
              onChange={(v) => set('headline', v || null)}
              placeholder="e.g. Senior Software Engineer with 8 years in distributed systems"
            />
          </FieldRow>
          <FieldRow label="Summary">
            <SmallTextarea
              value={draft.summary}
              onChange={(v) => set('summary', v)}
              placeholder="Professional summary..."
            />
          </FieldRow>
          <FieldRow label="Location">
            <SmallInput
              value={draft.location ?? ''}
              onChange={(v) => set('location', v || null)}
              placeholder="e.g. New York, NY"
            />
          </FieldRow>
          <FieldRow label="Email">
            <SmallInput
              value={draft.email ?? ''}
              onChange={(v) => set('email', v || null)}
              placeholder="email@example.com"
            />
          </FieldRow>
          <FieldRow label="Phone">
            <SmallInput
              value={draft.phone ?? ''}
              onChange={(v) => set('phone', v || null)}
              placeholder="+1 (555) 000-0000"
            />
          </FieldRow>
          <FieldRow label="LinkedIn">
            <SmallInput
              value={draft.linkedin ?? ''}
              onChange={(v) => set('linkedin', v || null)}
              placeholder="linkedin.com/in/username"
            />
          </FieldRow>
        </div>
      </div>

      {/* Work Experience */}
      <div>
        <SectionHeading>Work Experience</SectionHeading>
        <div className="space-y-5">
          {draft.work_experience.map((job, i) => (
            <div key={i} className="pl-3 border-l border-border-subtle space-y-1.5">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-text-secondary">Role {i + 1}</span>
                <button
                  type="button"
                  onClick={() => removeJob(i)}
                  className="text-text-tertiary hover:text-error transition-colors"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <SmallInput value={job.title} onChange={(v) => updateJob(i, 'title', v)} placeholder="Title" />
                <SmallInput value={job.company} onChange={(v) => updateJob(i, 'company', v)} placeholder="Company" />
                <SmallInput value={job.location ?? ''} onChange={(v) => updateJob(i, 'location', v)} placeholder="Location" />
                <SmallInput value={job.duration} onChange={(v) => updateJob(i, 'duration', v)} placeholder="Duration" />
              </div>
              <div className="mt-2 space-y-1">
                {job.bullets.map((b, j) => (
                  <div key={j} className="flex items-center gap-1.5">
                    <span className="text-text-tertiary flex-shrink-0">·</span>
                    <input
                      type="text"
                      value={b}
                      onChange={(e) => {
                        const next = [...job.bullets];
                        next[j] = e.target.value;
                        updateBullets(i, next);
                      }}
                      className="flex-1 text-xs bg-transparent border-b border-transparent hover:border-border-subtle focus:border-brand-primary outline-none py-0.5 text-text-secondary transition-colors"
                    />
                    <button
                      type="button"
                      onClick={() => updateBullets(i, job.bullets.filter((_, k) => k !== j))}
                      className="text-text-tertiary hover:text-error flex-shrink-0"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() => updateBullets(i, [...job.bullets, ''])}
                  className="flex items-center gap-1 text-text-tertiary hover:text-text-secondary mt-1 ml-3"
                >
                  <Plus className="h-3 w-3" />
                  <span>Add bullet</span>
                </button>
              </div>
            </div>
          ))}
        </div>
        <button
          type="button"
          onClick={addJob}
          className="flex items-center gap-1 text-text-tertiary hover:text-text-secondary mt-3"
        >
          <Plus className="h-3 w-3" />
          <span>Add role</span>
        </button>
      </div>

      {/* Skills */}
      <div>
        <SectionHeading>Skills</SectionHeading>
        <div className="space-y-2">
          <FieldRow label="Technical">
            <TagInput
              tags={draft.skills.technical}
              onChange={(t) => set('skills', { ...draft.skills, technical: t })}
              placeholder="Add skill..."
            />
          </FieldRow>
          <FieldRow label="Soft">
            <TagInput
              tags={draft.skills.soft}
              onChange={(t) => set('skills', { ...draft.skills, soft: t })}
              placeholder="Add skill..."
            />
          </FieldRow>
        </div>
      </div>

      {/* Certifications */}
      <div>
        <SectionHeading>Certifications</SectionHeading>
        <TagInput
          tags={draft.certifications}
          onChange={(t) => set('certifications', t)}
          placeholder="Add..."
        />
      </div>

      {/* Education */}
      <div>
        <SectionHeading>Education</SectionHeading>
        <div className="space-y-4">
          {draft.education.map((edu, i) => (
            <div key={i} className="pl-3 border-l border-border-subtle">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs font-medium text-text-secondary">Degree {i + 1}</span>
                <button
                  type="button"
                  onClick={() => removeEdu(i)}
                  className="text-text-tertiary hover:text-error transition-colors"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <SmallInput value={edu.degree} onChange={(v) => updateEdu(i, 'degree', v)} placeholder="Degree" />
                <SmallInput value={edu.institution} onChange={(v) => updateEdu(i, 'institution', v)} placeholder="Institution" />
                <SmallInput value={edu.location ?? ''} onChange={(v) => updateEdu(i, 'location', v)} placeholder="Location" />
                <SmallInput value={edu.year} onChange={(v) => updateEdu(i, 'year', v)} placeholder="Year" />
                <div className="col-span-2">
                  <SmallInput value={edu.distinction ?? ''} onChange={(v) => updateEdu(i, 'distinction', v)} placeholder="Distinction / GPA" />
                </div>
              </div>
            </div>
          ))}
        </div>
        <button
          type="button"
          onClick={addEdu}
          className="flex items-center gap-1 text-text-tertiary hover:text-text-secondary mt-3"
        >
          <Plus className="h-3 w-3" />
          <span>Add education</span>
        </button>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3 pt-3 border-t border-border-subtle">
        <Button size="sm" onClick={handleSave} disabled={saving}>
          {saving ? 'Saving...' : 'Save changes'}
        </Button>
        <button
          type="button"
          onClick={onCancel}
          className="text-xs text-text-tertiary hover:text-text-primary transition-colors"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
