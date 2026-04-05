"use client";

import { useEffect, useRef, useState } from "react";

type ScrollSectionProps = {
  children: React.ReactNode;
  className?: string;
};

export function ScrollSection({ children, className = "" }: ScrollSectionProps) {
  const ref = useRef<HTMLElement | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const element = ref.current;
    if (!element || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setVisible(true);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: "0px 0px -10% 0px", threshold: 0.14 },
    );

    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return (
    <section
      ref={ref}
      className={`landing-reveal ${visible ? "is-visible" : ""} ${className}`.trim()}
    >
      {children}
    </section>
  );
}
