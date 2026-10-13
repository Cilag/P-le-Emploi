import axios from "axios";
import { clearToken, getToken, setToken } from "./auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const api = axios.create({
  baseURL: API_URL,
  timeout: 30000,
});

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error?.response?.status === 401 && typeof window !== "undefined" && window.location.pathname !== "/login") {
      clearToken();
      window.location.href = "/login";
    }
    return Promise.reject(error);
  },
);

export const login = async (username: string, password: string) => {
  const r = await api.post<{ access_token: string }>(
    "/auth/token",
    new URLSearchParams({ username, password }),
    { headers: { "Content-Type": "application/x-www-form-urlencoded" } },
  );
  setToken(r.data.access_token);
};

export const errorMessage = (e: unknown): string => {
  const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  return e instanceof Error ? e.message : "Erreur inconnue";
};

export interface Offre {
  id: number;
  titre: string;
  entreprise: string;
  description: string | null;
  lien_source: string;
  source: string;
  ville: string | null;
  type_contrat: string | null;
  date_publication: string | null;
  date_import: string;
  statut: string;
  dedup_hash: string;
  email_contact: string | null;
}

export interface Lettre {
  id: number;
  offre_id: number | null;
  entreprise: string;
  contenu: string;
  version: number;
  cree_le: string;
  modifie_le: string;
}

export interface Candidature {
  id: number;
  offre_id: number;
  lettre_id: number | null;
  statut: string;
  cree_le: string;
  modifie_le: string;
  envoyee_le: string | null;
  offre_titre: string | null;
  offre_entreprise: string | null;
  offre_lien: string | null;
  offre_email_contact: string | null;
}

export interface CV {
  id: number;
  filename: string;
  texte_extrait: string | null;
  actif: boolean;
  cree_le: string;
}

export interface ScanParams {
  secteur?: string;
  region?: string;
  ville?: string;
  type_contrat?: string;
  mots_cles?: string;
  sources?: string[];
}

export interface TaskStatus {
  task_id: string;
  status: string;
  result: unknown;
  error?: string;
}

// Offres
export const getOffres = (params?: Record<string, string>) =>
  api.get<Offre[]>("/offres", { params }).then((r) => r.data);

export const launchScan = (params: ScanParams) =>
  api.post<TaskStatus>("/offres/scan", params).then((r) => r.data);

export const getScanStatus = (taskId: string) =>
  api.get<TaskStatus>(`/offres/scan/${taskId}`).then((r) => r.data);

export const getSources = () =>
  api.get<{ sources: string[] }>("/offres/sources/list").then((r) => r.data);

// Lettres
export const getLettres = (entreprise?: string) =>
  api.get<Lettre[]>("/lettres", { params: entreprise ? { entreprise } : {} }).then((r) => r.data);

export const getLettre = (id: number) =>
  api.get<Lettre>(`/lettres/${id}`).then((r) => r.data);

export const generateLettre = (offreId: number, force = false) =>
  api.post<TaskStatus>("/lettres/generate", { offre_id: offreId, force_regenerate: force }).then((r) => r.data);

export const updateLettre = (id: number, contenu: string) =>
  api.put<Lettre>(`/lettres/${id}`, { contenu }).then((r) => r.data);

export const getLettrePdfUrl = (id: number) => `${API_URL}/lettres/${id}/pdf`;

export const getLettresByEntreprise = (name: string) =>
  api.get<Lettre[]>(`/lettres/entreprise/${encodeURIComponent(name)}`).then((r) => r.data);

// Candidatures
export const getCandidatures = (statut?: string) =>
  api.get<Candidature[]>("/candidatures", { params: statut ? { statut } : {} }).then((r) => r.data);

export const createCandidature = (offreId: number, lettreId?: number) =>
  api.post<Candidature>("/candidatures", { offre_id: offreId, lettre_id: lettreId }).then((r) => r.data);

export const updateCandidature = (id: number, statut: string) =>
  api.patch<Candidature>(`/candidatures/${id}`, { statut }).then((r) => r.data);

export const exportCandidatures = (ids: number[]) =>
  api.post("/candidatures/export", { candidature_ids: ids }, { responseType: "blob" }).then((r) => r.data);

// CV
export const getActiveCV = () => api.get<CV>("/cv").then((r) => r.data);

export const uploadCV = (file: File) => {
  const formData = new FormData();
  formData.append("file", file);
  return api.post<CV>("/cv", formData, { headers: { "Content-Type": "multipart/form-data" } }).then((r) => r.data);
};

export const triggerAudit = (emailDestination: string) =>
  api.post<TaskStatus>("/cv/audit", { email_destination: emailDestination, jour_execution: 1 }).then((r) => r.data);

// Parcours candidature
export type PostulerResult =
  | { mode: "email"; destinataire: string }
  | { mode: "site"; lien: string; lettre_id: number; lettre_texte: string };

export const preparerCandidature = (offreId: number) =>
  api.post<{ candidature_id: number; task_id: string; status: string }>("/candidatures/preparer", { offre_id: offreId }).then((r) => r.data);

export const getGenerationStatus = (taskId: string) =>
  api.get<TaskStatus>(`/lettres/generate/${taskId}`).then((r) => r.data);

export const postuler = (id: number) =>
  api.post<PostulerResult>(`/candidatures/${id}/postuler`).then((r) => r.data);

export const marquerEnvoyee = (id: number) =>
  api.post<Candidature>(`/candidatures/${id}/marquer-envoyee`).then((r) => r.data);

export const updateOffreEmail = (offreId: number, email: string | null) =>
  api.patch<Offre>(`/offres/${offreId}`, { email_contact: email }).then((r) => r.data);

export const downloadFile = async (path: string, filename: string) => {
  const r = await api.get(path, { responseType: "blob" });
  const url = URL.createObjectURL(r.data as Blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
};

export const copierTexte = async (texte: string) => {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(texte);
    return;
  }
  const ta = document.createElement("textarea");
  ta.value = texte;
  ta.style.position = "fixed";
  ta.style.opacity = "0";
  document.body.appendChild(ta);
  ta.select();
  const ok = document.execCommand("copy");
  document.body.removeChild(ta);
  if (!ok) throw new Error("copie impossible");
};
