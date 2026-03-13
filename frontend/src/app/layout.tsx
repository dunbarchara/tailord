import type { Metadata } from 'next';
import { GFS_Didot } from 'next/font/google';
import './globals.css';
import ClientWrapper from "@/components/ClientWrapper"

const gfsDidot = GFS_Didot({
  weight: '400',
  subsets: ['latin'],
  variable: '--font-serif-display',
});

export const metadata: Metadata = {
  title: 'Tailord',
  description: 'Let Tailord showcase your relevant experience.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning className={gfsDidot.variable}>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  const theme = localStorage.getItem('theme') || 'tailord';
                  document.documentElement.setAttribute('data-theme', theme);
                  if (!window.location.pathname.startsWith('/t/')) {
                    const stored = localStorage.getItem('darkMode');
                    const dark = stored !== null ? stored === 'true' : window.matchMedia('(prefers-color-scheme: dark)').matches;
                    if (dark) document.documentElement.classList.add('dark');
                  }
                } catch (e) {}
              })();
            `,
          }}
        />
      </head>
      <body className="antialiased">
        {/* ClientWrapper handles SessionProvider */}
        <ClientWrapper>{children}</ClientWrapper>
      </body>
    </html>
  );
}
