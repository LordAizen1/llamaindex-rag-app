import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#0a0e14",
          900: "#0f141c",
          800: "#161d28",
          700: "#1f2937",
          600: "#2b3648",
        },
        accent: {
          DEFAULT: "#5b9dff",
          soft: "#3b82f6",
        },
      },
    },
  },
  plugins: [],
};

export default config;
