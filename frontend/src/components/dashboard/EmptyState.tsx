import Link from 'next/link';
import { Button } from '@/components/ui/button';

export function EmptyState() {
  return (
    <div className="h-full flex items-center justify-center p-6">
      <div className="text-center space-y-6 max-w-sm animate-fade-in">
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold text-text-primary">Welcome to Tailord</h1>
          <p className="text-text-secondary">
            Add your experience, then paste a job URL to generate your first tailoring.
          </p>
        </div>
        <div className="flex gap-3 justify-center">
          <Button asChild variant="outline">
            <Link href="/dashboard/experience">Add Experience</Link>
          </Button>
          <Button asChild>
            <Link href="/dashboard/tailorings/new">New Tailoring</Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
