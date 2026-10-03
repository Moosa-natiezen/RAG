"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { authClient } from "@/lib/auth-client";

export function AuthGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { data: session, isPending } = authClient.useSession();

  useEffect(() => {
    if (!isPending && !session) router.replace("/sign-in");
  }, [isPending, router, session]);

  if (isPending || !session) {
    return <main className="auth-loading"><span className="auth-spinner" />Checking your secure session</main>;
  }
  return children;
}