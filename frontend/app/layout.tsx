import type { Metadata } from "next";
import { Playfair_Display } from "next/font/google";
import "./globals.css";

const playfair = Playfair_Display({
  subsets: ["latin"],
  variable: "--font-playfair",
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
    <html lang="en" className={`dark ${playfair.variable}`}>
      <body>
        <div className="watermark">K.</div>
        {children}
      </body>
    </html>
  );
}
