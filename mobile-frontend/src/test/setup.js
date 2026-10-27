import * as matchers from "@testing-library/jest-dom/matchers";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, expect, vi } from "vitest";

// Extend Vitest's expect with jest-dom matchers
expect.extend(matchers);

// Cleanup after each test
afterEach(() => {
  cleanup();
});

// Mock window.matchMedia
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Mock localStorage with a working in-memory store wrapped in spies.
// jsdom exposes `localStorage` as a getter-only property, so it has to be
// replaced with Object.defineProperty rather than plain assignment.
const localStorageStore = new Map();
const localStorageImpl = {
  getItem: (key) =>
    localStorageStore.has(String(key))
      ? localStorageStore.get(String(key))
      : null,
  setItem: (key, value) => {
    localStorageStore.set(String(key), String(value));
  },
  removeItem: (key) => {
    localStorageStore.delete(String(key));
  },
  clear: () => {
    localStorageStore.clear();
  },
};
const localStorageMock = {
  getItem: vi.fn(localStorageImpl.getItem),
  setItem: vi.fn(localStorageImpl.setItem),
  removeItem: vi.fn(localStorageImpl.removeItem),
  clear: vi.fn(localStorageImpl.clear),
};
for (const target of new Set([globalThis, window])) {
  Object.defineProperty(target, "localStorage", {
    configurable: true,
    writable: true,
    value: localStorageMock,
  });
}

// Reset storage contents and any per-test mockReturnValue overrides so tests
// cannot leak state into each other.
beforeEach(() => {
  localStorageStore.clear();
  Object.entries(localStorageImpl).forEach(([name, impl]) => {
    localStorageMock[name].mockReset();
    localStorageMock[name].mockImplementation(impl);
  });
});

// Mock navigator.onLine
Object.defineProperty(navigator, "onLine", {
  writable: true,
  value: true,
});

// Mock IntersectionObserver (used by some UI primitives)
global.IntersectionObserver = class IntersectionObserver {
  disconnect() {}
  observe() {}
  takeRecords() {
    return [];
  }
  unobserve() {}
};

// Mock ResizeObserver (used by recharts and some Radix primitives)
global.ResizeObserver = class ResizeObserver {
  disconnect() {}
  observe() {}
  unobserve() {}
};

// jsdom cannot parse some modern (Tailwind v4) CSS injected via <style> tags.
// Filter only that specific noise; leave all other console errors intact.
const originalConsoleError = console.error;
console.error = (...args) => {
  const first = args[0];
  if (
    typeof first === "string" &&
    first.includes("Could not parse CSS stylesheet")
  ) {
    return;
  }
  if (first instanceof Error && first.message.includes("Could not parse CSS")) {
    return;
  }
  originalConsoleError(...args);
};
