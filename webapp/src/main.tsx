import "./index.css";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { api } from "./lib/api";
import { routeFromStartParam } from "./lib/router";
import { initTelegram, setupPromoAudience, startParam } from "./lib/telegram";

initTelegram();

// A Direct Link (t.me/<bot>/shop?startapp=p_42, e.g. from a channel post)
// opens straight on its screen, with no flash of the catalog.
const start = routeFromStartParam(startParam());
if (start && (!location.hash || location.hash === "#/" || location.hash === "#/catalog")) {
  history.replaceState(null, "", `#${start}`);
}

setupPromoAudience(api.subscribe);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 60_000, refetchOnWindowFocus: false, retry: 1 },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
);
