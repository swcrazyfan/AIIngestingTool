import React from "react";
import ReactDOM from "react-dom/client";
import { initBolt, enableSpectrum } from "../lib/utils/bolt";

import Main from "./main";

// Enable Spectrum for proper UI interaction on macOS
enableSpectrum();

// Initialize Bolt CEP utilities
initBolt();

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <Main />
  </React.StrictMode>
);
