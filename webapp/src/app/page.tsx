"use client";

import Link from "next/link";
import { CSSProperties, ReactNode, useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Bot,
  Clapperboard,
  Coins,
  ImageIcon,
} from "lucide-react";
import { CinematicSequenceBackdrop } from "@/components/CinematicSequenceBackdrop";
import { IntroGateOverlay } from "@/components/IntroGateOverlay";
import { ThemeToggle } from "@/components/theme/theme-toggle";

const heroPhrases = [
  {
    ending: "delivery.",
    description:
      "The homepage stays elegant and responsive while the product structure remains focused on our real platform features.",
  },
  {
    ending: "generation.",
    description:
      "Generate images, transform references with image-to-image tools, use the assistant, and manage credits from one clean production interface.",
  },
  {
    ending: "results.",
    description:
      "Readable typography, smooth sections, and the cinematic background move together so the experience feels premium and intentional.",
  },
] as const;

const cards = [
  {
    number: "01",
    title: "Image\nGeneration",
    body: "Create polished visuals from detailed prompts, preview outputs, and keep every result organized in history.",
    cta: "Explore",
    href: "/generate/image",
    titleTone: "from-cyan-200 via-sky-300 to-blue-500",
    icon: ImageIcon,
    art: <ImageGenerationArt />,
  },
  {
    number: "02",
    title: "Image-to-\nImage",
    body: "Transform an uploaded person, product, bottle, watch, flyer source or object into a new visual while preserving the important reference details.",
    cta: "Explore",
    href: "/generate/image-to-image",
    titleTone: "from-[#f0d8ff] via-[#8db8ff] to-[#2d7dff]",
    icon: Clapperboard,
    art: <VideoGenerationArt />,
  },
  {
    number: "03",
    title: "Smart\nAssistant",
    body: "Plan, revise, compare, and improve creative ideas with an assistant that stays connected to your workspace.",
    cta: "Explore",
    href: "/assistant",
    titleTone: "from-[#dfe8ff] via-[#8ea7ff] to-[#5577ff]",
    icon: Bot,
    art: <AssistantArt />,
  },
  {
    number: "04",
    title: "Credits &\nAdmin",
    body: "Track credits, review generations, manage users, and keep operations under control with a clean admin flow.",
    cta: "Explore",
    href: "/credits",
    titleTone: "from-[#c7eaff] via-[#6db6ff] to-[#5272ff]",
    icon: Coins,
    art: <CreditsAdminArt />,
  },
] as const;

const stackedFlow = [
  {
    step: "01",
    title: "Big hero titles animate cleanly without overlapping the content.",
    body: "The main heading now has reserved space and animated text transitions, so it stays premium and readable on the homepage.",
  },
  {
    step: "02",
    title: "The animated background keeps running as the user scrolls.",
    body: "Foreground sections remain clear and stable while the cinematic backdrop follows the page movement naturally.",
  },
  {
    step: "03",
    title: "Feature cards use more concrete visuals and subtle motion.",
    body: "The cards now display clearer creative-oriented elements for image generation, image-to-image, assistant, and credits, with smooth animation that feels more professional.",
  },
] as const;

