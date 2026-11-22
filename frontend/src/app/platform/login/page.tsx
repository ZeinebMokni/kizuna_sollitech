"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Card, ErrorNote, PageHeader } from "@/components/ui";
import { platformRequest, setPlatformToken } from "@/lib/platform-api";

export default function PlatformLogin() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await platformRequest<{ access_token: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setPlatformToken(result.access_token);
      router.push("/platform/farms");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Login failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeader title="Platform login" lead="Sign in to manage farms and authenticated field data. The research engine dashboard remains available without this account." />
      <Card className="max-w-md">
        {error && <div className="mb-4"><ErrorNote message={error} /></div>}
        <form onSubmit={submit} className="space-y-4">
          <label className="block text-sm">
            <span className="mb-1 block text-muted">Email</span>
            <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="w-full rounded-md border border-line px-3 py-2" />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-muted">Password</span>
            <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} className="w-full rounded-md border border-line px-3 py-2" />
          </label>
          <button disabled={busy} className="w-full rounded-md bg-green-deep px-4 py-2 text-sm font-medium text-white disabled:opacity-60">
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </Card>
    </>
  );
}
