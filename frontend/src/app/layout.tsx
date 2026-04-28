import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AM – Academic Manuscript IP Evaluator",
  description: "Structural Search and Overlap Workflow for academic manuscript novelty evaluation",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}