import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NEXUS Ω — AI Engineering & Knowledge Workspace",
  description: "A clear, evidence-first workspace for autonomous AI engineering, research, learning, and retrieval-augmented knowledge.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body>{children}</body></html>;
}
