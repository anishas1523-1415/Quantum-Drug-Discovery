import "@testing-library/jest-dom/vitest";

// Node 25+ defines a broken global `localStorage` ({} with no methods,
// gated behind --localstorage-file) that shadows jsdom's own storage
// and jsdom itself declines to redefine an already-present property.
// Replace it with a minimal, functional in-memory Storage polyfill.
function createMemoryStorage() {
  let store = new Map();

  return {
    getItem: (key) => (store.has(key) ? store.get(key) : null),
    setItem: (key, value) => store.set(key, String(value)),
    removeItem: (key) => store.delete(key),
    clear: () => store.clear(),
    key: (index) => Array.from(store.keys())[index] ?? null,
    get length() {
      return store.size;
    },
  };
}

const memoryStorage = createMemoryStorage();

for (const target of [globalThis, window]) {
  Object.defineProperty(target, "localStorage", {
    value: memoryStorage,
    configurable: true,
    writable: true,
  });
}
