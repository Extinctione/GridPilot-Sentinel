/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0B0F14",
        panel: "#121823",
        panelborder: "#1E2A3A",
        accentgreen: "#22C55E",
        accentamber: "#F59E0B",
        accentred: "#EF4444",
        textprimary: "#E5EAF0",
        textmuted: "#8B98A9",
      },
    },
  },
  plugins: [],
}
