"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { errorMessage, login } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setPending(true);
    try {
      await login(username, password);
      router.push("/jobs");
    } catch (err) {
      toast.error(`Connexion refusée : ${errorMessage(err)}`);
    } finally {
      setPending(false);
    }
  };

  return (
    <form onSubmit={submit} className="max-w-sm mx-auto bg-white rounded-xl border border-gray-100 shadow-sm p-6 space-y-4">
      <h1 className="text-xl font-bold text-gray-900">Connexion</h1>
      <input aria-label="Identifiant" className="w-full border border-gray-200 rounded-lg px-3 py-2"
        value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
      <input aria-label="Mot de passe" type="password" className="w-full border border-gray-200 rounded-lg px-3 py-2"
        value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
      <button type="submit" disabled={pending || !password}
        className="w-full bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700 disabled:opacity-50">
        {pending ? "Connexion..." : "Se connecter"}
      </button>
    </form>
  );
}
