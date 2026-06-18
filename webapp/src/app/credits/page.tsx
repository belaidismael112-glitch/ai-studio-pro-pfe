
"use client";

import { useMemo, useState } from "react";
import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import {
  useCreditBalance,
  useCreditPackages,
  useCreditHistory,
  usePurchaseCredits,
} from "@/hooks/useCredits";
import {
  CreditCard,
  Loader2,
  Wallet,
  Receipt,
  ArrowUpRight,
  Coins,
  ShieldCheck,
  LockKeyhole,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import { formatCredits, formatPrice, formatDate } from "@/lib/utils";

export default function CreditsPage() {
  const { user } = useAuth();

  const [selectedPackage, setSelectedPackage] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{ type: "success" | "error" | "info"; text: string } | null>(null);
  const [isPurchasing, setIsPurchasing] = useState<string | null>(null);

  const { data: balance, isLoading: balanceLoading } = useCreditBalance();
  const { data: packages, isLoading: packagesLoading } = useCreditPackages();
  const { data: history, isLoading: historyLoading } = useCreditHistory(20);
  const purchase = usePurchaseCredits();

  const selected = useMemo(
    () => packages?.find((pkg) => pkg.id === selectedPackage) || packages?.[1] || packages?.[0],
    [packages, selectedPackage]
  );

  const canPay = !!selected;

  const selectPackage = (packageId: string) => {
    setSelectedPackage(packageId);
    setFeedback({ type: "info", text: "Pack selected. Continue to the hosted Stripe Checkout page to enter payment details securely." });
  };

  const handlePurchase = async () => {
    if (!selected || !canPay) {
      setFeedback({ type: "error", text: "Select a credit pack before opening checkout." });
      return;
    }

    setIsPurchasing(selected.id);
    setFeedback(null);

    try {
      const result = await purchase.mutateAsync(selected.id);
      const checkoutUrl = String(result?.checkout_url || "").trim();
      if (checkoutUrl.startsWith("https://checkout.stripe.com/")) {
        window.location.href = checkoutUrl;
        return;
      }

      throw new Error("Stripe did not return a hosted Checkout URL. Credits were not added.");
    } catch (error: any) {
      const status = error?.response?.status;
      const detail = error?.response?.data?.detail;
      const message = status === 404
        ? "Checkout endpoint not found. Restart the backend after installing the credits fix."
        : detail || error?.message || "Payment failed";
      setFeedback({ type: "error", text: String(message) });
    } finally {
      setIsPurchasing(null);
    }
  };

  return (
    <DashboardLayout>
      <div className="human-made-screen relative min-h-[calc(100vh-120px)] overflow-hidden rounded-[28px] border border-white/10 bg-black text-white shadow-[0_0_80px_rgba(217,70,239,0.08)]">
        <div className="absolute inset-0">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(217,70,239,0.16),transparent_28%),radial-gradient(circle_at_top_right,rgba(34,211,238,0.10),transparent_24%),radial-gradient(circle_at_bottom_center,rgba(239,68,68,0.10),transparent_30%),linear-gradient(180deg,#040404_0%,#090909_100%)]" />
          <div className="absolute inset-0 opacity-[0.16]" style={{ backgroundImage: "radial-gradient(rgba(255,255,255,0.55) 0.6px, transparent 0.6px)", backgroundSize: "26px 26px" }} />
          <div className="absolute left-[10%] top-[12%] h-44 w-44 rounded-full bg-fuchsia-500/10 blur-3xl animate-pulse" />
          <div className="absolute right-[10%] top-[20%] h-56 w-56 rounded-full bg-cyan-400/10 blur-3xl animate-pulse" />
          <div className="absolute bottom-[8%] left-[40%] h-64 w-64 rounded-full bg-violet-500/10 blur-3xl animate-pulse" />
        </div>

        <div className="relative z-10 mx-auto max-w-7xl p-6 md:p-8 xl:p-10 space-y-8">
          <div className="grid gap-6 lg:grid-cols-[1fr_380px] lg:items-end">
            <div>
              <div className="human-pill mb-3 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] tracking-[0.08em] text-white/60 backdrop-blur">
                <span className="h-2 w-2 rounded-full bg-cyan-300" />
                Secure billing
              </div>
              <h1 className="text-4xl font-black tracking-tight md:text-5xl">
                Credits & <span className="text-fuchsia-400">Secure Checkout</span>
              </h1>
              <p className="human-note mt-3 max-w-2xl text-sm leading-6 text-white/60 md:text-base">
                Choose a credit pack here, then enter payment details only on the hosted Stripe Checkout page. This app never asks for or stores your card number or CVC.
              </p>
            </div>

            <div className="rounded-[26px] border border-white/10 bg-white/[0.055] p-4 backdrop-blur-xl">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-white/40">Account</p>
                  <p className="mt-1 truncate text-sm font-semibold text-white">{user?.full_name || user?.email || "User"}</p>
                  <p className="truncate text-xs text-white/50">{user?.email}</p>
                </div>
                <div className="rounded-2xl border border-emerald-400/20 bg-emerald-400/10 px-4 py-3 text-right">
                  <p className="text-xs text-emerald-100/70">Current credits</p>
                  <p className="text-xl font-black text-white">{balanceLoading ? "..." : formatCredits(balance?.credits || 0)}</p>
                </div>
              </div>
            </div>
          </div>

          {feedback && (
            <div className={`flex items-center gap-3 rounded-2xl border px-4 py-3 text-sm ${feedback.type === "success" ? "border-emerald-400/20 bg-emerald-400/10 text-emerald-50" : feedback.type === "error" ? "border-red-400/20 bg-red-500/10 text-red-100" : "border-cyan-300/20 bg-cyan-300/10 text-cyan-50"}`}>
              {feedback.type === "success" ? <CheckCircle2 className="h-4 w-4" /> : feedback.type === "error" ? <AlertCircle className="h-4 w-4" /> : <ShieldCheck className="h-4 w-4" />}
              {feedback.text}
            </div>
          )}

          <div className="grid gap-6 xl:grid-cols-[1fr_430px]">
            <section className="space-y-5">
              <div className="relative overflow-hidden rounded-[30px] border border-white/10 bg-gradient-to-br from-fuchsia-600/30 via-pink-600/20 to-cyan-500/20 p-[1px] shadow-[0_0_45px_rgba(217,70,239,0.20)]">
                <div className="relative overflow-hidden rounded-[30px] bg-black/65 p-8 backdrop-blur-2xl">
                  <div className="absolute -right-16 -top-16 h-52 w-52 rounded-full bg-fuchsia-500/20 blur-3xl" />
                  <div className="relative flex flex-col gap-8 md:flex-row md:items-center md:justify-between">
                    <div>
                      <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-white/65">
                        <Wallet className="h-4 w-4 text-cyan-300" /> Available balance
                      </div>
                      <p className="text-sm uppercase tracking-[0.24em] text-white/40">Your credits</p>
                      <div className="mt-3 flex items-end gap-3">
                        <p className="text-5xl font-black md:text-6xl">{balanceLoading ? "..." : formatCredits(balance?.credits || 0)}</p>
                        <span className="pb-2 text-sm text-white/55">credits</span>
                      </div>
                      <p className="mt-3 max-w-xl text-sm text-white/50">Use your credits for image generation, image-to-image workflows, operator tasks, and production previews.</p>
                    </div>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <div className="rounded-3xl border border-white/10 bg-white/5 px-5 py-4 backdrop-blur-xl">
                        <div className="mb-2 flex items-center gap-2 text-white/60"><Coins className="h-4 w-4 text-fuchsia-300" /> Billing mode</div>
                        <div className="text-2xl font-bold text-white">Secure</div>
                      </div>
                      <div className="rounded-3xl border border-white/10 bg-white/5 px-5 py-4 backdrop-blur-xl">
                        <div className="mb-2 flex items-center gap-2 text-white/60"><ShieldCheck className="h-4 w-4 text-emerald-300" /> Gateway</div>
                        <div className="text-2xl font-bold text-white">Stripe-ready</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div>
                <h2 className="text-2xl font-bold text-white">Choose credit pack</h2>
                <p className="mt-1 text-sm text-white/50">Select a pack, then continue to the hosted Stripe Checkout page.</p>
              </div>

              {packagesLoading ? (
                <div className="flex justify-center py-12"><Loader2 className="h-8 w-8 animate-spin text-fuchsia-400" /></div>
              ) : (
                <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
                  {packages?.map((pkg, index) => {
                    const active = selected?.id === pkg.id;
                    return (
                      <button
                        type="button"
                        key={pkg.id}
                        onClick={() => selectPackage(pkg.id)}
                        className={`group relative overflow-hidden rounded-[28px] border p-[1px] text-left backdrop-blur-xl transition duration-300 hover:-translate-y-1 hover:border-fuchsia-400/30 hover:shadow-[0_0_35px_rgba(217,70,239,0.16)] ${active ? "border-fuchsia-300/40 bg-fuchsia-400/10" : "border-white/10 bg-white/[0.04]"}`}
                      >
                        <div className="relative h-full rounded-[28px] bg-black/70 p-6">
                          {index === 1 && <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-fuchsia-400/20 bg-fuchsia-500/10 px-3 py-1 text-[11px] uppercase tracking-[0.24em] text-fuchsia-300"><Coins className="h-3.5 w-3.5" />Popular</div>}
                          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl border border-white/10 bg-white/5"><CreditCard className="h-5 w-5 text-cyan-300" /></div>
                          <h3 className="text-2xl font-bold text-white">{pkg.name}</h3>
                          <p className="mt-2 min-h-[44px] text-sm leading-6 text-white/50">{pkg.description}</p>
                          <div className="mt-6 space-y-2">
                            <div className="text-4xl font-black text-fuchsia-400">{formatCredits(pkg.credits)}</div>
                            <div className="text-sm uppercase tracking-[0.22em] text-white/35">credits included</div>
                          </div>
                          <div className="mt-6 text-3xl font-bold text-white">{formatPrice(pkg.price, pkg.currency)}</div>
                          <div className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-fuchsia-500 via-pink-500 to-violet-500 px-4 py-3 text-sm font-bold text-white">
                            {active ? "Selected" : "Select pack"} <ArrowUpRight className="h-4 w-4" />
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </section>

            <aside className="rounded-[30px] border border-white/10 bg-white/[0.055] p-5 backdrop-blur-xl xl:sticky xl:top-24 xl:self-start">
              <div className="mb-5 flex items-center justify-between gap-4">
                <div>
                  <p className="text-xs uppercase tracking-[0.22em] text-white/40">Secure checkout</p>
                  <h2 className="mt-1 text-2xl font-black text-white">Stripe Checkout</h2>
                </div>
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-emerald-400/20 bg-emerald-400/10"><LockKeyhole className="h-5 w-5 text-emerald-200" /></div>
              </div>

              <div className="mb-5 rounded-2xl border border-cyan-300/15 bg-cyan-300/10 p-4 text-sm leading-6 text-cyan-50/85">
                Your payment details are collected only by Stripe on its hosted Checkout page. AI Studio Pro does not collect card numbers, expiry dates, or CVC values.
              </div>

              <div className="space-y-4">
                <div className="rounded-2xl border border-white/10 bg-black/30 p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-white/60">Selected pack</span>
                    <span className="font-bold text-white">{selected?.name || "Select one"}</span>
                  </div>
                  <div className="mt-2 flex items-center justify-between">
                    <span className="text-sm text-white/60">Total</span>
                    <span className="text-2xl font-black text-fuchsia-300">{selected ? formatPrice(selected.price, selected.currency) : "—"}</span>
                  </div>
                </div>

                <div className="grid gap-3 text-sm leading-6 text-white/70">
                  <div className="rounded-2xl border border-white/10 bg-black/25 p-4">1. Choose the credit pack you need.</div>
                  <div className="rounded-2xl border border-white/10 bg-black/25 p-4">2. Open the hosted Stripe Checkout page.</div>
                  <div className="rounded-2xl border border-white/10 bg-black/25 p-4">3. Stripe securely handles card authorization and returns you to this page.</div>
                </div>

                <Button onClick={handlePurchase} disabled={!canPay || !!isPurchasing} className="h-13 w-full rounded-2xl bg-gradient-to-r from-fuchsia-500 via-pink-500 to-violet-500 text-white shadow-[0_0_30px_rgba(217,70,239,0.22)] hover:opacity-95 disabled:opacity-50">
                  {isPurchasing ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Opening checkout...</> : <><LockKeyhole className="mr-2 h-4 w-4" /> Continue to Stripe Checkout</>}
                </Button>
              </div>
            </aside>
          </div>

          <section className="space-y-4">
            <div><h2 className="text-2xl font-bold text-white">Transaction History</h2><p className="mt-1 text-sm text-white/50">A complete timeline of credit activity on your account.</p></div>
            <div className="overflow-hidden rounded-[26px] border border-white/10 bg-white/[0.04] backdrop-blur-xl">
              {historyLoading ? (
                <div className="flex justify-center py-12"><Loader2 className="h-6 w-6 animate-spin text-fuchsia-400" /></div>
              ) : history && history.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm"><thead><tr className="border-b border-white/10 text-left text-white/45"><th className="px-6 py-4">Date</th><th className="px-6 py-4">Type</th><th className="px-6 py-4 text-right">Amount</th><th className="px-6 py-4 text-right">Balance</th></tr></thead><tbody>{history.map((tx) => (<tr key={tx.id} className="border-b border-white/5 text-white/75"><td className="px-6 py-4">{formatDate(tx.created_at)}</td><td className="px-6 py-4"><span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs capitalize">{tx.transaction_type}</span></td><td className={`px-6 py-4 text-right font-semibold ${tx.amount > 0 ? "text-emerald-300" : "text-red-300"}`}>{tx.amount > 0 ? "+" : ""}{formatCredits(tx.amount)}</td><td className="px-6 py-4 text-right font-semibold text-white">{formatCredits(tx.balance_after)}</td></tr>))}</tbody></table>
                </div>
              ) : (
                <div className="flex min-h-[180px] flex-col items-center justify-center p-8 text-center"><Receipt className="mb-3 h-8 w-8 text-white/35" /><p className="text-white/60">No transactions yet.</p></div>
              )}
            </div>
          </section>
        </div>
      </div>
    </DashboardLayout>
  );
}
