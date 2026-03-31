import Link from 'next/link';
import { Briefcase, Plus } from 'lucide-react';

export function EmptyState() {
  return (
    <div className="h-full flex items-center justify-center p-6">
      <div className="text-center space-y-5 max-w-xs animate-fade-in">
        <div className="mx-auto h-12 w-12 rounded-[12px] bg-brand-accent-subtle flex items-center justify-center">
          <Briefcase className="h-5 w-5 text-brand-accent" />
        </div>
        <div className="space-y-1.5">
          <h1 className="text-[15px] font-semibold text-text-primary tracking-tight">Welcome to Tailord</h1>
          <p className="text-[13px] text-text-secondary leading-relaxed">
            Add your experience, then paste a job URL to generate your first tailoring.
          </p>
        </div>
        <div className="flex gap-2 justify-center">
          <Link
            href="/dashboard/experience"
            className="inline-flex items-center gap-1.5 h-8 px-3.5 rounded-full text-[13px] font-medium border border-border-default text-text-secondary hover:text-text-primary hover:border-border-strong transition-colors"
          >
            <Briefcase className="h-3.5 w-3.5" />
            Add Experience
          </Link>
          <Link
            href="/dashboard/tailorings/new"
            className="inline-flex items-center gap-1.5 h-8 px-3.5 rounded-full text-[13px] font-medium bg-text-primary text-surface-base hover:opacity-90 transition-opacity"
          >
            <Plus className="h-3.5 w-3.5" />
            New Tailoring
          </Link>
        </div>
      </div>
    </div>
  );
}
