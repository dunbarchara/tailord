import type { Config } from "tailwindcss"

const config: Config = {
  //darkMode: "class", // enable dark mode via 'class'
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Brand colors
        brand: {
          primary: 'var(--color-brand-primary)',
          secondary: 'var(--color-brand-secondary)',
          accent: 'var(--color-brand-accent)',
        },
        // Surface colors
        surface: {
          base: 'var(--color-surface-base)',
          elevated: 'var(--color-surface-elevated)',
          overlay: 'var(--color-surface-overlay)',
        },
        // Text colors
        text: {
          primary: 'var(--color-text-primary)',
          secondary: 'var(--color-text-secondary)',
          tertiary: 'var(--color-text-tertiary)',
          inverse: 'var(--color-text-inverse)',
        },
        // Border colors
        border: {
          default: 'var(--color-border-default)',
          subtle: 'var(--color-border-subtle)',
          strong: 'var(--color-border-strong)',
        },
      },
      borderRadius: {
        'card': 'var(--radius-card)',
        'button': 'var(--radius-button)',
      },
    },
  },
  /*theme: {
    extend: {
      colors: {
        shark: {
          50: '#F4F4F4',
          100: '#E8E8E8',
          200: '#C7C6C6',
          300: '#A5A4A4',
          400: '#616060',
          500: '#1D1C1C',
          600: '#1A1919',
          700: '#111111',
          800: '#0D0D0D',
          900: '#090808',
        },
        concrete: {
          50: '#FEFEFE',
          100: '#FEFEFE',
          200: '#FCFCFC',
          300: '#FAFAFA',
          400: '#F6F6F6',
          500: '#F2F2F2',
          600: '#DADADA',
          700: '#919191',
          800: '#6D6D6D',
          900: '#494949',
        },
        gold: {
          50: '#FFFDF3',
          100: '#FEFAE6',
          200: '#FDF3C1',
          300: '#FCEC9B',
          400: '#FADE50',
          500: '#F8D005',
          600: '#DFBB05',
          700: '#957D03',
          800: '#705E02',
          900: '#4A3E02',
        },
        stack: {
          50: '#F9F9F9',
          100: '#F4F4F4',
          200: '#E3E3E3',
          300: '#D1D2D1',
          400: '#AFB0AF',
          500: '#8D8E8D',
          600: '#7F807F',
          700: '#555555',
          800: '#3F403F',
          900: '#2A2B2A',
        },
      },
    },
  },*/
}

export default config
