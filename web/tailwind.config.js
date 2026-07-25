/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{js,jsx,ts,tsx}", "./components/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#EDECE7",
        surface: "#F7F6F2",
        ink: "#141414",
        muted: "#8C8A82",
        line: "#C9C7BC",
        accent: "#FF4B1F",
        danger: "#B23B2E",
      },
      fontFamily: {
        mono: ["IBM Plex Mono", "ui-monospace", "monospace"],
        sans: ["Inter", "ui-sans-serif", "system-ui"],
      },
      borderRadius: {
        DEFAULT: "2px",
      },
      boxShadow: {
        none: "none",
      },
    },
  },
  plugins: [],
};
