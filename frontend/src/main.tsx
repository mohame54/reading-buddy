import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { checkHealth } from "./api/client";
import App from "./App";
import "./i18n";
import "./index.css";

// Wake cold backend (e.g. Cloud Run) without blocking the SPA
void checkHealth();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
