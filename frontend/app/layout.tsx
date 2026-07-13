import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RAG Document Q&A",
  description:
    "Upload your documents and ask questions about them. Every answer shows you where it came from.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Geomini:wght@200..800&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
