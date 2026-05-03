import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: "#000000",
          surface: "#0a0a0a",
          elevated: "#141414",
        },
        border: {
          subtle: "#1f1f1f",
          accent: "#2a2a2a",
        },
        text: {
          primary: "#e8e8e8",
          secondary: "#a8a8a8",
          muted: "#6a6a6a",
          subtle: "#444444",
        },
        brand: {
          DEFAULT: "#ff3344",
          glow: "#ff5566",
          deep: "#c41e3a",
        },
        status: {
          refined: "#44dd88",
          promising: "#7be0c5",
          pending: "#ffcc44",
          discarded: "#6a6a6a",
          failed: "#ff3344",
        },
      },
      fontFamily: {
        mono: [
          "JetBrains Mono",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "Consolas",
          "monospace",
        ],
      },
      fontSize: {
        "display": ["2rem", { lineHeight: "1.15", fontWeight: "700" }],
        "h1": ["1.5rem", { lineHeight: "1.2", fontWeight: "700" }],
        "h2": ["1.0625rem", { lineHeight: "1.3", fontWeight: "700" }],
        "h3": ["0.9375rem", { lineHeight: "1.35", fontWeight: "600" }],
        "body": ["0.875rem", { lineHeight: "1.6", fontWeight: "400" }],
        "small": ["0.75rem", { lineHeight: "1.4", fontWeight: "400" }],
        "data": ["0.8125rem", { lineHeight: "1.5", fontWeight: "400" }],
      },
      borderRadius: {
        none: "0",
      },
      maxWidth: {
        content: "1280px",
      },
      animation: {
        "pulse-red": "pulseRed 1.6s ease-in-out infinite",
        "blink": "blink 1s step-end infinite",
      },
      keyframes: {
        pulseRed: {
          "0%, 100%": { opacity: "1", boxShadow: "0 0 0 0 rgba(255, 51, 68, 0.6)" },
          "50%": { opacity: "0.7", boxShadow: "0 0 0 6px rgba(255, 51, 68, 0)" },
        },
        blink: {
          "0%, 50%": { opacity: "1" },
          "51%, 100%": { opacity: "0" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