export default function Page() {
  return (
    <main className="relative min-h-screen overflow-x-hidden bg-[#030812] text-white selection:bg-cyan-300/25">
      <CinematicSequenceBackdrop />
      <IntroGateOverlay sequence="home" label="Studio Pro" />
      <div className="pointer-events-none fixed inset-0 z-[1] bg-[radial-gradient(circle_at_18%_18%,rgba(34,211,238,0.14),transparent_16%),radial-gradient(circle_at_78%_18%,rgba(59,130,246,0.16),transparent_20%),linear-gradient(180deg,rgba(3,8,18,0.16),rgba(3,8,18,0.54)_52%,rgba(3,8,18,0.9))]" />

      <TopNav />

      <section id="home" className="relative z-10 flex min-h-screen items-center px-6 pb-20 pt-28 sm:px-8 lg:px-10 lg:pt-36">
        <div className="mx-auto grid w-full max-w-7xl gap-10 lg:grid-cols-[minmax(0,1.04fr)_minmax(320px,0.78fr)] lg:items-start">
          <FadeInUp className="max-w-4xl">
            <div className="inline-flex items-center gap-3 rounded-full border border-cyan-200/15 bg-[#07111d]/62 px-4 py-2 text-[10px] font-black uppercase tracking-[0.34em] text-cyan-100/80 shadow-[0_18px_80px_rgba(0,0,0,0.35)] backdrop-blur-2xl">
              <span className="h-1.5 w-1.5 rounded-full bg-cyan-300 shadow-[0_0_18px_rgba(103,232,249,0.9)]" />
              Studio Pro
            </div>

            <AnimatedHero />

            <div className="mt-10 flex flex-col gap-4 sm:flex-row">
              <Link href="/register" className="rounded-full bg-white px-7 py-4 text-center text-[11px] font-black uppercase tracking-[0.28em] text-black shadow-[0_18px_70px_rgba(103,232,249,0.24)] transition duration-300 hover:-translate-y-0.5 hover:bg-cyan-100">
                Start Free
              </Link>
              <a href="#capabilities" className="rounded-full border border-white/15 bg-[#04111f]/58 px-7 py-4 text-center text-[11px] font-black uppercase tracking-[0.28em] text-white backdrop-blur-2xl transition duration-300 hover:-translate-y-0.5 hover:bg-white/10">
                Explore Platform
              </a>
            </div>
          </FadeInUp>

          <FadeInUp delay={120} className="lg:pt-20">
            <HeroInfoPanel />
          </FadeInUp>
        </div>
      </section>

      <section id="capabilities" className="relative z-10 px-6 py-24 sm:px-8 lg:px-10 lg:py-28">
        <div className="mx-auto max-w-7xl">
          <div className="grid gap-8 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)] lg:items-end">
            <FadeInUp>
              <div className="text-[11px] font-black uppercase tracking-[0.38em] text-cyan-200/78">Capabilities</div>
              <h2 className="mt-5 max-w-3xl text-4xl font-black leading-[0.92] tracking-[-0.07em] text-white drop-shadow-[0_18px_70px_rgba(0,0,0,0.72)] sm:text-6xl">
                Clearer animated cards built around real product elements.
              </h2>
            </FadeInUp>

            <FadeInUp delay={120}>
              <p className="max-w-2xl rounded-[28px] border border-white/10 bg-[#020812]/56 p-6 text-base leading-8 text-white/78 shadow-[0_28px_120px_rgba(0,0,0,0.46)] backdrop-blur-2xl">
                The cards below reflect the production focus of the platform: image generation, image-to-image workflows, smart assistance, and credits management — now with more concrete visuals and smoother motion.
              </p>
            </FadeInUp>
          </div>

          <div className="mt-14 grid gap-6 md:grid-cols-2 xl:grid-cols-4">
            {cards.map((card, index) => (
              <FadeInUp key={card.number} delay={index * 70}>
                <ProductCard {...card} />
              </FadeInUp>
            ))}
          </div>
        </div>
      </section>

      <section id="workflow" className="relative z-10 px-6 py-24 sm:px-8 lg:px-10 lg:py-28">
        <div className="mx-auto grid w-full max-w-7xl gap-10 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)] lg:gap-14">
          <div className="lg:sticky lg:top-28 lg:self-start">
            <FadeInUp>
              <div className="text-[11px] font-black uppercase tracking-[0.38em] text-cyan-200/78">Scroll experience</div>
              <h2 className="mt-5 max-w-[12ch] text-4xl font-black leading-[0.92] tracking-[-0.07em] text-white sm:text-6xl">
                Motion follows the user. The UI stays clear.
              </h2>
              <p className="mt-7 max-w-xl text-base leading-8 text-white/78">
                As the cursor scrolls down the page, the background sequence continues, sections reveal naturally, and the stacked panels move in rhythm without breaking readability.
              </p>
            </FadeInUp>
          </div>

          <div className="space-y-8">
            {stackedFlow.map((item, index) => (
              <FadeInUp key={item.step} delay={index * 80}>
                <StackedPanel step={item.step} title={item.title} body={item.body} offset={index} />
              </FadeInUp>
            ))}
          </div>
        </div>
      </section>

      <section id="cta" className="relative z-10 px-6 pb-28 pt-10 sm:px-8 lg:px-10">
        <FadeInUp className="mx-auto max-w-7xl">
          <GlassShell className="rounded-[42px] p-8 sm:p-10 lg:p-14">
            <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
              <div>
                <div className="text-[11px] font-black uppercase tracking-[0.38em] text-cyan-200/78">Ready for production</div>
                <h2 className="mt-5 max-w-[14ch] text-4xl font-black leading-[0.92] tracking-[-0.07em] text-white sm:text-6xl">
                  A sharper homepage for the same Studio Pro product.
                </h2>
                <p className="mt-7 max-w-3xl text-base leading-8 text-white/76">
                  The landing page now uses cleaner hero motion, clearer AI visuals, better spacing, and more refined feature cards while staying aligned with the project subject.
                </p>
              </div>
              <div className="flex flex-col gap-4 sm:flex-row lg:flex-col">
                <Link href="/register" className="rounded-full bg-white px-7 py-4 text-center text-[11px] font-black uppercase tracking-[0.28em] text-black transition duration-300 hover:-translate-y-0.5 hover:bg-cyan-100">
                  Start Free
                </Link>
                <Link href="/login" className="rounded-full border border-white/15 bg-white/[0.04] px-7 py-4 text-center text-[11px] font-black uppercase tracking-[0.28em] text-white transition duration-300 hover:-translate-y-0.5 hover:bg-white/[0.1]">
                  Login
                </Link>
              </div>
            </div>
          </GlassShell>
        </FadeInUp>
      </section>

      <Footer />
    </main>
  );
}

