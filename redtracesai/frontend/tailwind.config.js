/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#080b0f",
        panel: "#0d1218",
        line: "#1d2833",
        signal: "#56f2c3",
        cyan: "#5bd6ff",
      },
      fontFamily: {
        sans: ["Manrope", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      boxShadow: {
        signal: "0 0 28px rgba(86, 242, 195, 0.08)",
      },
    },
  },
  plugins: [],
};
