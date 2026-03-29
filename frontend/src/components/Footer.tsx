import Link from 'next/link';

export function Footer() {
  return (
    <footer className="border-t border-border-subtle bg-surface-base">
      <div className="mx-auto max-w-5xl px-6 py-6 flex items-center justify-between">
        <p className="text-xs text-text-tertiary">
          &copy; {new Date().getFullYear()} Tailord
        </p>
        <div className="flex items-center gap-5">
          <Link href="/privacy" className="text-xs text-text-tertiary hover:text-text-secondary transition-colors">
            Privacy
          </Link>
          <Link href="/terms" className="text-xs text-text-tertiary hover:text-text-secondary transition-colors">
            Terms
          </Link>
        </div>
      </div>
    </footer>
  );
}
