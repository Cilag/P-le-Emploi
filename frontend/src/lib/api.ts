import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const api = axios.create({
  baseURL: API_URL,
  timeout: 30000,
});

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

export const sendCandidatureEmail = (id: number, destinataire: string, sujet?: string) =>
  api.post(`/candidatures/${id}/send-email`, { candidature_id: id, destinataire, sujet }).then((r) => r.data);

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
