import "@copilotkit/react-core/v2/styles.css";
import "./app.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App.tsx";
import { ErrorBoundary } from "./ErrorBoundary.tsx";
import { initTheme } from "./theme.ts";

// Apply the saved/system theme before the first paint so there is no light flash.
initTheme();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary label="kicad-harness">
      <App />
    </ErrorBoundary>
  </StrictMode>,
);
