/** Palette taken from the JobBox reference: royal blue, deep navy headings, pale blue surfaces. */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        brand: { DEFAULT: '#3C65F5', dark: '#2F54D8', soft: '#E0E6F7', tint: '#F2F6FD' },
        navy: '#05264E',
        ink: '#4F5E64',
        line: '#E0E6F7',
      },
      fontFamily: { sans: ['"Plus Jakarta Sans"', 'Inter', 'system-ui', 'sans-serif'] },
      boxShadow: { card: '0 4px 20px rgba(60, 101, 245, 0.07)', lift: '0 10px 30px rgba(60, 101, 245, 0.15)' },
    },
  },
  plugins: [],
}