function TopNav() {
  return (
    <header className="fixed left-0 right-0 top-0 z-50 px-5 py-5 sm:px-7 lg:px-10">
      <div className="mx-auto flex max-w-7xl items-center justify-between rounded-full border border-white/10 bg-[#07111d]/74 px-4 py-3 shadow-[0_24px_100px_rgba(0,0,0,0.32)] backdrop-blur-2xl sm:px-6">
        <Link href="/" className="flex items-center gap-3">
          <span className="h-2.5 w-2.5 rounded-full bg-cyan-300 shadow-[0_0_22px_rgba(103,232,249,0.95)]" />
          <span className="text-[11px] font-black uppercase tracking-[0.34em] text-white/90">Studio Pro</span>
        </Link>
        <div className="flex items-center gap-3">
          <nav className="hidden items-center gap-7 text-[11px] font-black uppercase tracking-[0.32em] text-white/62 md:flex">
            <a href="#home" className="transition hover:text-white">Home</a>
            <a href="#capabilities" className="transition hover:text-white">Tools</a>
            <a href="#workflow" className="transition hover:text-white">Workflow</a>
            <Link href="/login" className="transition hover:text-white">Login</Link>
          </nav>
          <ThemeToggle compact />
        </div>
      </div>
    </header>
  );
}

