import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { PlayersProvider } from "./context/PlayersContext";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <PlayersProvider>
        <App />
      </PlayersProvider>
    </BrowserRouter>
  </StrictMode>
);
