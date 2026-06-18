"use client";

import Link from "next/link";

export default function Page() {
  return (
    <main className="min-h-screen bg-black text-white flex items-center justify-center p-6">
      <div className="max-w-xl rounded-3xl border border-amber-400/20 bg-amber-400/10 p-8 text-center">
        <h1 className="text-3xl font-bold">Payment cancelled</h1>
        <p className="mt-4 text-white/75">No charge was completed. You can return to the credits page and try again whenever you want.</p>
        <Link href="/credits" className="mt-6 inline-flex rounded-2xl bg-white/10 px-5 py-3 font-semibold">Back to credits</Link>
      </div>
    </main>
  );
}
