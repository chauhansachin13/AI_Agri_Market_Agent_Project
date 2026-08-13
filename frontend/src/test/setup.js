import '@testing-library/jest-dom/vitest';

// Recharts sizes itself from ResizeObserver, which jsdom does not implement.
// A no-op stub is not enough — the observer must actually report a non-zero
// box, or ResponsiveContainer refuses to draw and logs a warning.
globalThis.ResizeObserver = class {
  constructor(callback) {
    this.callback = callback;
  }

  observe(target) {
    const contentRect = { width: 1024, height: 768, top: 0, left: 0, bottom: 768, right: 1024 };
    this.callback([{ target, contentRect, contentBoxSize: [{ inlineSize: 1024, blockSize: 768 }] }], this);
  }

  unobserve() {}
  disconnect() {}
};

// jsdom performs no layout, so every element reports a zero-sized box and
// ResponsiveContainer refuses to draw. Reporting a fixed viewport lets the
// chart render its SVG in tests instead of bailing out with a warning.
for (const [property, value] of [
  ['offsetWidth', 1024],
  ['offsetHeight', 768],
  ['clientWidth', 1024],
  ['clientHeight', 768],
]) {
  Object.defineProperty(globalThis.HTMLElement.prototype, property, {
    configurable: true,
    value,
  });
}

if (typeof globalThis.matchMedia === 'undefined') {
  globalThis.matchMedia = () => ({
    matches: false,
    addEventListener() {},
    removeEventListener() {},
    addListener() {},
    removeListener() {},
  });
}
