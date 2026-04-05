"use client";

import { useEffect, useRef, useState } from "react";

export function usePolling<T>(
  loader: () => Promise<T>,
  intervalMs: number,
  active: boolean,
  shouldContinue?: (data: T | null) => boolean,
) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const mountedRef = useRef(true);
  const loaderRef = useRef(loader);
  const shouldContinueRef = useRef(shouldContinue);
  const latestDataRef = useRef<T | null>(null);

  useEffect(() => {
    loaderRef.current = loader;
  }, [loader]);

  useEffect(() => {
    shouldContinueRef.current = shouldContinue;
  }, [shouldContinue]);

  useEffect(() => {
    latestDataRef.current = data;
  }, [data]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    let timer: number | undefined;
    let cancelled = false;

    async function load(isInitial = false) {
      try {
        if (isInitial || latestDataRef.current === null) {
          setLoading(true);
        }
        const next = await loaderRef.current();
        if (cancelled) {
          return;
        }
        if (mountedRef.current) {
          latestDataRef.current = next;
          setData(next);
          setError(null);
        }
        const keepPolling = active && (shouldContinueRef.current ? shouldContinueRef.current(next) : true);
        if (keepPolling) {
          timer = window.setTimeout(() => {
            void load();
          }, intervalMs);
        }
      } catch (loadError) {
        if (mountedRef.current) {
          setError(
            loadError instanceof Error ? loadError.message : "Failed to load data",
          );
        }
        if (active && !cancelled) {
          timer = window.setTimeout(() => {
            void load();
          }, intervalMs);
        }
      } finally {
        if (mountedRef.current) {
          setLoading(false);
        }
      }
    }

    if (!active) {
      setLoading(false);
      return;
    }

    void load(true);

    return () => {
      cancelled = true;
      if (timer) {
        window.clearTimeout(timer);
      }
    };
  }, [active, intervalMs]);

  return { data, error, loading, setData };
}
