/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Cyberpunk/HUD color palette
        cyber: {
          cyan: "#06b6d4",
          purple: "#a855f7",
          pink: "#ec4899",
          green: "#10b981",
          orange: "#f97316",
          red: "#ef4444",
        },
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "glow": "glow 2s ease-in-out infinite alternate",
        "scan": "scan 2s linear infinite",
      },
      keyframes: {
        glow: {
          "0%": { opacity: "0.5", filter: "blur(10px)" },
          "100%": { opacity: "0.8", filter: "blur(15px)" },
        },
        scan: {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100%)" },
        },
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "cyber-grid":
          "linear-gradient(rgba(6, 182, 212, 0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(6, 182, 212, 0.1) 1px, transparent 1px)",
      },
      boxShadow: {
        cyber: "0 0 20px rgba(6, 182, 212, 0.3)",
        "cyber-lg": "0 0 40px rgba(6, 182, 212, 0.4)",
        neon: "0 0 10px currentColor, 0 0 20px currentColor, 0 0 30px currentColor",
      },
    },
  },
  plugins: [],
};
