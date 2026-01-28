'use client';

import { useTheme } from '@/components/ThemeProvider';
import { Moon, Sun, Bell } from 'lucide-react';

export function DashboardHeader() {
    const { theme, setTheme, darkMode, setDarkMode, toggleTheme } = useTheme();

    return (
        <header className="h-16 border-b border-border-subtle bg-surface-elevated/80 backdrop-blur-xl flex items-center justify-end px-6 gap-3">
            {/* Notifications */}
            <button
                className="p-2 rounded-lg hover:bg-surface-overlay transition-colors relative"
                aria-label="Notifications"
            >
                <Bell className="h-5 w-5 text-text-secondary" />
                <span className="absolute top-1.5 right-1.5 h-2 w-2 bg-brand-primary rounded-full" />
            </button>

            {/* Theme toggle */}
            <button
                onClick={() => setDarkMode(!darkMode)}
                className="p-2 rounded-md hover:bg-surface-overlay transition-colors"
                aria-label="Toggle theme"
            >
                {darkMode ? (<Sun className="h-5 w-5 text-text-secondary" />) : (<Moon className="h-5 w-5 text-text-secondary" />)}
            </button>
        </header>
    );
}
