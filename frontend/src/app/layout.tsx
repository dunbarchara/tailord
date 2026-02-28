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
  icons: {
    icon: [
      { url: '/favicon.svg', type: 'image/svg+xml' },
      { url: '/favicon.ico' },
    ],
  },
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
