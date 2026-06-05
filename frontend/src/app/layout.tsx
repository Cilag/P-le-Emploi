import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Pôle Emploi — Assistant de Candidature",
  description: "Assistant intelligent pour optimiser vos candidatures",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body>{children}</body>
    </html>
  );
}