function AnimatedHero() {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => {
      setIndex((value) => (value + 1) % heroPhrases.length);
    }, 3400);
    return () => window.clearInterval(id);
  }, []);

  return (
    <div className="mt-7">
      <h1 className="max-w-[8.8ch] text-[clamp(3.6rem,9vw,7.4rem)] font-black leading-[0.88] tracking-[-0.075em] text-white drop-shadow-[0_24px_90px_rgba(0,0,0,0.92)]">
        <span className="block">Professional</span>
        <span className="block">flow</span>
        <span className="block bg-gradient-to-r from-white via-cyan-100 to-cyan-300 bg-clip-text text-transparent">from prompt to</span>
        <span className="relative mt-1 block min-h-[1.04em]">
          {heroPhrases.map((phrase, phraseIndex) => {
            const active = phraseIndex === index;
            return (
              <span
                key={phrase.ending}
                className="absolute inset-0 transition-all duration-700 ease-out"
                style={{
                  opacity: active ? 1 : 0,
                  transform: `translateY(${active ? 0 : 20}px)`,
                  filter: active ? "blur(0px)" : "blur(6px)",
                }}
              >
                {phrase.ending}
              </span>
            );
          })}
        </span>
      </h1>

      <div className="mt-7 min-h-[116px] max-w-2xl rounded-[28px] border border-white/10 bg-[#020812]/58 p-5 text-base leading-8 text-white/82 shadow-[0_26px_110px_rgba(0,0,0,0.46)] backdrop-blur-2xl sm:text-lg">
        <div className="relative h-full min-h-[76px]">
          {heroPhrases.map((phrase, phraseIndex) => {
            const active = phraseIndex === index;
            return (
              <p
                key={phrase.description}
                className="absolute inset-0 transition-all duration-700 ease-out"
                style={{
                  opacity: active ? 1 : 0,
                  transform: `translateY(${active ? 0 : 12}px)`,
                  filter: active ? "blur(0px)" : "blur(4px)",
                }}
              >
                {phrase.description}
              </p>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function HeroInfoPanel() {
  return (
    <GlassShell className="rounded-[34px] p-6 sm:p-7">
      <div className="flex items-start gap-4">
        <div className="relative flex h-16 w-16 shrink-0 items-center justify-center rounded-[20px] border border-cyan-200/18 bg-[linear-gradient(180deg,rgba(59,130,246,0.28),rgba(30,64,175,0.14))] shadow-[inset_0_1px_0_rgba(255,255,255,0.1)]">
          <Bot className="h-7 w-7 text-white" strokeWidth={1.8} />
          <div className="absolute -right-2 -top-2 rounded-full border border-cyan-200/18 bg-[#081221] px-2 py-1 text-[9px] font-black uppercase tracking-[0.22em] text-cyan-200/88 shadow-[0_10px_30px_rgba(0,0,0,0.3)]">
            AI
          </div>
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-[10px] font-black uppercase tracking-[0.28em] text-cyan-200/70">AI creative flow</div>
          <p className="mt-3 text-[1rem] leading-8 text-white/86">
            Built for creators and teams who want powerful AI tools that stay out of the way and keep the workflow moving.
          </p>
        </div>
      </div>

      <div className="mt-6 space-y-3">
        <InfoRow label="Image generation" value="Prompt, preview, history" />
        <InfoRow label="Image-to-image" value="Reference lock, transform, export" />
        <InfoRow label="Assistant" value="Compare, revise, continue" />
        <InfoRow label="Credits & admin" value="Usage, controls, tracking" />
      </div>
    </GlassShell>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-[18px] border border-white/8 bg-white/[0.04] px-4 py-4 text-sm shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
      <span className="text-white/68">{label}</span>
      <span className="text-right font-medium text-white/88">{value}</span>
    </div>
  );
}

function ProductCard({
  title,
  body,
  cta,
  href,
  number,
  titleTone,
  icon: Icon,
  art,
}: {
  title: string;
  body: string;
  cta: string;
  href: string;
  number: string;
  titleTone: string;
  icon: typeof ImageIcon;
  art: ReactNode;
}) {
  return (
    <Link href={href} className="group block h-full focus:outline-none">
      <div className="relative flex h-full min-h-[620px] flex-col overflow-hidden rounded-[34px] border border-white/12 bg-[linear-gradient(180deg,rgba(1,4,12,0.98),rgba(0,0,0,0.98))] p-6 shadow-[0_34px_130px_rgba(0,0,0,0.55)] transition duration-300 hover:-translate-y-2 hover:border-cyan-200/24 hover:shadow-[0_40px_150px_rgba(0,0,0,0.62)]">
        <div className="absolute inset-x-0 top-0 h-40 bg-[radial-gradient(circle_at_50%_0%,rgba(96,165,250,0.18),transparent_60%)]" />
        <div className="absolute inset-0 rounded-[34px] bg-[linear-gradient(180deg,rgba(255,255,255,0.02),transparent_20%,transparent_75%,rgba(255,255,255,0.02))]" />

        <div className="relative flex items-center justify-between">
          <div className="text-[11px] font-black uppercase tracking-[0.26em] text-white/76">{number}</div>
          <div className="flex h-11 w-11 items-center justify-center rounded-full border border-white/12 bg-white/[0.04] text-cyan-100/90">
            <Icon className="h-5 w-5" strokeWidth={1.8} />
          </div>
        </div>

        <div className="relative mt-5 flex h-[260px] items-center justify-center overflow-hidden rounded-[26px] border border-white/8 bg-[radial-gradient(circle_at_50%_50%,rgba(35,99,255,0.12),transparent_55%),linear-gradient(180deg,rgba(7,20,49,0.45),rgba(2,4,12,0.88))]">
          {art}
        </div>

        <div className="relative mt-8 whitespace-pre-line text-[42px] font-black leading-[0.98] tracking-[-0.06em] sm:text-[46px]">
          <span className={`bg-gradient-to-r ${titleTone} bg-clip-text text-transparent`}>{title}</span>
        </div>

        <p className="relative mt-8 text-[1rem] leading-9 text-white/82">{body}</p>

        <div className="relative mt-auto pt-12">
          <div className="flex items-center justify-center">
            <span className="inline-flex min-w-[138px] items-center justify-center rounded-full border border-cyan-300/55 px-6 py-3 text-sm font-medium text-white shadow-[0_0_0_1px_rgba(59,130,246,0.08),0_12px_32px_rgba(0,0,0,0.28)] transition duration-300 group-hover:border-cyan-200/85 group-hover:shadow-[0_0_0_1px_rgba(125,211,252,0.12),0_16px_36px_rgba(37,99,235,0.24)]">
              {cta}
            </span>
          </div>
        </div>
      </div>
    </Link>
  );
}

function StackedPanel({ step, title, body, offset }: { step: string; title: string; body: string; offset: number }) {
  return (
    <GlassShell
      className="rounded-[34px] p-7 sm:p-8 lg:sticky"
      style={{ top: `${110 + offset * 24}px`, transform: `translateY(${offset * 8}px)` }}
    >
      <div className="text-[10px] font-black uppercase tracking-[0.28em] text-cyan-200/70">Step {step}</div>
      <h3 className="mt-5 max-w-2xl text-2xl font-black leading-tight tracking-[-0.05em] text-white sm:text-[2rem]">{title}</h3>
      <p className="mt-5 max-w-2xl text-base leading-8 text-white/76">{body}</p>
      <div className="mt-7 inline-flex items-center gap-2 text-[11px] font-black uppercase tracking-[0.28em] text-cyan-300">
        <span>Keep scrolling</span>
        <ArrowRight className="h-4 w-4" />
      </div>
    </GlassShell>
  );
}

function GlassShell({ children, className = "", style }: { children: ReactNode; className?: string; style?: CSSProperties }) {
  return (
    <div
      className={`relative overflow-hidden border border-white/12 bg-[#071421]/72 shadow-[0_38px_150px_rgba(0,0,0,0.5)] backdrop-blur-2xl ${className}`}
      style={style}
    >
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,rgba(255,255,255,0.06),transparent_20%,transparent_80%,rgba(255,255,255,0.03))]" />
      <div className="relative">{children}</div>
    </div>
  );
}

function FadeInUp({ children, className = "", delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.unobserve(element);
        }
      },
      { threshold: 0.15, rootMargin: "0px 0px -10% 0px" }
    );

    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className={className}
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? "translateY(0px)" : "translateY(30px)",
        filter: visible ? "blur(0px)" : "blur(8px)",
        transition: "opacity 700ms ease, transform 700ms ease, filter 700ms ease",
        transitionDelay: `${delay}ms`,
      }}
    >
      {children}
    </div>
  );
}

