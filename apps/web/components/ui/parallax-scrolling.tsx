"use client";

import { useEffect, useRef } from "react";
import { ArrowUpRight, ScanSearch } from "lucide-react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

const layers = [
  {
    id: "1",
    yPercent: 66,
    image:
      "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=1400&q=80",
    alt: "Detailed analytics dashboard on a laptop in a dark studio.",
  },
  {
    id: "2",
    yPercent: 48,
    image:
      "https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&w=1400&q=80",
    alt: "Team reviewing product analytics on a large screen.",
  },
  {
    id: "4",
    yPercent: 14,
    image:
      "https://images.unsplash.com/photo-1498050108023-c5249f4df085?auto=format&fit=crop&w=1400&q=80",
    alt: "Engineer working through product telemetry and bug reports.",
  },
];

export function ParallaxComponent() {
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return;
    }

    gsap.registerPlugin(ScrollTrigger);

    const rootElement = rootRef.current;
    if (!rootElement) {
      return;
    }

    const triggerElement = rootElement.querySelector<HTMLElement>("[data-parallax-layers]");
    if (!triggerElement) {
      return;
    }

    const introElements = rootElement.querySelectorAll<HTMLElement>("[data-scroll-reveal]");
    introElements.forEach((element) => {
      gsap.fromTo(
        element,
        { autoAlpha: 0, y: 18 },
        {
          autoAlpha: 1,
          y: 0,
          duration: 0.7,
          ease: "power2.out",
          scrollTrigger: {
            trigger: element,
            start: "top 82%",
            once: true,
          },
        },
      );
    });

    const timeline = gsap.timeline({
      scrollTrigger: {
        trigger: triggerElement,
        start: "top bottom",
        end: "bottom top",
        scrub: 0.45,
      },
    });

    layers.forEach((layer, index) => {
      timeline.to(
        triggerElement.querySelectorAll(`[data-parallax-layer="${layer.id}"]`),
        {
          yPercent: layer.yPercent,
          ease: "none",
        },
        index === 0 ? undefined : "<",
        );
      });

    return () => {
      timeline.kill();
      ScrollTrigger.getAll().forEach((instance) => instance.kill());
    };
  }, []);

  return (
    <section
      ref={rootRef}
      className="relative overflow-hidden rounded-[1.5rem] border border-[#2A2A2A] bg-[#121212] shadow-panel"
    >
      <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(255,255,255,0.02),transparent_18%)]" />

      <div className="relative px-6 py-8 md:px-10 md:py-10">
        <div
          data-scroll-reveal
          className="flex flex-wrap items-center justify-between gap-4 border-b border-[#2A2A2A] pb-6"
        >
          <div>
            <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
              Evidence scroll
            </p>
            <h2 className="font-display mt-3 text-3xl font-semibold text-white md:text-5xl">
              Smooth motion, minimal noise.
            </h2>
          </div>

          <div className="max-w-sm text-sm leading-6 text-slate-300">
            The page should evolve as you scroll, but it should never hijack the wheel or
            fight the user for control.
          </div>
        </div>

        <div
          data-parallax-layers
          className="relative mt-8 min-h-[34rem] overflow-hidden rounded-[1.5rem] border border-[#2A2A2A] bg-[#0f0f0f] md:min-h-[40rem]"
        >
          <div className="absolute inset-0 bg-gradient-to-b from-white/[0.03] via-transparent to-black/60" />

          <div
            data-parallax-layer="1"
            className="absolute inset-x-[8%] top-[8%] h-[52%] overflow-hidden rounded-[1.25rem] border border-[#2A2A2A] shadow-2xl shadow-black/20"
          >
            <img
              src={layers[0].image}
              alt={layers[0].alt}
              className="h-full w-full object-cover"
            />
          </div>

          <div
            data-parallax-layer="2"
            className="absolute inset-x-[16%] top-[24%] h-[50%] overflow-hidden rounded-[1.15rem] border border-[#2A2A2A] shadow-2xl shadow-black/20"
          >
            <img
              src={layers[1].image}
              alt={layers[1].alt}
              className="h-full w-full object-cover"
            />
          </div>

          <div
            data-parallax-layer="3"
            className="absolute inset-x-[8%] top-[18%] flex h-[52%] items-center justify-center"
          >
            <div className="rounded-[1.35rem] border border-[#2A2A2A] bg-[#161616]/92 px-6 py-8 text-center shadow-2xl shadow-black/25 backdrop-blur-sm md:px-12">
              <div className="mx-auto mb-5 flex size-16 items-center justify-center rounded-full border border-blue-400/20 bg-blue-500/10 text-blue-300">
                <ScanSearch className="size-8" />
              </div>
              <p className="text-xs uppercase tracking-[0.32em] text-slate-500">
                Browser evidence
              </p>
              <h3 className="font-display mt-4 text-4xl font-semibold text-white md:text-6xl">
                Detection to insight
              </h3>
              <p className="mx-auto mt-4 max-w-md text-sm leading-6 text-slate-300 md:text-base">
                Scroll should reveal the product story naturally: detection, suggested fix,
                and structured summary.
              </p>
            </div>
          </div>

          <div
            data-parallax-layer="4"
            className="absolute inset-x-[24%] top-[46%] h-[38%] overflow-hidden rounded-[1rem] border border-[#2A2A2A] shadow-2xl shadow-black/20"
          >
            <img
              src={layers[2].image}
              alt={layers[2].alt}
              className="h-full w-full object-cover"
            />
          </div>

          <div className="absolute inset-x-0 bottom-0 h-48 bg-gradient-to-t from-[#0f0f0f] via-[#0f0f0f]/70 to-transparent" />
        </div>

        <div
          data-scroll-reveal
          className="mt-6 flex flex-wrap items-center justify-between gap-4 text-sm text-slate-300"
        >
          <div className="inline-flex items-center gap-3 rounded-full border border-[#2A2A2A] bg-white/[0.03] px-4 py-2">
            <ArrowUpRight className="size-4 text-blue-300" />
            Scroll animations now follow the page instead of owning it.
          </div>
          <p className="text-xs uppercase tracking-[0.22em] text-slate-600">
            Native scroll first, motion second
          </p>
        </div>
      </div>
    </section>
  );
}
