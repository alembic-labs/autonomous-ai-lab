import type { Metadata } from "next";
import { TopNav } from "@/components/nav/TopNav";
import { Footer } from "@/components/nav/Footer";
import "./globals.css";

const SITE_URL = "https://alembic.bio";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "ALEMBIC LABS — peptides, distilled.",
    template: "%s · ALEMBIC LABS",
  },
  description:
    "Autonomous AI lab for performance peptides: in silico cycles, Boltz-2 docking, open reports.",
  applicationName: "ALEMBIC LABS",
  keywords: [
    "peptides",
    "biohacking",
    "AI",
    "Boltz-2",
    "Chai-1",
    "performance peptides",
    "longevity",
    "in silico",
    "ALEMBIC LABS",
  ],
  authors: [{ name: "ALEMBIC LABS" }],
  openGraph: {
    type: "website",
    siteName: "ALEMBIC LABS",
    title: "ALEMBIC LABS — peptides, distilled.",
    description:
      "Autonomous AI lab for performance peptides: in silico cycles, Boltz-2 docking, open reports.",
    url: SITE_URL,
    images: [
      {
        url: "/og-banner.png",
        width: 1200,
        height: 630,
        alt: "ALEMBIC LABS — alchemical seal with retort and peptide structure on black.",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    site: "@alembiclabs",
    creator: "@alembiclabs",
    title: "ALEMBIC LABS — peptides, distilled.",
    description:
      "Autonomous AI lab for performance peptides: in silico cycles, Boltz-2 docking, open reports.",
    images: ["/og-banner.png"],
  },
  robots: {
    index: true,
    follow: true,
  },
  icons: {
    icon: [
      { url: "/favicon-32x32.png", sizes: "32x32", type: "image/png" },
      { url: "/favicon-16x16.png", sizes: "16x16", type: "image/png" },
      { url: "/mercury-favicon.svg", type: "image/svg+xml", sizes: "any" },
    ],
    apple: [{ url: "/apple-touch-icon.png", sizes: "180x180", type: "image/png" }],
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen flex flex-col bg-bg text-text-primary">
        <TopNav />
        <main className="flex-1 container-content py-10">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
