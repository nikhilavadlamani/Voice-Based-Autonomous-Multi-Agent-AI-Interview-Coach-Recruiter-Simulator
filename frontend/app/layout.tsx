import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Northstar Interview AI",
  description: "Human-sounding voice interview practice with resume-aware prompts, smarter follow-ups, and instant coaching."
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
