/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        background: '#020208',
        accent: '#7c3aed',
        'accent-light': '#a855f7',
        cyan: '#00e5ff',
        'cyan-dim': '#00b8cc',
        surface: 'rgba(255,255,255,0.04)',
        'surface-hover': 'rgba(255,255,255,0.07)',
        border: 'rgba(255,255,255,0.08)',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      keyframes: {
        slideIn: {
          '0%': { transform: 'translateX(100%)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        pulse_glow: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.4' },
        },
        gradient_shift: {
          '0%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
          '100%': { backgroundPosition: '0% 50%' },
        },
        heartbeat: {
          '0%, 100%': { transform: 'scale(1)' },
          '14%': { transform: 'scale(1.3)' },
          '28%': { transform: 'scale(1)' },
          '42%': { transform: 'scale(1.3)' },
          '70%': { transform: 'scale(1)' },
        },
        border_glow: {
          '0%, 100%': { borderColor: 'rgba(124, 58, 237, 0.2)' },
          '50%': { borderColor: 'rgba(124, 58, 237, 0.5)' },
        },
      },
      animation: {
        'slide-in': 'slideIn 0.3s ease-out',
        'pulse-glow': 'pulse_glow 2s ease-in-out infinite',
        'gradient-shift': 'gradient_shift 6s ease infinite',
        'heartbeat': 'heartbeat 1.4s ease-in-out infinite',
        'border-glow': 'border_glow 3s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
