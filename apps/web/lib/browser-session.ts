"use client";

const GUEST_SESSION_KEY = "uxray_guest_session_id";
const DEMO_STATE_KEY = "uxray_demo_state_v1";

function canUseBrowserStorage() {
  return typeof window !== "undefined";
}

function createSessionId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }

  return `guest_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

export function readGuestSessionId() {
  if (!canUseBrowserStorage()) {
    return null;
  }

  return window.sessionStorage.getItem(GUEST_SESSION_KEY);
}

export function ensureGuestSession() {
  if (!canUseBrowserStorage()) {
    return null;
  }

  const existing = readGuestSessionId();
  if (existing) {
    return existing;
  }

  const nextId = createSessionId();
  window.sessionStorage.setItem(GUEST_SESSION_KEY, nextId);
  return nextId;
}

export function clearGuestSession() {
  if (!canUseBrowserStorage()) {
    return;
  }

  window.sessionStorage.removeItem(GUEST_SESSION_KEY);
}

export function readDemoState() {
  if (!canUseBrowserStorage()) {
    return null;
  }

  return window.sessionStorage.getItem(DEMO_STATE_KEY);
}

export function writeDemoState(value: string) {
  if (!canUseBrowserStorage()) {
    return;
  }

  window.sessionStorage.setItem(DEMO_STATE_KEY, value);
}

export function clearDemoState() {
  if (!canUseBrowserStorage()) {
    return;
  }

  window.sessionStorage.removeItem(DEMO_STATE_KEY);
}

export function isDemoRecordId(id: string) {
  return id.startsWith("demo_");
}
