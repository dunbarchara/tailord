import { MockProvider } from '@/mock/context';
import { getMockTailorings } from '@/mock/loader';
import { Sidebar } from '@/components/dashboard/Sidebar';

export default function DemoLayout({ children }: { children: React.ReactNode }) {
  return (
    <MockProvider>
      <div
        className="flex h-screen bg-surface-base overflow-hidden"
        style={{ fontFamily: "ui-sans-serif, system-ui, sans-serif, 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol', 'Noto Color Emoji'", WebkitFontSmoothing: 'antialiased' }}
      >
        <Sidebar tailorings={getMockTailorings()} isMock basePath="/demo/dashboard" />
        <main className="flex-1 overflow-y-auto">{children}</main>
      </div>
    </MockProvider>
  );
}
