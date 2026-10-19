/** Light/dark theme for the app chrome. One root attribute drives every colour in app.css.
 *
 *  The KiCad board canvas is always dark (KiCad Default), so dark mode simply extends that
 *  palette to the rest of the UI. CopilotKit's own stylesheet keys off a `.dark` ancestor,
 *  so we put the class on <html> as well as the `data-theme` attribute.
 */

export type Theme = "light" | "dark";

const KEY = "kicad-harness-theme";
const listeners = new Set<(t: Theme) => void>();

function systemTheme(): Theme {
  try {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  } catch {
    return "light";
  }
}

export function getTheme(): Theme {
  try {
    const stored = localStorage.getItem(KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    // private mode / storage disabled
  }
  return systemTheme();
}

export function applyTheme(theme: Theme, persist = true) {
  document.documentElement.dataset.theme = theme;
  document.documentElement.classList.toggle("dark", theme === "dark");
  document.documentElement.style.colorScheme = theme;
  if (persist) {
    try {
      localStorage.setItem(KEY, theme);
    } catch {
      // ignore
    }
  }
  for (const fn of listeners) fn(theme);
}

export function initTheme(): Theme {
  const theme = getTheme();
  applyTheme(theme, false);
  return theme;
}

export function toggleTheme(): Theme {
  const next: Theme = getTheme() === "dark" ? "light" : "dark";
  applyTheme(next);
  return next;
}

export function subscribeTheme(fn: (t: Theme) => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
