import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Voice-Based Autonomous Multi-Agent AI Interview Coach",
  description: "Real-time multi-agent AI recruiter simulator with voice, planner orchestration, and resume-aware questioning."
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

