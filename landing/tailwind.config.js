/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx,mdx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // ── TG1.AI brand palette ────────────────────────────────────
        brand: {
          // Primary blue — Self-Serve product accent
          blue: {
            50:  '#EFF6FF',
            100: '#DBEAFE',
            200: '#BFDBFE',
            300: '#93C5FD',
            400: '#3B82F6',
            500: '#0066FF', // TG1 hero blue
            600: '#0052CC',
            700: '#003D99',
            800: '#002B6E',
            900: '#001A45',
          },
          // Purple — AI Marketing Assistant accent
          purple: {
            50:  '#FAF5FF',
            100: '#F3E8FF',
            200: '#E9D5FF',
            300: '#D8B4FE',
            400: '#C084FC',
            500: '#A855F7',
            600: '#9333EA',
            700: '#7E22CE',
            800: '#6B21A8',
            900: '#581C87',
          },
          // Ink — text + surfaces
          ink: {
            50:  '#F8FAFC',
            100: '#F1F5F9',
            200: '#E2E8F0',
            300: '#CBD5E1',
            400: '#94A3B8',
            500: '#64748B',
            600: '#475569',
            700: '#334155',
            800: '#1E293B',
            900: '#0F172A',
            950: '#020617',
          },
        },
        surface: {
          1: '#0A0F1E',  // L1 — sits between ink-950 (#020617) and ink-900 (#0F172A)
        },
        fg: {
          primary:   '#F0F2F8',
          secondary: '#8B92A8',
          muted:     '#5B6178',
        },
        line: {
          subtle: 'rgba(255,255,255,0.08)',
          strong: 'rgba(255,255,255,0.14)',
        },
        success: '#22C55E',
        warning: '#F59E0B',
        danger:  '#EF4444',
      },
      fontFamily: {
        // Display headlines (hero / section titles)
        display: ['Manrope', 'ui-sans-serif', 'system-ui', '-apple-system', 'sans-serif'],
        // Body
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
        // Code / pricing / numbers
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      },
      fontSize: {
        'display-1': ['clamp(2.5rem, 6vw, 4.5rem)', { lineHeight: '1.05', letterSpacing: '-0.03em', fontWeight: '700' }],
        'display-2': ['clamp(2rem, 4vw, 3rem)',     { lineHeight: '1.1',  letterSpacing: '-0.02em', fontWeight: '700' }],
        'display-3': ['clamp(1.5rem, 3vw, 2rem)',   { lineHeight: '1.2',  letterSpacing: '-0.01em', fontWeight: '600' }],
        'eyebrow':   ['0.75rem',                    { lineHeight: '1',    letterSpacing: '0.12em',  fontWeight: '600' }],
      },
      maxWidth: {
        container: '1280px',
      },
      backgroundImage: {
        'grad-hero-blue':   'linear-gradient(135deg, #0066FF 0%, #0052CC 100%)',
        'grad-hero-purple': 'linear-gradient(135deg, #A855F7 0%, #7E22CE 100%)',
        'grad-hero-mixed':  'linear-gradient(135deg, #0066FF 0%, #A855F7 100%)',
        'grad-radial-dark': 'radial-gradient(ellipse at top, #1E293B 0%, #020617 60%)',
        'noise':            "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence baseFrequency='.9' numOctaves='2' stitchTiles='stitch'/%3E%3CfeColorMatrix values='0 0 0 0 1 0 0 0 0 1 0 0 0 0 1 0 0 0 0.03 0'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")",
      },
      boxShadow: {
        'card':       '0 1px 2px rgba(15, 23, 42, 0.04), 0 4px 16px rgba(15, 23, 42, 0.06)',
        'card-hover': '0 4px 8px rgba(15, 23, 42, 0.06), 0 12px 32px rgba(15, 23, 42, 0.12)',
        'glow-blue':  '0 0 0 1px rgba(0,102,255,0.2), 0 8px 24px rgba(0,102,255,0.18)',
        'glow-purple':'0 0 0 1px rgba(168,85,247,0.22), 0 8px 24px rgba(168,85,247,0.20)',
      },
      animation: {
        'fade-up':      'fadeUp 0.6s cubic-bezier(0.22, 1, 0.36, 1) both',
        'pulse-soft':   'pulseSoft 2.4s ease-in-out infinite',
        'aurora-drift': 'auroraDrift 80s ease-in-out infinite',
        'aurora-drift-2': 'auroraDrift2 90s ease-in-out infinite',
        'shimmer':      'shimmer 700ms ease-in-out',
        'count-fade':   'fadeIn 0.4s ease-out both',
      },
      keyframes: {
        fadeUp:    { '0%': { opacity: '0', transform: 'translateY(16px)' }, '100%': { opacity: '1', transform: 'translateY(0)' } },
        pulseSoft: { '0%,100%': { opacity: '1' }, '50%': { opacity: '0.5' } },
        auroraDrift: {
          '0%, 100%': { transform: 'translate3d(0, 0, 0)' },
          '50%':      { transform: 'translate3d(40px, -30px, 0)' },
        },
        auroraDrift2: {
          '0%, 100%': { transform: 'translate3d(0, 0, 0)' },
          '50%':      { transform: 'translate3d(-30px, 40px, 0)' },
        },
        shimmer: {
          '0%':   { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        fadeIn: {
          '0%':   { opacity: '0' },
          '100%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
};
