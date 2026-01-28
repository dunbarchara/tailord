'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

type Theme = 'tailord' | 'claude' | 'hollow' ;

interface ThemeContextType {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  darkMode: boolean;
  setDarkMode: (darkMode: boolean) => void;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>('tailord');
  const [darkMode, setDarkMode] = useState(false);
  const [mounted, setMounted] = useState(false);

  // Load preferences from localStorage on mount
  useEffect(() => {
    setMounted(true);
    const savedTheme = localStorage.getItem('theme') as Theme | null;
    const savedDarkMode = localStorage.getItem('darkMode') === 'true';

    if (savedTheme) {
      setTheme(savedTheme);
    }
    setDarkMode(savedDarkMode);
  }, []);

  // Apply theme and dark mode to document
  useEffect(() => {
    if (mounted) {
      // Set theme
      document.documentElement.setAttribute('data-theme', theme);
      localStorage.setItem('theme', theme);

      // Set dark mode
      if (darkMode) {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
      localStorage.setItem('darkMode', darkMode.toString());
    }
  }, [theme, darkMode, mounted]);

  const toggleTheme = () => {
    //setTheme(prev => prev === 'claude-light' ? 'claude-dark' : 'claude-light');
  };

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