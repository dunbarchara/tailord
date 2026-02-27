import Link from 'next/link';
import { Plus, Briefcase, Sparkles } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';

export function EmptyState() {
  return (
    <div className="h-full flex items-center justify-center p-6">
      <div className="max-w-2xl text-center space-y-8 animate-fade-in">
        <div className="flex justify-center">
          <div className="relative">
            <div className="h-20 w-20 rounded-2xl bg-brand-primary/10 flex items-center justify-center">
              <Sparkles className="h-10 w-10 text-brand-primary" />
            </div>
            <div className="absolute -top-1 -right-1 h-6 w-6 rounded-full bg-brand-primary flex items-center justify-center">
              <Plus className="h-4 w-4 text-text-inverse" />
            </div>
          </div>
        </div>

        <div className="space-y-3">
          <h1 className="text-3xl font-semibold text-text-primary">Welcome to Tailord</h1>
          <p className="text-lg text-text-secondary">
            Start by adding your experience, then create your first tailored application
          </p>
        </div>

        <div className="grid sm:grid-cols-2 gap-4 pt-4">
          <Link href="/dashboard/experience">
            <Card className="group hover:shadow-md transition-all hover:border-brand-primary/50 cursor-pointer">
              <CardContent className="pt-6 flex flex-col items-center text-center space-y-3">
                <div className="h-12 w-12 rounded-lg bg-surface-overlay group-hover:bg-brand-primary/10 flex items-center justify-center transition-colors">
                  <Briefcase className="h-6 w-6 text-text-tertiary group-hover:text-brand-primary transition-colors" />
                </div>
                <div>
                  <h3 className="font-semibold text-text-primary mb-1">Add Your Experience</h3>
                  <p className="text-sm text-text-secondary">Upload resume or connect GitHub</p>
                </div>
              </CardContent>
            </Card>
          </Link>

          <Link href="/dashboard/tailorings/new">
            <Card className="group hover:shadow-md transition-all hover:border-brand-primary/50 cursor-pointer">
              <CardContent className="pt-6 flex flex-col items-center text-center space-y-3">
                <div className="h-12 w-12 rounded-lg bg-surface-overlay group-hover:bg-brand-primary/10 flex items-center justify-center transition-colors">
                  <Plus className="h-6 w-6 text-text-tertiary group-hover:text-brand-primary transition-colors" />
                </div>
                <div>
                  <h3 className="font-semibold text-text-primary mb-1">Create Tailoring</h3>
                  <p className="text-sm text-text-secondary">Paste a job posting URL</p>
                </div>
              </CardContent>
            </Card>
          </Link>
        </div>

        <p className="text-sm text-text-tertiary pt-4">
          Need help getting started?{' '}
          <a href="#" className="text-brand-primary hover:underline">
            View tutorial
          </a>
        </p>
      </div>
    </div>
  );
}