function ShowcaseFrame({ children }: { children: ReactNode }) {
  return (
    <div className="relative h-[220px] w-[220px]">
      <div className="absolute inset-x-[8px] bottom-[22px] h-[88px] rounded-[30px] border border-cyan-200/28 bg-[linear-gradient(180deg,rgba(7,17,74,0.82),rgba(3,7,28,0.28))] shadow-[0_18px_60px_rgba(37,99,235,0.18)]" />
      <div className="absolute inset-x-[0px] bottom-[14px] h-[100px] rounded-[36px] border border-cyan-200/16" />
      <div className="absolute left-[42px] right-[42px] bottom-[11px] h-[14px] rounded-full bg-[radial-gradient(circle_at_50%_50%,rgba(255,255,255,0.94),rgba(255,255,255,0.08)_65%,transparent)] blur-[2px]" />
      {children}
    </div>
  );
}

function ImageGenerationArt() {
  return (
    <ShowcaseFrame>
      <svg viewBox="0 0 220 220" className="absolute inset-0 h-full w-full overflow-visible">
        <g className="animate-float-slow">
          <rect x="44" y="50" rx="18" ry="18" width="132" height="92" fill="rgba(13,33,92,0.92)" stroke="rgba(255,255,255,0.72)" />
          <rect x="52" y="58" rx="14" ry="14" width="116" height="76" fill="url(#ig-panel)" stroke="rgba(255,255,255,0.18)" />
          <circle cx="74" cy="78" r="9" fill="rgba(201,236,255,0.95)" />
          <path d="M66 122 L96 92 L118 112 L140 86 L154 122 Z" fill="rgba(223,237,255,0.92)" />
          <path d="M56 124 L92 96 L112 116 L140 82 L164 124 Z" fill="url(#ig-mountains)" opacity="0.9" />
        </g>
        <g className="animate-float-delay">
          <rect x="70" y="26" rx="18" ry="18" width="80" height="56" fill="rgba(31,76,196,0.82)" stroke="rgba(255,255,255,0.58)" />
          <rect x="80" y="36" rx="10" ry="10" width="60" height="36" fill="rgba(255,214,255,0.72)" />
        </g>
        <defs>
          <linearGradient id="ig-panel" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="rgba(34,87,255,0.95)" />
            <stop offset="100%" stopColor="rgba(114,215,255,0.56)" />
          </linearGradient>
          <linearGradient id="ig-mountains" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="rgba(255,215,255,0.88)" />
            <stop offset="100%" stopColor="rgba(74,130,255,0.88)" />
          </linearGradient>
        </defs>
      </svg>
    </ShowcaseFrame>
  );
}

