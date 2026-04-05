import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { ScrollSection } from "../components/ui/scroll-section";

export default function LandingPage() {
  return (
    <>
      <header className="fixed top-0 z-50 h-16 w-full border-b hairline-border border-white/5 bg-[#080808]/80 px-6 backdrop-blur-md md:px-8">
        <div className="flex h-full w-full items-center justify-between">
          <div className="relative -ml-3 flex h-full w-[260px] items-center overflow-visible md:-ml-6 md:w-[468px]">
            <img
              alt="UXRay"
              className="absolute left-0 top-1/2 h-[5.4rem] w-auto -translate-y-1/2 object-contain object-left md:h-[6.75rem]"
              src="/logo transparent background.png"
            />
          </div>

          <div className="flex items-center pr-3 md:pr-6">
            <Link
              href="/login"
              className="text-xs font-medium uppercase tracking-[0.24em] text-white transition hover:text-zinc-300"
            >
              Log in
            </Link>
          </div>
        </div>
      </header>

      <main className="min-h-screen pt-16 md:pt-18">
        <section className="px-6 pb-32 pt-28 md:px-8 md:pb-40 md:pt-36">
          <div className="mx-auto max-w-5xl text-center">
            <div className="inline-flex items-center gap-2 rounded-full border hairline-border border-white/10 px-4 py-2 text-[10px] uppercase tracking-[0.28em] text-zinc-500">
              premium developer-first ux auditing
            </div>
            <h1 className="mt-10 font-display text-5xl font-black tracking-[-0.04em] leading-[0.95] text-white md:text-[5.5rem]">
              Catch UX failures
              <br />
              before your users do.
            </h1>
            <p className="mx-auto mt-10 max-w-2xl text-lg font-light leading-relaxed text-zinc-500 md:text-xl">
              Deploy autonomous browser agents to test your product like real users. Get
              screenshot-based friction reports and code-grounded fix suggestions.
            </p>
            <div className="mt-14 flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Link
                href="/login"
                className="inline-flex items-center gap-2 bg-white px-10 py-3.5 text-xs font-bold uppercase tracking-[0.24em] text-black transition hover:bg-zinc-200"
              >
                Start audit
                <ArrowRight className="size-4" />
              </Link>
            </div>
          </div>
        </section>

        <ScrollSection className="px-6 pb-40 md:px-8 md:pb-56">
          <div className="mx-auto max-w-6xl">
            <div className="overflow-hidden rounded-sm border hairline-border border-white/10 bg-[#0c0c0c] shadow-[0_0_80px_-20px_rgba(0,0,0,1)]">
              <div className="flex h-10 items-center justify-between border-b hairline-border border-white/5 bg-black/40 px-4">
                <div className="flex gap-1.5">
                  <div className="h-2.5 w-2.5 rounded-full bg-white/10" />
                  <div className="h-2.5 w-2.5 rounded-full bg-white/10" />
                  <div className="h-2.5 w-2.5 rounded-full bg-white/10" />
                </div>
                <div className="font-mono text-[10px] tracking-tight text-zinc-600">
                  app.uxray.forensic/audit/live_session
                </div>
                <div className="w-12" />
              </div>

              <div className="grid min-h-[500px] grid-cols-1 gap-12 p-8 md:grid-cols-12">
                <div className="flex flex-col gap-8 md:col-span-7">
                  <div className="group relative aspect-video overflow-hidden border hairline-border border-white/5 bg-black/40">
                    <img
                      alt="Minimal data visualization"
                      className="h-full w-full object-cover opacity-20 grayscale"
                      src="https://lh3.googleusercontent.com/aida-public/AB6AXuCA_wXuj8CYnsvCsY6ThqsJGqECAwMCLX2eTLNNkx7EDuXoDYE2yYpeeF03irY_Kg0X2ZFgImKN-mQVh0Y-sgouomA6bSTXnRqzjSGNPmWZbxTdjOmCaz2JF31CWqnIr4eTBXyBhASDI72KIhl-v5wuRjavy6AaZGMaYZ57PnZdHIzM3-WeZzWhvRbhA1K_g6NhTAiUuY20kYIAItETNx5pQZcVBcGVPFDOX7-fSLojGq5FKqvuRj6lK8z-weToXWKLddAN466J2E0"
                    />
                    <div className="absolute inset-0 p-6">
                      <div className="flex items-start justify-between">
                        <div className="border-l border-white/20 bg-black/60 p-4 backdrop-blur-sm">
                          <div className="mb-1 font-mono text-[9px] uppercase tracking-widest text-zinc-500">
                            Status
                          </div>
                          <div className="text-sm font-bold tracking-tight text-white">
                            ERR_RAGE_CLICK
                          </div>
                        </div>
                        <div className="border-l border-white/20 bg-black/60 p-4 backdrop-blur-sm">
                          <div className="mb-1 font-mono text-[9px] uppercase tracking-widest text-zinc-500">
                            Latency
                          </div>
                          <div className="text-sm font-bold tracking-tight text-white">
                            142ms
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-4">
                    <div className="h-px flex-1 bg-white/5" />
                    <span className="font-mono text-[10px] uppercase tracking-widest text-zinc-600">
                      Temporal Analysis Graph
                    </span>
                    <div className="h-px flex-1 bg-white/5" />
                  </div>
                </div>

                <div className="flex flex-col gap-10 md:col-span-5">
                  <div className="space-y-4">
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 w-1.5 rounded-full bg-[#ffb4ab]" />
                      <span className="font-mono text-[10px] font-medium uppercase tracking-[0.2em] text-[#ffb4ab]">
                        Layout Shift
                      </span>
                    </div>
                    <h4 className="text-lg font-medium tracking-tight text-white">
                      CLS detected in Hero container.
                    </h4>
                    <p className="text-sm font-light leading-relaxed text-zinc-500">
                      Asset hydration causing 120px height fluctuation on mobile viewports.
                    </p>
                    <div className="pt-4">
                      <pre className="border hairline-border border-white/5 bg-black/40 p-4 font-mono text-[11px] text-zinc-400">
                        .hero {`{ min-height: 480px; }`}
                      </pre>
                    </div>
                  </div>

                  <div className="h-px bg-white/5" />

                  <div className="space-y-4">
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 w-1.5 rounded-full bg-zinc-600" />
                      <span className="font-mono text-[10px] font-medium uppercase tracking-[0.2em] text-zinc-500">
                        Contrast Log
                      </span>
                    </div>
                    <h4 className="text-lg font-medium tracking-tight text-white">
                      WCAG AA Failure.
                    </h4>
                    <p className="text-sm font-light text-zinc-500">
                      Input placeholder contrast ratio below 4.5:1 in footer.
                    </p>
                    <div className="flex gap-3">
                      <div className="h-6 w-6 border hairline-border border-white/10 bg-[#333]" />
                      <ArrowRight className="size-6 text-zinc-700" />
                      <div className="h-6 w-6 border hairline-border border-white/10 bg-[#adc6ff]" />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </ScrollSection>

        <ScrollSection className="border-t hairline-border border-white/5 px-6 py-32 md:px-8 md:py-40">
          <div className="mx-auto grid max-w-6xl grid-cols-1 items-center gap-20 lg:grid-cols-2">
            <div className="space-y-10">
              <div className="space-y-5">
                <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-zinc-600">
                  01 / Speed
                </span>
                <h2 className="font-display text-5xl font-bold tracking-tight text-white">
                  TTI Forensics
                </h2>
                <p className="max-w-lg text-lg font-light leading-relaxed text-zinc-500">
                  Isolate script bottlenecks per component with sub-millisecond accuracy.
                  UXRay monitors dead clicks and click delay to identify where execution lag
                  directly impacts experience.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-8">
                <div>
                  <div className="mb-2 font-mono text-[10px] uppercase text-zinc-500">
                    Resolution
                  </div>
                  <div className="font-mono text-2xl text-white">0.01ms</div>
                </div>
                <div>
                  <div className="mb-2 font-mono text-[10px] uppercase text-zinc-500">
                    Metrics
                  </div>
                  <div className="font-mono text-2xl text-white">FID / LCP / TBT</div>
                </div>
              </div>
            </div>

            <div className="border hairline-border border-white/10 bg-[#0c0c0c] p-8">
              <div className="mb-6 flex h-48 items-end gap-1">
                {[20, 35, 60, 45, 90, 30, 15].map((height, index) => (
                  <div
                    key={`${height}-${index}`}
                    className={`flex-1 ${index === 4 ? "bg-[#ffb4ab]" : height > 40 ? "bg-white/10" : "bg-white/5"}`}
                    style={{ height: `${height}%` }}
                  />
                ))}
              </div>
              <div className="flex justify-between font-mono text-[9px] uppercase tracking-widest text-zinc-700">
                <span>Script Load</span>
                <span>Interaction Start</span>
                <span>Main Thread Idle</span>
              </div>
            </div>
          </div>
        </ScrollSection>

        <ScrollSection className="border-t hairline-border border-white/5 px-6 py-32 md:px-8 md:py-40">
          <div className="mx-auto grid max-w-6xl grid-cols-1 items-center gap-20 lg:grid-cols-2">
            <div className="order-last space-y-10 lg:order-first">
              <div className="space-y-5">
                <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-zinc-600">
                  02 / Logic
                </span>
                <h2 className="font-display text-5xl font-bold tracking-tight text-white">
                  Cognitive Load
                </h2>
                <p className="max-w-lg text-lg font-light leading-relaxed text-zinc-500">
                  Map visual density to identify user fatigue before it impacts conversion.
                  Autonomous agents simulate different personas and detect where complex layouts
                  cause hesitation or retries.
                </p>
              </div>

              <ul className="space-y-4 font-mono text-sm text-zinc-400">
                {[
                  "Visual Saliency Mapping",
                  "Persona-Based Intent Modeling",
                  "Decision Friction Analysis",
                ].map((item) => (
                  <li key={item} className="flex items-center gap-3">
                    <span className="h-1.5 w-1.5 rounded-full bg-[#adc6ff]" />
                    {item}
                  </li>
                ))}
              </ul>
            </div>

            <div className="mx-auto max-w-md bg-[#0c0c0c]">
              <img
                alt="Cognitive Load Mapping technical diagram"
                className="block h-auto w-full mix-blend-lighten opacity-95 [filter:brightness(1.08)_contrast(1.08)]"
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuCFQO51B41FZA_Q08PRlEQDM8jLT3rukHiLGFckPLh0t1w0nNAnuplq4qT9uliAXhKIceSX5G_wMhsOpw6mhmQyBRqPLwArgrN1MgngfK9NqjKraXhmdHmmfEnt9oR9IPFBtrUvn9l9Fbb8gfBLRIrSEDC26C1GzdrUh3KcA5SAWCQO6gp38E8_yC4u9dnNnbgYMwEnNUkorYtIOtZd5ACJl2XuuUM8325ONFFprfQkf6_p5JukzZAgA4qVFV1zw4q6-FViOk0d7a0"
              />
            </div>
          </div>
        </ScrollSection>

        <ScrollSection className="border-t hairline-border border-white/5 px-6 py-32 md:px-8 md:py-40">
          <div className="mx-auto grid max-w-6xl grid-cols-1 items-center gap-20 lg:grid-cols-2">
            <div className="space-y-10">
              <div className="space-y-5">
                <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-zinc-600">
                  03 / Auto
                </span>
                <h2 className="font-display text-5xl font-bold tracking-tight text-white">
                  Patch Engine
                </h2>
                <p className="max-w-lg text-lg font-light leading-relaxed text-zinc-500">
                  One-click code deployments based on automated forensic audit results. When
                  connected to your repository, UXRay maps issues to likely source files and
                  generates fix suggestions grounded in your code.
                </p>
              </div>

              <button className="border border-white/10 px-8 py-3 text-xs font-bold uppercase tracking-[0.24em] text-white transition hover:bg-white hover:text-black">
                Connect Repository
              </button>
            </div>

            <div className="overflow-hidden rounded-sm border hairline-border border-white/10 bg-black shadow-2xl">
              <div className="flex h-8 items-center gap-1.5 bg-zinc-900 px-4">
                <div className="h-2 w-2 rounded-full bg-white/10" />
                <div className="h-2 w-2 rounded-full bg-white/10" />
                <div className="h-2 w-2 rounded-full bg-white/10" />
              </div>
              <div className="p-6 font-mono text-xs leading-relaxed text-zinc-400">
                <div className="mb-2 text-zinc-600">// Suggested fix for Layout Shift</div>
                {[
                  ["24", "- .hero {"],
                  ["25", "-   padding-top: 12vh;"],
                  ["26", "- }"],
                  ["27", "+ .hero {"],
                  ["28", "+   min-height: 480px;"],
                  ["29", "+   padding-top: 12vh;"],
                  ["30", "+ }"],
                ].map(([line, text], index) => (
                  <div key={line} className="flex gap-4">
                    <span className="text-zinc-700">{line}</span>
                    <span className={index < 3 ? "font-medium text-[#ffb4ab]" : "font-medium text-[#adc6ff]"}>
                      {text}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </ScrollSection>
      </main>

      <footer className="flex h-16 items-center justify-between border-t hairline-border border-white/5 px-6 font-mono text-[10px] uppercase tracking-widest text-zinc-600 md:px-8">
        <div className="flex gap-8">
          <span>UXRay © 2024</span>
          <span className="text-zinc-800">|</span>
          <span>Version 2.4.0</span>
        </div>
        <div className="flex gap-8">
          <span className="transition hover:text-white">System: Operational</span>
          <span className="transition hover:text-white">Privacy</span>
        </div>
      </footer>
    </>
  );
}
