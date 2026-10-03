"use client";

import { FormEvent, useState } from "react";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";

import { authClient } from "@/lib/auth-client";

export default function SignInPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"sign-in" | "sign-up">("sign-in");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const result = mode === "sign-in"
        ? await authClient.signIn.email({ email, password, callbackURL: "/" })
        : await authClient.signUp.email({ name, email, password, callbackURL: "/" });
      if (result.error) throw new Error(result.error.message ?? "Unable to authenticate.");
      router.replace("/");
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to authenticate.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-page">
      <div className="auth-grid" aria-hidden="true" />
      <section className="auth-panel">
        <div className="auth-brand"><div className="brand-mark"><span /><span /><span /></div><span className="brand-name">northstar<span>.</span></span><span className="auth-brand-label">ENTERPRISE</span></div>
        <div className="auth-intro"><div className="auth-kicker"><span /> PRIVATE KNOWLEDGE WORKSPACE</div><h1>{mode === "sign-in" ? "Your knowledge,\nwithin reach." : "A clearer path\nto your knowledge."}</h1><p>Grounded answers from the information your team trusts.</p></div>
        <form className="auth-form" onSubmit={submit}>
          {mode === "sign-up" && <label>Full name<input autoComplete="name" required value={name} onChange={(event) => setName(event.target.value)} placeholder="Your name" /></label>}
          <label>Work email<input autoComplete="email" type="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@company.com" /></label>
          <label>Password<input autoComplete={mode === "sign-in" ? "current-password" : "new-password"} type="password" minLength={8} required value={password} onChange={(event) => setPassword(event.target.value)} placeholder="At least 8 characters" /></label>
          {error && <p className="auth-error" role="alert">{error}</p>}
          <button className="auth-submit" disabled={busy} type="submit"><span>{busy ? "Securing your session..." : mode === "sign-in" ? "Sign in securely" : "Create account"}</span><ArrowRight size={16} /></button>
        </form>
        <div className="auth-switch">{mode === "sign-in" ? "New to this workspace?" : "Already have an account?"}<button onClick={() => { setMode(mode === "sign-in" ? "sign-up" : "sign-in"); setError(""); }}>{mode === "sign-in" ? "Create an account" : "Sign in"}</button></div>
        <div className="auth-security"><ShieldCheck size={14} /><span>Protected by encrypted sessions and verified source access</span></div>
      </section>
      <aside className="auth-aside"><div className="aside-orbit orbit-one" /><div className="aside-orbit orbit-two" /><div className="aside-copy"><div className="aside-index">01 <span>/ YOUR KNOWLEDGE GRAPH</span></div><div className="auth-art"><div className="art-node node-center"><span className="brand-mark"><i /><i /><i /></span></div><div className="art-node node-a"><span /><span /></div><div className="art-node node-b"><span /><span /></div><div className="art-node node-c"><span /><span /></div><i className="art-link link-a" /><i className="art-link link-b" /><i className="art-link link-c" /><i className="art-link link-d" /><i className="art-link link-e" /></div><h2>Answers with a paper trail.</h2><p>Every response stays close to its source, with context you can inspect.</p><div className="aside-footer"><span>HYBRID SEARCH</span><i /><span>VERIFIED CITATIONS</span><i /><span>ROLE-BASED ACCESS</span></div></div></aside>
    </main>
  );
}