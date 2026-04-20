'use client';

import { useState } from 'react';
import { CheckCircle2, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ProfileGap } from '@/types';

interface GapQuestionsProps {
  tailoringId: string;
  gaps: ProfileGap[];
}

export function GapQuestions({ tailoringId, gaps }: GapQuestionsProps) {
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [saving, setSaving] = useState<Record<number, boolean>>({});
  const [saved, setSaved] = useState<Record<number, boolean>>({});
  const [errors, setErrors] = useState<Record<number, string>>({});

  async function handleSave(index: number) {
    const answer = (answers[index] ?? '').trim();
    if (!answer) return;

    setSaving(prev => ({ ...prev, [index]: true }));
    setErrors(prev => ({ ...prev, [index]: '' }));

    try {
      const res = await fetch(`/api/tailorings/${tailoringId}/gap-answer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ gap_index: index, answer }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setErrors(prev => ({
          ...prev,
          [index]: data?.detail ?? 'Could not save. Please try again.',
        }));
        return;
      }

      setSaved(prev => ({ ...prev, [index]: true }));
    } catch {
      setErrors(prev => ({ ...prev, [index]: 'Could not reach the server.' }));
    } finally {
      setSaving(prev => ({ ...prev, [index]: false }));
    }
  }

  return (
    <div className="space-y-3">
      {gaps.map((gap, i) => (
        <div
          key={i}
          className="rounded-xl border border-border-default bg-surface-base p-4 space-y-3"
        >
          {/* Requirement heading */}
          <p className="text-sm font-medium text-text-primary leading-snug">
            {gap.job_requirement}
          </p>

          {/* Question */}
          <p className="text-sm text-text-secondary leading-relaxed">
            {gap.question_for_candidate}
          </p>

          {/* Context */}
          <p className="text-xs text-text-tertiary leading-relaxed">
            {gap.context}
          </p>

          {/* Answer area or saved confirmation */}
          {saved[i] ? (
            <div className="flex items-center gap-2 text-sm text-success">
              <CheckCircle2 className="h-4 w-4 shrink-0" />
              <span>
                Saved — your experience has been updated.{' '}
                <a
                  href="/dashboard/experience"
                  className="text-text-link hover:underline"
                >
                  View experience →
                </a>
              </span>
            </div>
          ) : (
            <div className="space-y-2">
              <textarea
                rows={4}
                placeholder="Share your experience here…"
                value={answers[i] ?? ''}
                onChange={e => setAnswers(prev => ({ ...prev, [i]: e.target.value }))}
                className={cn(
                  'w-full resize-none rounded-lg border border-border-default bg-surface-elevated',
                  'px-3 py-2 text-sm text-text-primary placeholder:text-text-disabled',
                  'focus:outline-none focus:ring-1 focus:ring-border-focus focus:border-border-focus',
                  'transition-colors'
                )}
              />

              {errors[i] && (
                <p className="text-xs text-error">{errors[i]}</p>
              )}

              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={() => handleSave(i)}
                  disabled={saving[i] || !(answers[i] ?? '').trim()}
                  className={cn(
                    'inline-flex items-center gap-1.5 h-8 px-3 rounded-[10px]',
                    'bg-brand-primary text-white text-sm font-normal tracking-[-0.1px]',
                    'hover:opacity-90 transition-opacity',
                    'disabled:opacity-40 disabled:cursor-not-allowed'
                  )}
                >
                  {saving[i] && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                  Save answer
                </button>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
