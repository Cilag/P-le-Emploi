"use client";
import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getActiveCV, uploadCV } from "@/lib/api";
import toast from "react-hot-toast";
import { Upload } from "lucide-react";

export default function CVUploadPage() {
  const qc = useQueryClient();
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const { data: cv, isLoading } = useQuery({
    queryKey: ["cv"],
    queryFn: getActiveCV,
  });

  const uploadMutation = useMutation({
    mutationFn: uploadCV,
    onSuccess: () => {
      toast.success("CV uploadé avec succès");
      qc.invalidateQueries({ queryKey: ["cv"] });
    },
    onError: () => toast.error("Erreur lors de l'upload"),
  });

  const handleFile = (file: File) => {
    if (!["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"].includes(file.type)) {
      toast.error("Format non supporté. Utilisez PDF ou DOCX.");
      return;
    }
    uploadMutation.mutate(file);
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold text-gray-900">Mon CV</h1>

      <div
        role="button"
        tabIndex={0}
        aria-label="Zone de dépôt du CV — cliquez ou glissez un fichier PDF ou DOCX"
        className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors ${
          dragging ? "border-primary-500 bg-primary-50" : "border-gray-200 hover:border-primary-400"
        }`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const file = e.dataTransfer.files[0];
          if (file) handleFile(file);
        }}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") inputRef.current?.click(); }}
      >
        <Upload className="w-10 h-10 text-gray-400 mx-auto mb-3" />
        <p className="text-gray-600 font-medium">
          {uploadMutation.isPending ? "Upload en cours..." : "Glissez votre CV ici ou cliquez pour sélectionner"}
        </p>
        <p className="text-sm text-gray-400 mt-1">PDF ou DOCX, max 10MB</p>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx"
          className="hidden"
          aria-label="Sélectionner un fichier CV (PDF ou DOCX)"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
        />
      </div>

      {isLoading ? (
        <div className="text-gray-500">Chargement...</div>
      ) : cv ? (
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-gray-900">CV actif</h2>
            <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">Actif</span>
          </div>
          <p className="text-sm text-gray-600 font-medium">{cv.filename}</p>
          <p className="text-xs text-gray-400 mt-0.5">Uploadé le {new Date(cv.cree_le).toLocaleDateString("fr-FR")}</p>
          {cv.texte_extrait && (
            <details className="mt-3">
              <summary className="text-sm text-primary-600 cursor-pointer hover:underline">Voir le texte extrait</summary>
              <pre className="mt-2 text-xs text-gray-500 whitespace-pre-wrap bg-gray-50 p-3 rounded-lg max-h-60 overflow-y-auto">
                {cv.texte_extrait}
              </pre>
            </details>
          )}
        </div>
      ) : (
        <p className="text-gray-400 text-sm">Aucun CV uploadé pour le moment.</p>
      )}
    </div>
  );
}
