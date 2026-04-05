"use client";

import { BrainCircuit, CodeXml, Gauge, ScanSearch, ShieldCheck } from "lucide-react";

const microCards = [
  {
    title: "TTI forensics",
    copy: "Trace hesitation back to the exact moment scripts, layout, or media delayed confidence.",
    icon: Gauge,
  },
  {
    title: "Cognitive load",
    copy: "See where density, hierarchy, and messaging stack too much effort into one screen.",
    icon: BrainCircuit,
  },
  {
    title: "Fix handoff",
    copy: "Turn evidence into a repair brief instead of losing the thread between audit and implementation.",
    icon: CodeXml,
  },
];

export function LandingBentoGrid() {
  return (
    <section className="px-5 py-16 md:px-8 lg:px-10">
      <div className="mx-auto grid max-w-7xl gap-6 md:grid-cols-3">
        <article className="glass-panel relative overflow-hidden rounded-[1.5rem] border border-[#2A2A2A] p-8 md:col-span-2">
          <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(255,255,255,0.02),transparent_22%)]" />
          <div className="relative flex h-full flex-col justify-between gap-8">
            <div>
              <p className="text-[10px] uppercase tracking-[0.24em] text-slate-500">Moment 2: Solution</p>
              <h3 className="font-display mt-4 max-w-xl text-3xl font-semibold leading-tight text-white md:text-4xl">
                Turn browser evidence into a clear engineering fix.
              </h3>
              <p className="mt-5 max-w-2xl text-base leading-8 text-slate-300">
                The product should move from detection into a repair surface without dumping the user into raw logs or
                disconnected screenshots.
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-[1.1rem] border border-[#2A2A2A] bg-black/20 p-5">
                <div className="flex size-12 items-center justify-center rounded-2xl bg-white/5 text-blue-300">
                  <ScanSearch className="size-5" />
                </div>
                <p className="mt-4 text-sm uppercase tracking-[0.2em] text-slate-500">Observed directly</p>
                <p className="mt-2 text-sm leading-7 text-slate-200">
                  Browser Use sessions capture routes, screenshots, friction notes, and persona-specific context.
                </p>
              </div>
              <div className="rounded-[1.1rem] border border-[#2A2A2A] bg-black/20 p-5">
                <div className="flex size-12 items-center justify-center rounded-2xl bg-white/5 text-blue-300">
                  <ShieldCheck className="size-5" />
                </div>
                <p className="mt-4 text-sm uppercase tracking-[0.2em] text-slate-500">Reviewed separately</p>
                <p className="mt-2 text-sm leading-7 text-slate-200">
                  Hosted review stays downstream so teams can compare raw evidence with synthesized priority.
                </p>
              </div>
            </div>
          </div>
        </article>

        <article className="glass-panel rounded-[1.5rem] border border-[#2A2A2A] p-8 text-center">
          <div className="mx-auto flex size-24 items-center justify-center rounded-full border-4 border-blue-400/15 bg-blue-500/8">
            <span className="font-display text-5xl font-semibold text-white">84</span>
          </div>
          <h3 className="font-display mt-6 text-2xl font-semibold text-white">UX health score</h3>
          <p className="mt-2 text-[11px] uppercase tracking-[0.24em] text-slate-500">Moment 3: Insight</p>

          <div className="mt-6 h-1.5 overflow-hidden rounded-full bg-white/8">
            <div className="h-full w-[84%] bg-blue-400" />
          </div>

          <p className="mt-6 text-sm leading-7 text-slate-300">
            "Structured feedback your team can act on, prioritized by friction and audience impact."
          </p>
        </article>

        {microCards.map((card) => {
          const Icon = card.icon;
          return (
            <article
              key={card.title}
              className="rounded-[1.2rem] border border-[#2A2A2A] bg-white/[0.02] p-6 backdrop-blur-sm"
            >
              <div className="flex size-12 items-center justify-center rounded-2xl bg-blue-500/10 text-blue-300">
                <Icon className="size-5" />
              </div>
              <h4 className="font-display mt-5 text-2xl font-semibold text-white">{card.title}</h4>
              <p className="mt-3 text-sm leading-7 text-slate-300">{card.copy}</p>
            </article>
          );
        })}
      </div>
    </section>
  );
}
