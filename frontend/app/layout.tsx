import type { Metadata } from "next";
import { EB_Garamond } from "next/font/google";
import "./globals.css";

const garamond = EB_Garamond({
  subsets: ["latin"],
  variable: "--font-garamond",
});

export const metadata: Metadata = {
  title: "Alucard — Franz Kafka",
  description: "Digital Clone AI — Speak with Franz Kafka",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={garamond.variable}>
      <body className="bg-[#0a0a0a] antialiased font-[family-name:var(--font-garamond)]">
        {children}
      </body>
    </html>
  );
}
