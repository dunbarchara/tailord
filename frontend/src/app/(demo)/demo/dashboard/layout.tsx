import Link from 'next/link';
import { MockProvider } from '@/mock/context';
import { getMockTailorings } from '@/mock/loader';
import { Sidebar } from '@/components/dashboard/Sidebar';

export default function DemoLayout({ children }: { children: React.ReactNode }) {
  return (
    <MockProvider>
      <div
        className="flex flex-col h-screen bg-surface-base overflow-hidden"
        style={{ fontFamily: "ui-sans-serif, system-ui, sans-serif, 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol', 'Noto Color Emoji'", WebkitFontSmoothing: 'antialiased' }}
      >
        {/* Demo Banner */}
        <div className="shrink-0 flex items-center justify-between gap-4 px-4 py-2.5 bg-brand-primary border-b border-border-default text-sm text-text-inverse">
          <span className="flex items-center gap-2">
            <span>◆</span>
            <span>
              <span className="font-medium">Demo mode</span>
              {" — "}
              You&apos;re viewing a read-only dashboard for{" "}
              <span className="font-medium">Charles Dunbar</span>
              {", a software engineer with 5+ years of experience at Microsoft."}
            </span>
          </span>
          <Link
            href="/register"
            className="shrink-0 font-medium hover:underline underline-offset-2"
          >
            Create an account to get started →
          </Link>
        </div>

        {/* Sidebar + content */}
        <div className="flex flex-1 overflow-hidden">
          <Sidebar tailorings={getMockTailorings()} isMock basePath="/demo/dashboard" />
          <main className="flex-1 overflow-y-auto">{children}</main>
        </div>
      </div>
    </MockProvider>
  );
}
