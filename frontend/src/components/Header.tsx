'use client';

import { useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useTheme } from './ThemeProvider';
import { Moon, Sun, Menu, X } from 'lucide-react';
import { useSession, signOut } from 'next-auth/react';

export function Header() {
  const { data: session, status } = useSession();
  const { darkMode, setDarkMode } = useTheme();
  const [mobileOpen, setMobileOpen] = useState(false);

  if (status === 'loading') return null;

  return (
    <header className="fixed top-0 left-0 right-0 z-50 w-full bg-surface-elevated dark:bg-surface-base">
      <nav className="mx-auto flex max-w-5xl items-center justify-between px-6 h-14">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-1 shrink-0">
          <Image src="/logo.svg" alt="" width={24} height={24} className="h-6 w-6" />
          <span className="text-[18px] font-semibold tracking-tight text-text-primary">Tailord</span>
        </Link>

        {/* Desktop actions */}
        <div className="hidden sm:flex items-center gap-1">
          <button
            onClick={() => setDarkMode(!darkMode)}
            className="rounded-full p-2 text-text-tertiary hover:text-text-primary hover:bg-surface-overlay transition-colors"
            aria-label="Toggle theme"
          >
            {darkMode ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>

          {session ? (
            <>
              <button
                onClick={() => signOut({ callbackUrl: '/' })}
                className="rounded-full px-3.5 py-1.5 text-sm font-medium text-text-secondary hover:text-text-primary hover:bg-surface-overlay transition-colors"
              >
                Sign out
              </button>
              <Link
                href="/dashboard"
                className="rounded-full px-3.5 py-1.5 text-sm font-medium bg-text-primary text-surface-base hover:opacity-90 transition-opacity"
              >
                Dashboard
              </Link>
            </>
          ) : (
            <>
              <Link
                href="/login"
                className="rounded-full px-3.5 py-1.5 text-sm font-medium text-text-secondary hover:text-text-primary hover:bg-surface-overlay transition-colors"
              >
                Sign in
              </Link>
              <Link
                href="/register"
                className="rounded-full px-3.5 py-1.5 text-sm font-medium bg-text-primary text-surface-base hover:opacity-90 transition-opacity"
              >
                Get started
              </Link>
            </>
          )}
        </div>

        {/* Mobile toggle */}
        <div className="flex sm:hidden items-center gap-1">
          <button
            onClick={() => setDarkMode(!darkMode)}
            className="rounded-full p-2 text-text-tertiary hover:text-text-primary hover:bg-surface-overlay transition-colors"
            aria-label="Toggle theme"
          >
            {darkMode ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="rounded-full p-2 text-text-tertiary hover:text-text-primary hover:bg-surface-overlay transition-colors"
          >
            <span className="sr-only">Menu</span>
            {mobileOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>
        </div>
      </nav>

      {/* Mobile menu */}
      {mobileOpen && (
        <div className="sm:hidden px-6 pb-3 pt-2 flex flex-col gap-1 border-t border-border-subtle animate-fade-in">
          {session ? (
            <>
              <button
                onClick={() => signOut({ callbackUrl: '/' })}
                className="rounded-full px-3.5 py-2 text-sm font-medium text-text-secondary hover:text-text-primary hover:bg-surface-overlay transition-colors text-left"
              >
                Sign out
              </button>
              <Link
                href="/dashboard"
                className="rounded-full px-3.5 py-2 text-sm font-medium bg-text-primary text-surface-base hover:opacity-90 transition-opacity text-center"
                onClick={() => setMobileOpen(false)}
              >
                Dashboard
              </Link>
            </>
          ) : (
            <>
              <Link
                href="/login"
                className="rounded-full px-3.5 py-2 text-sm font-medium text-text-secondary hover:text-text-primary hover:bg-surface-overlay transition-colors"
                onClick={() => setMobileOpen(false)}
              >
                Sign in
              </Link>
              <Link
                href="/register"
                className="rounded-full px-3.5 py-2 text-sm font-medium bg-text-primary text-surface-base hover:opacity-90 transition-opacity text-center"
                onClick={() => setMobileOpen(false)}
              >
                Get started
              </Link>
            </>
          )}
        </div>
      )}
    </header>
  );
}
