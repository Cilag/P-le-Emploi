import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { Toaster } from "react-hot-toast";
import { NavBar } from "@/components/ui/NavBar";

export const metadata: Metadata = {
  title: "Pôle Emploi Assistant",
  description: "Votre assistant de candidature intelligent",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body className="min-h-screen bg-gray-50">
        <Providers>
          <NavBar />
          <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">{children}</main>
          <Toaster position="top-right" />
        </Providers>
      </body>
    </html>
  );
}
