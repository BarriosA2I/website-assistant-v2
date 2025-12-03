// app/layout.tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Barrios A2I | AI Video Generation",
  description: "Generate professional commercials in minutes with AI-powered video creation",
  keywords: ["AI video", "commercial generation", "marketing automation"],
  authors: [{ name: "Barrios A2I" }],
  openGraph: {
    title: "Barrios A2I | AI Video Generation",
    description: "Generate professional commercials in minutes",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} bg-slate-950 text-slate-100 antialiased`}>
        {children}
      </body>
    </html>
  );
}
