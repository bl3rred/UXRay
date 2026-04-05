"use client";

import {
  Activity,
  AlertTriangle,
  ChevronRight,
  Lock,
  ShieldAlert,
  TerminalSquare,
  TimerReset,
} from "lucide-react";

const heroFeed = [
  {
    eyebrow: "Issue detected",
    title: "Unexpected layout shift during asset hydration",
    copy:
      "The hero container jumps after media loads on mobile, pushing the primary action below the fold at the highest intent moment.",
    tone:
      "border-red-400/20 bg-red-500/10 text-red-100 shadow-[0_12px_40px_rgba(244,63,94,0.08)]",
    icon: AlertTriangle,
    labelTone: "text-red-200",
    code: [
      ".hero-frame {",
      "  min-height: 480px;",
      "  aspect-ratio: 16 / 9;",
      "}",
    ],
  },
  {
    eyebrow: "Diagnostic log",
    title: "Contrast and emphasis drift near the decision path",
    copy:
      "The pricing path is discoverable, but weaker than the hero CTA. Trust support and navigation hierarchy arrive too late in the sequence.",
    tone: "border-[#2A2A2A] bg-white/[0.03] text-slate-100",
    icon: TerminalSquare,
    labelTone: "text-sky-200",
    code: null,
  },
];

const eventTrail = [
  "First-time visitor hesitated after click because the button state never changed.",
  "Intent-driven persona routed around login and found pricing through the footer.",
  "Trust evaluator reached the signup route and marked reassurance copy as visually secondary.",
];

