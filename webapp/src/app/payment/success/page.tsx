"use client";

import Link from "next/link";

export default function Page() {
  return (
    <main className="min-h-screen bg-black text-white flex items-center justify-center p-6">
      <div className="max-w-xl rounded-3xl border border-emerald-400/20 bg-emerald-400/10 p-8 text-center">
        <h1 className="text-3xl font-bold">Payment successful</h1>
        <p className="mt-4 text-white/75">Your payment was completed. Return to the credits page to review your updated balance.</p>
        <Link href="/credits" className="mt-6 inline-flex rounded-2xl bg-white/10 px-5 py-3 font-semibold">Back to credits</Link>
      </div>
    </main>
  );
}