function VideoGenerationArt() {
  return (
    <ShowcaseFrame>
      <svg viewBox="0 0 220 220" className="absolute inset-0 h-full w-full overflow-visible">
        <g className="animate-float-slow">
          <rect x="48" y="58" rx="24" ry="24" width="124" height="88" fill="rgba(16,43,116,0.85)" stroke="rgba(255,255,255,0.7)" />
          <rect x="58" y="68" rx="18" ry="18" width="104" height="68" fill="url(#vg-screen)" stroke="rgba(255,255,255,0.2)" />
          <polygon points="100,86 100,118 126,102" fill="rgba(255,255,255,0.92)" className="animate-pulse-soft" />
          <rect x="64" y="122" rx="4" ry="4" width="48" height="6" fill="rgba(220,239,255,0.64)" />
          <rect x="116" y="122" rx="4" ry="4" width="32" height="6" fill="rgba(99,200,255,0.72)" />
        </g>
        <g className="animate-float-delay">
          <rect x="70" y="34" rx="10" ry="10" width="72" height="20" fill="rgba(35,87,225,0.88)" stroke="rgba(255,255,255,0.6)" />
          <rect x="77" y="28" rx="4" ry="4" width="16" height="8" fill="rgba(255,255,255,0.82)" />
          <rect x="97" y="28" rx="4" ry="4" width="16" height="8" fill="rgba(255,255,255,0.82)" />
          <rect x="117" y="28" rx="4" ry="4" width="16" height="8" fill="rgba(255,255,255,0.82)" />
        </g>
        <circle cx="168" cy="42" r="8" fill="rgba(173,213,255,0.92)" className="animate-drift-orbit" />
        <defs>
          <linearGradient id="vg-screen" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="rgba(38,82,255,0.96)" />
            <stop offset="100%" stopColor="rgba(57,187,255,0.76)" />
          </linearGradient>
        </defs>
      </svg>
    </ShowcaseFrame>
  );
}

