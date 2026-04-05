import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        surface: "var(--surface)",
        border: "var(--border)",
        body: "var(--body)",
        accent: "var(--accent)"
      },
      boxShadow: {
        panel: "var(--shadow)",
      },
      borderRadius: {
        "4xl": "2rem",
      }
    }
  },
  plugins: []
};

export default config;