export function ForensicViewport() {
  return (
    <section className="relative">
      <div className="relative overflow-hidden rounded-[1.6rem] border border-[#2A2A2A] bg-[#121212] shadow-panel">
        <div className="flex items-center justify-between border-b border-[#2A2A2A] bg-black/20 px-4 py-3">
          <div className="flex items-center gap-4">
            <div className="flex gap-2">
              <span className="size-3 rounded-full bg-red-400/30" />
              <span className="size-3 rounded-full bg-amber-300/30" />
              <span className="size-3 rounded-full bg-emerald-300/30" />
            </div>
            <div className="hidden items-center gap-2 rounded-full border border-[#2A2A2A] bg-white/[0.03] px-3 py-1 text-[11px] uppercase tracking-[0.22em] text-slate-500 md:flex">
              <Lock className="size-3.5" />
              app.uxray.forensic/live_session_9283
            </div>
          </div>

          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.22em] text-slate-600">
            <Activity className="size-3.5 text-sky-300" />
            system optimal
          </div>
        </div>

        <div className="grid min-h-[38rem] lg:grid-cols-[56px_1fr]">
          <div className="hidden border-r border-[#2A2A2A] bg-black/10 py-5 lg:flex lg:flex-col lg:items-center lg:justify-between">
            <div className="flex w-full flex-col items-center gap-3">
              {[
                { icon: Activity, active: true },
                { icon: ShieldAlert, active: false },
                { icon: TimerReset, active: false },
                { icon: TerminalSquare, active: false },
              ].map((item, index) => {
                const Icon = item.icon;
                return (
                  <div
                    key={index}
                    className={`flex h-12 w-full items-center justify-center border-l-2 ${
                      item.active
                        ? "border-sky-400 bg-sky-400/10 text-sky-200"
                        : "border-transparent text-slate-600"
                    }`}
                  >
                    <Icon className="size-4" />
                  </div>
                );
              })}
            </div>

            <div className="text-[10px] uppercase tracking-[0.18em] text-slate-600">v2.4</div>
          </div>

          <div className="grid gap-4 bg-[#111111] p-4 lg:grid-cols-12 lg:p-5">
            <div className="relative overflow-hidden rounded-[1.25rem] border border-[#2A2A2A] bg-[#151515] lg:col-span-8">
              <img
                src="https://images.unsplash.com/photo-1516321497487-e288fb19713f?auto=format&fit=crop&w=1600&q=80"
                alt="Dark analytics interface projected on large monitors."
                className="h-full w-full object-cover opacity-30 grayscale"
              />
              <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(15,15,15,0.1),rgba(15,15,15,0.82))]" />

              <div className="absolute inset-0 flex flex-col justify-between p-5 md:p-8">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="rounded-[1rem] border-l-2 border-sky-400 bg-black/45 px-4 py-3 backdrop-blur-sm">
                    <p className="text-[10px] uppercase tracking-[0.24em] text-sky-300">Cursor trajectory</p>
                    <p className="mt-2 font-display text-2xl text-white md:text-3xl">ERR_RAGE_CLICK</p>
                  </div>
                  <div className="rounded-[1rem] border-l-2 border-red-400 bg-black/45 px-4 py-3 backdrop-blur-sm">
                    <p className="text-[10px] uppercase tracking-[0.24em] text-red-200">Live latency</p>
                    <p className="mt-2 font-display text-2xl text-white md:text-3xl">142ms</p>
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="max-w-[24rem] rounded-[1rem] border border-[#2A2A2A] bg-black/40 px-4 py-3 backdrop-blur-sm">
                    <p className="text-[10px] uppercase tracking-[0.24em] text-slate-500">Moment 1: Detection</p>
                    <p className="mt-2 text-sm leading-6 text-slate-200">
                      UXRay catches the moment the interaction fails instead of smoothing over the hesitation.
                    </p>
                  </div>

                  <div className="flex h-20 items-end gap-2 rounded-[1rem] border border-[#2A2A2A] bg-black/35 px-4 pb-4 pt-3 backdrop-blur-sm">
                    {[14, 32, 58, 84, 90, 28, 12].map((height, index) => (
                      <div
                        key={height}
                        className={`flex-1 rounded-t-sm ${
                          index === 3 || index === 4 ? "bg-red-400/75" : "bg-sky-300/45"
                        }`}
                        style={{ height: `${height}%` }}
                      />
                    ))}
                  </div>
                </div>
              </div>
            </div>

            <div className="flex flex-col gap-4 lg:col-span-4">
              {heroFeed.map((item) => {
                const Icon = item.icon;
                return (
                  <article
                    key={item.title}
                    className={`rounded-[1.1rem] border p-4 ${item.tone}`}
                  >
                    <div className="flex items-center gap-2">
                      <Icon className={`size-4 ${item.labelTone}`} />
                      <p className={`text-[10px] uppercase tracking-[0.24em] ${item.labelTone}`}>{item.eyebrow}</p>
                    </div>

                    <h3 className="mt-3 font-display text-xl font-semibold leading-tight">{item.title}</h3>
                    <p className="mt-3 text-sm leading-6 text-slate-300">{item.copy}</p>

                    {item.code ? (
                      <pre className="mt-4 overflow-hidden rounded-[1rem] border border-[#2A2A2A] bg-[#101010] p-3 text-[11px] leading-5 text-slate-300">
                        {item.code.join("\n")}
                      </pre>
                    ) : (
                      <div className="mt-4 flex items-center gap-3 text-sm text-slate-300">
                        <div className="size-4 border border-[#2A2A2A] bg-[#575757]" />
                        <ChevronRight className="size-4 text-slate-500" />
                        <div className="size-4 border border-[#2A2A2A] bg-sky-300/80" />
                      </div>
                    )}
                  </article>
                );
              })}

              <article className="rounded-[1.1rem] border border-[#2A2A2A] bg-white/[0.02] p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.24em] text-slate-500">Evidence trail</p>
                    <h3 className="mt-2 font-display text-xl font-semibold text-white">One run, several lenses.</h3>
                  </div>
                  <div className="rounded-full border border-blue-400/20 bg-blue-500/10 px-3 py-1 text-[10px] uppercase tracking-[0.2em] text-blue-200">
                    merged
                  </div>
                </div>

                <div className="mt-4 space-y-3">
                  {eventTrail.map((entry) => (
                    <div key={entry} className="rounded-[1rem] border border-[#2A2A2A] bg-black/20 px-3 py-3 text-sm text-slate-200">
                      {entry}
                    </div>
                  ))}
                </div>
              </article>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
