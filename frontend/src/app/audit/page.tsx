"use client";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { triggerAudit } from "@/lib/api";
import toast from "react-hot-toast";
import { FileSearch } from "lucide-react";

export default function AuditPage() {
  const [email, setEmail] = useState("");

  const auditMutation = useMutation({
    mutationFn: () => triggerAudit(email),
    onSuccess: () => toast.success("Audit lancé ! Vous recevrez le rapport par email."),
    onError: () => toast.error("Erreur lors du déclenchement de l'audit"),
  });

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center gap-3">
        <FileSearch className="w-7 h-7 text-primary-600" />
        <h1 className="text-2xl font-bold text-gray-900">Audit CV mensuel</h1>
      </div>

      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6 space-y-4">
        <p className="text-gray-600">
          L'agent IA analyse votre CV en profondeur et génère un rapport structuré avec :
          des points forts, des axes d'amélioration, des recommandations et les compétences
          manquantes détectées dans les offres récentes.
        </p>

        <ul className="text-sm text-gray-500 space-y-1 list-disc list-inside">
          <li>Analyse de cohérence et de lisibilité</li>
          <li>Identification des lacunes vs offres récentes</li>
          <li>Score global et recommandations actionnables</li>
          <li>Rapport envoyé par email</li>
        </ul>

        <div className="pt-2 space-y-3">
          <label className="block text-sm font-medium text-gray-700">
            Email de destination
          </label>
          <input
            type="email"
            className="w-full border border-gray-200 rounded-lg px-3 py-2"
            placeholder="votre@email.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <button
            onClick={() => auditMutation.mutate()}
            disabled={auditMutation.isPending || !email}
            className="w-full bg-primary-600 text-white py-3 rounded-lg hover:bg-primary-700 font-medium transition-colors disabled:opacity-50"
          >
            {auditMutation.isPending ? "Lancement en cours..." : "Déclencher l'audit maintenant"}
          </button>
        </div>
      </div>

      <div className="bg-blue-50 border border-blue-100 rounded-xl p-4 text-sm text-blue-700">
        <strong>Note :</strong> L'audit mensuel automatique est configuré par votre administrateur infrastructure.
        Utilisez ce bouton pour déclencher un audit à la demande.
      </div>
    </div>
  );
}
