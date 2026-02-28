'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

type Theme = 'tailord' | 'claude' | 'hollow';

interface ThemeContextType {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  darkMode: boolean;
  setDarkMode: (darkMode: boolean) => void;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export function ThemeProvider({ children }: { children: ReactNode }) {
  // Lazy initializers read localStorage once on mount (no setState in effect needed)
  const [theme, setThemeState] = useState<Theme>(() => {
    if (typeof window === 'undefined') return 'tailord';
    return (localStorage.getItem('theme') as Theme | null) ?? 'tailord';
  });

  const [darkMode, setDarkModeState] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    return localStorage.getItem('darkMode') === 'true';
  });

  // Sync theme to document
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  // Sync dark mode to document
  useEffect(() => {
    document.documentElement.classList.toggle('dark', darkMode);
    localStorage.setItem('darkMode', String(darkMode));
  }, [darkMode]);

  const setTheme = (t: Theme) => setThemeState(t);
  const setDarkMode = (d: boolean) => setDarkModeState(d);
  const toggleTheme = () => {};

  return (
    <ThemeContext.Provider value={{ theme, setTheme, darkMode, setDarkMode, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
}
