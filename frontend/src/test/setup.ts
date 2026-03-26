import { vi } from "vitest";

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};

  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value.toString();
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
  };
})();

Object.defineProperty(window, "localStorage", {
  value: localStorageMock,
});

// Mock window.location
delete (window as any).location;
window.location = { href: "" } as any;

// Mock import.meta.env
Object.defineProperty(import.meta, "env", {
  value: {
    VITE_API_URL: "http://localhost:3000/api/v1",
  },
});
