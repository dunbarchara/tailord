'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useTheme } from './ThemeProvider';
import { Moon, Sun, Menu, X } from 'lucide-react';

export function Header() {
  const { theme, setTheme, darkMode, setDarkMode, toggleTheme } = useTheme();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border-subtle bg-surface-elevated/80 backdrop-blur-xl">
      <nav className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4 lg:px-8">
        {/* Logo */}
        <div className="flex lg:flex-1">
          <Link href="/" className="-m-1.5 p-1.5 flex items-center gap-2 group">
            <div className="h-7 w-7 rounded-md bg-brand-primary flex items-center justify-center transition-transform group-hover:scale-105">
              <span className="text-text-inverse font-semibold text-sm">T</span>
            </div>
            <span className="text-lg font-semibold text-text-primary">Tailord</span>
          </Link>
        </div>

        {/* Mobile menu button */}
        <div className="flex lg:hidden gap-3 items-center">
          <button
            onClick={toggleTheme}
            className="p-2 rounded-md hover:bg-surface-overlay transition-colors"
            aria-label="Toggle theme"
          >
            {theme === 'tailord' ? (
              <Sun className="h-5 w-5 text-text-secondary" />
            ) : (
              <Moon className="h-5 w-5 text-text-secondary" />
            )}
          </button>
          <button
            type="button"
            className="p-2 rounded-md text-text-secondary hover:bg-surface-overlay"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          >
            <span className="sr-only">Open main menu</span>
            {mobileMenuOpen ? (
              <X className="h-6 w-6" />
            ) : (
              <Menu className="h-6 w-6" />
            )}
          </button>
        </div>

        {/* Desktop navigation */}
        <div className="hidden lg:flex lg:gap-x-8 items-center">
          <Link href="/product" className="text-sm font-medium text-text-secondary hover:text-text-primary transition-colors">
            Product
          </Link>
          <Link href="/research" className="text-sm font-medium text-text-secondary hover:text-text-primary transition-colors">
            Research
          </Link>
          <Link href="/company" className="text-sm font-medium text-text-secondary hover:text-text-primary transition-colors">
            Company
          </Link>
          <Link href="/news" className="text-sm font-medium text-text-secondary hover:text-text-primary transition-colors">
            News
          </Link>
        </div>

            
        {/* Desktop actions */}
        <div className="hidden lg:flex lg:flex-1 lg:justify-end lg:gap-x-4 items-center">
            {/* Theme Toggle */}


            <div className=" rounded-md hover:bg-surface-overlay transition-colors">
              <button
                onClick={() => setTheme('tailord')}
                className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                  theme === 'tailord'
                    ? 'bg-brand-primary text-text-inverse shadow-md'
                    : 'text-text-tertiary hover:text-text-secondary'
                }`}
                aria-label="TailorD theme"
              >
                Tailord
              </button>
              <button
                onClick={() => setTheme('claude')}
                className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                  theme === 'claude'
                    ? 'bg-brand-primary text-text-inverse shadow-md'
                    : 'text-text-tertiary hover:text-text-secondary'
                }`}
                aria-label="TailorD theme"
              >
                Claude
              </button>
              <button
                onClick={() => setTheme('hollow')}
                className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                  theme === 'hollow'
                    ? 'bg-brand-primary text-text-inverse shadow-md'
                    : 'text-text-tertiary hover:text-text-secondary'
                }`}
                aria-label="TailorD theme"
              >
                Hollow
              </button>
            </div>
          <button
              onClick={() => setDarkMode(!darkMode)}
            className="p-2 rounded-md hover:bg-surface-overlay transition-colors"
            aria-label="Toggle theme"
          >
            {darkMode ? (
              <Sun className="h-5 w-5 text-text-secondary" />
            ) : (
              <Moon className="h-5 w-5 text-text-secondary" />
            )}
          </button>
          <Link
            href="/login"
            className="text-sm font-medium text-text-secondary hover:text-text-primary transition-colors px-3 py-2"
          >
            Log in
          </Link>
          <Link
            href="/signup"
            className="text-sm font-medium text-text-inverse bg-brand-primary hover:bg-brand-primary-hover rounded-md px-4 py-2 transition-colors shadow-sm"
          >
            Get started
          </Link>
        </div>
      </nav>

      {/* Mobile menu */}
      {mobileMenuOpen && (
        <div className="lg:hidden border-t border-border-subtle animate-fade-in">
          <div className="space-y-1 px-6 py-4">
            <Link
              href="/product"
              className="block px-3 py-2 text-base font-medium text-text-secondary hover:text-text-primary hover:bg-surface-overlay rounded-md transition-colors"
            >
              Product
            </Link>
            <Link
              href="/research"
              className="block px-3 py-2 text-base font-medium text-text-secondary hover:text-text-primary hover:bg-surface-overlay rounded-md transition-colors"
            >
              Research
            </Link>
            <Link
              href="/company"
              className="block px-3 py-2 text-base font-medium text-text-secondary hover:text-text-primary hover:bg-surface-overlay rounded-md transition-colors"
            >
              Company
            </Link>
            <Link
              href="/news"
              className="block px-3 py-2 text-base font-medium text-text-secondary hover:text-text-primary hover:bg-surface-overlay rounded-md transition-colors"
            >
              News
            </Link>
            <div className="pt-4 border-t border-border-subtle mt-4">
              <Link
                href="/login"
                className="block px-3 py-2 text-base font-medium text-text-secondary hover:text-text-primary hover:bg-surface-overlay rounded-md transition-colors"
              >
                Log in
              </Link>
              <Link
                href="/signup"
                className="mt-2 block px-4 py-2.5 text-base font-medium text-text-inverse bg-brand-primary hover:bg-brand-primary-hover rounded-md transition-colors text-center"
              >
                Get started
              </Link>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
