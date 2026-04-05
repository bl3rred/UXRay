"use client";

import { useEffect, useMemo, useState } from "react";

import { resolveAssetUrl } from "../../lib/api";

type SmartImageProps = {
  src: string | null | undefined;
  fallbackSrcs?: Array<string | null | undefined>;
  alt: string;
  className?: string;
  fallbackClassName?: string;
  fallbackLabel?: string;
};

export function SmartImage({
  src,
  fallbackSrcs,
  alt,
  className,
  fallbackClassName,
  fallbackLabel = "Image unavailable",
}: SmartImageProps) {
  const [failedIndex, setFailedIndex] = useState(0);
  const resolvedCandidates = useMemo(
    () =>
      [src, ...(fallbackSrcs ?? [])]
        .map((candidate) => (candidate ? resolveAssetUrl(candidate) : ""))
        .filter((candidate, index, candidates) => candidate && candidates.indexOf(candidate) === index),
    [fallbackSrcs, src],
  );
  const resolved = resolvedCandidates[failedIndex] ?? "";

  useEffect(() => {
    setFailedIndex(0);
  }, [resolvedCandidates]);

  if (!resolved) {
    return (
      <div
        className={
          fallbackClassName ??
          "flex min-h-32 items-center justify-center rounded-2xl border border-border bg-black/20 px-4 py-6 text-center text-sm text-body"
        }
      >
        {fallbackLabel}
      </div>
    );
  }

  return (
    <img
      src={resolved}
      alt={alt}
      className={className}
      onError={() => setFailedIndex((current) => current + 1)}
    />
  );
}