function AssistantArt() {
  return (
    <ShowcaseFrame>
      <svg viewBox="0 0 220 220" className="absolute inset-0 h-full w-full overflow-visible">
        <g className="animate-float-slow">
          <rect x="62" y="40" rx="28" ry="28" width="96" height="104" fill="url(#ai-chip)" stroke="rgba(255,255,255,0.74)" />
          <circle cx="92" cy="84" r="10" fill="rgba(255,255,255,0.92)" />
          <circle cx="128" cy="84" r="10" fill="rgba(255,255,255,0.92)" />
          <path d="M90 114 Q110 130 130 114" stroke="rgba(255,255,255,0.92)" strokeWidth="6" fill="none" strokeLinecap="round" />
        </g>
        <g className="animate-pulse-soft">
          <path d="M50 96 H72" stroke="rgba(119,198,255,0.82)" strokeWidth="4" strokeLinecap="round" />
          <path d="M148 96 H170" stroke="rgba(119,198,255,0.82)" strokeWidth="4" strokeLinecap="round" />
          <path d="M110 26 V40" stroke="rgba(119,198,255,0.82)" strokeWidth="4" strokeLinecap="round" />
          <path d="M110 144 V160" stroke="rgba(119,198,255,0.82)" strokeWidth="4" strokeLinecap="round" />
        </g>
        <g className="animate-drift-orbit" transform="translate(0 0)">
          <path d="M154 52 l8 16 l16 8 l-16 8 l-8 16 l-8-16 l-16-8 l16-8 z" fill="rgba(223,237,255,0.92)" />
          <path d="M58 118 l5 9 l9 5 l-9 5 l-5 9 l-5-9 l-9-5 l9-5 z" fill="rgba(145,195,255,0.86)" />
        </g>
        <defs>
          <linearGradient id="ai-chip" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="rgba(67,96,255,0.96)" />
            <stop offset="100%" stopColor="rgba(212,184,255,0.8)" />
          </linearGradient>
        </defs>
      </svg>
    </ShowcaseFrame>
  );
}

function CreditsAdminArt() {
  return (
    <ShowcaseFrame>
      <svg viewBox="0 0 220 220" className="absolute inset-0 h-full w-full overflow-visible">
        <g className="animate-float-slow">
          <ellipse cx="108" cy="62" rx="50" ry="18" fill="rgba(44,92,255,0.96)" stroke="rgba(255,255,255,0.74)" />
          <ellipse cx="108" cy="84" rx="50" ry="18" fill="rgba(67,112,255,0.82)" stroke="rgba(255,255,255,0.4)" />
          <ellipse cx="108" cy="106" rx="50" ry="18" fill="rgba(110,134,255,0.7)" stroke="rgba(255,255,255,0.34)" />
          <ellipse cx="108" cy="128" rx="50" ry="18" fill="rgba(234,213,255,0.76)" stroke="rgba(255,255,255,0.42)" />
          <rect x="152" y="52" rx="12" ry="12" width="34" height="56" fill="rgba(8,20,54,0.82)" stroke="rgba(255,255,255,0.42)" className="animate-float-delay" />
          <rect x="160" y="66" rx="3" ry="3" width="18" height="4" fill="rgba(118,201,255,0.86)" />
          <rect x="160" y="78" rx="3" ry="3" width="10" height="4" fill="rgba(255,255,255,0.82)" />
          <rect x="160" y="90" rx="3" ry="3" width="14" height="4" fill="rgba(118,201,255,0.86)" />
        </g>
      </svg>
    </ShowcaseFrame>
  );
}

function Footer() {
  return (
    <footer className="relative z-10 border-t border-white/10 bg-[#020812]/88 px-6 py-8 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl flex-col gap-3 text-[11px] uppercase tracking-[0.32em] text-white/45 sm:flex-row sm:items-center sm:justify-between">
        <span>© 2026 Studio Pro</span>
        <span>Image · Image-to-Image · Assistant · Credits</span>
      </div>
    </footer>
  );
}
