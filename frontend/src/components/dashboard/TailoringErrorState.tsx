'use client';

import { AlertCircle } from 'lucide-react';

interface TailoringErrorStateProps {
  message: string;
  jobUrl?: string | null;
}

export function TailoringErrorState({ message, jobUrl }: TailoringErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 max-w-xs mx-auto px-6 py-16 text-center">
      <div className="flex items-center justify-center h-10 w-10 rounded-full bg-red-50 dark:bg-red-950/20">
        <AlertCircle className="h-5 w-5 text-error" />
      </div>
      <div className="space-y-1">
        {jobUrl && (
          <p className="text-sm text-text-secondary">
            Processing failed for{' '}
            <a
              href={jobUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-text-link hover:underline"
            >
              this posting
            </a>
            .
          </p>
        )}
        <p className="text-sm text-text-secondary leading-relaxed">{message}</p>
      </div>
    </div>
  );
}
