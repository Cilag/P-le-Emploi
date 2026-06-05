import Link from "next/link";
import { Briefcase, FileText, Send, FileSearch, Upload } from "lucide-react";

const features = [
  { href: "/jobs", icon: Briefcase, label: "Offres d'emploi", desc: "Scannez et filtrez les offres de 11 sources" },
  { href: "/letters", icon: FileText, label: "Lettres de motivation", desc: "Générez et gérez vos lettres avec l'IA" },
  { href: "/applications", icon: Send, label: "Candidatures", desc: "Suivez et envoyez vos candidatures" },
  { href: "/cv-upload", icon: Upload, label: "Mon CV", desc: "Uploadez et gérez votre CV actif" },
  { href: "/audit", icon: FileSearch, label: "Audit CV", desc: "Déclenchez un audit IA mensuel de votre CV" },
];

export default function Home() {
  return (
    <div className="space-y-8">
      <div className="text-center py-12">
        <h1 className="text-4xl font-bold text-gray-900">Pôle Emploi Assistant</h1>
        <p className="mt-4 text-lg text-gray-600">Votre assistant IA pour automatiser votre recherche d&apos;emploi en France</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {features.map(({ href, icon: Icon, label, desc }) => (
          <Link
            key={href}
            href={href}
            className="block p-6 bg-white rounded-xl shadow hover:shadow-md transition-shadow border border-gray-100 group"
          >
            <div className="flex items-center gap-3 mb-3">
              <Icon className="w-6 h-6 text-primary-600 group-hover:text-primary-700" />
              <h2 className="text-lg font-semibold text-gray-900">{label}</h2>
            </div>
            <p className="text-gray-500 text-sm">{desc}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
