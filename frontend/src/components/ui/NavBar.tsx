"use client";
import Link from "next/link";
import { Briefcase } from "lucide-react";
import { clearToken } from "@/lib/auth";

const links = [
  { href: "/jobs", label: "Offres" },
  { href: "/letters", label: "Lettres" },
  { href: "/applications", label: "Candidatures" },
  { href: "/appartements", label: "Appartements" },
  { href: "/cv-upload", label: "Mon CV" },
  { href: "/audit", label: "Audit" },
];

export function NavBar() {
  return (
    <nav className="bg-white border-b border-gray-200 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2 text-primary-600 font-bold text-lg">
          <Briefcase className="w-5 h-5" />
          PE Assistant
        </Link>
        <div className="flex gap-6">
          {links.map(({ href, label }) => (
            <Link key={href} href={href} className="text-gray-600 hover:text-primary-600 text-sm font-medium transition-colors">
              {label}
            </Link>
          ))}
          <button
            onClick={() => { clearToken(); window.location.href = "/login"; }}
            className="text-gray-400 hover:text-red-600 text-sm font-medium transition-colors"
          >
            Déconnexion
          </button>
        </div>
      </div>
    </nav>
  );
}
