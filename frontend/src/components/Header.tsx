'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useTheme } from './ThemeProvider';
import { Moon, Sun, Menu, X } from 'lucide-react';
import { useSession, signOut } from "next-auth/react"
import { Button } from '@/components/ui/button';

export function Header() {
    const { data: session, status } = useSession()
    const { darkMode, setDarkMode } = useTheme();
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

    if (status === "loading") return null

    return (
        <header className="sticky top-0 z-50 w-full border-b border-border-subtle bg-surface-elevated/80 backdrop-blur-xl">
            <nav className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4 lg:px-8">
                {/* Logo */}
                <div className="flex lg:flex-1">
                    <Link href="/" className="-m-1.5 p-1.5 flex items-center gap-2 group">
                        <img src="/logo.svg" alt="Tailord logo" className="h-8 w-8 dark:invert transition-transform group-hover:scale-105" />
                        <span className="text-2xl font-display text-text-primary">Tailord</span>
                    </Link>
                </div>

                {/* Mobile menu button */}
                <div className="flex lg:hidden gap-3 items-center">
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setDarkMode(!darkMode)}
                        aria-label="Toggle theme"
                    >
                        {darkMode ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
                    </Button>
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                    >
                        <span className="sr-only">Open main menu</span>
                        {mobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
                    </Button>
                </div>

                {/* Desktop actions */}
                <div className="hidden lg:flex lg:flex-1 lg:justify-end lg:gap-x-4 items-center">
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setDarkMode(!darkMode)}
                        aria-label="Toggle theme"
                    >
                        {darkMode ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
                    </Button>

                    {session ? (
                        <>
                            <Button
                                variant="ghost"
                                onClick={() => signOut({ callbackUrl: "/" })}
                            >
                                Sign out
                            </Button>
                            <Button asChild>
                                {session.user.status === "approved"
                                    ? <Link href="/dashboard">Dashboard</Link>
                                    : <Link href="/pending">Pending</Link>
                                }
                            </Button>
                        </>
                    ) : (
                        <>
                            <Button variant="ghost" asChild>
                                <Link href="/login">Log in</Link>
                            </Button>
                            <Button asChild>
                                <Link href="/register">Get started</Link>
                            </Button>
                        </>
                    )}
                </div>
            </nav>

            {/* Mobile menu */}
            {mobileMenuOpen && (
                <div className="lg:hidden border-t border-border-subtle animate-fade-in">
                    <div className="space-y-1 px-6 py-4">
                        {session ? (
                            <>
                                <Button variant="ghost" className="w-full justify-start" onClick={() => signOut({ callbackUrl: "/" })}>
                                    Sign out
                                </Button>
                                <Button className="w-full mt-2" asChild>
                                    {session.user.status === "approved"
                                        ? <Link href="/dashboard">Dashboard</Link>
                                        : <Link href="/pending">Pending</Link>
                                    }
                                </Button>
                            </>
                        ) : (
                            <>
                                <Button variant="ghost" className="w-full justify-start" asChild>
                                    <Link href="/login">Log in</Link>
                                </Button>
                                <Button className="w-full mt-2" asChild>
                                    <Link href="/register">Get started</Link>
                                </Button>
                            </>
                        )}
                    </div>
                </div>
            )}
        </header>
    );
}
