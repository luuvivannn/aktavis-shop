import { AnimatePresence, motion } from "motion/react";
import { useEffect, useLayoutEffect, type ReactNode } from "react";

import { TabBar } from "@/components/TabBar";
import { About } from "@/pages/About";
import { Catalog } from "@/pages/Catalog";
import { CustomOrder } from "@/pages/CustomOrder";
import { Favorites } from "@/pages/Favorites";
import { ProductPage } from "@/pages/Product";
import { goBack, routeKey, useRoute, type Route } from "@/lib/router";
import { setBackButton } from "@/lib/telegram";

// Scroll position per screen, so coming back from a product lands on the
// same spot in the catalog.
const scrollPositions = new Map<string, number>();
let currentKey = "";

window.addEventListener(
  "scroll",
  () => {
    if (currentKey) scrollPositions.set(currentKey, window.scrollY);
  },
  { passive: true },
);

function Screen({ id, children }: { id: string; children: ReactNode }) {
  useLayoutEffect(() => {
    currentKey = id;
    window.scrollTo(0, scrollPositions.get(id) ?? 0);
  }, [id]);
  return (
    <motion.main
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.22, ease: [0.32, 0.72, 0, 1] }}
      className="min-h-dvh pb-32"
    >
      {children}
    </motion.main>
  );
}

function page(route: Route) {
  switch (route.name) {
    case "product":
      return <ProductPage id={route.id} />;
    case "favorites":
      return <Favorites />;
    case "custom-order":
      return <CustomOrder />;
    case "about":
      return <About />;
    default:
      return <Catalog />;
  }
}

/** The tab a screen belongs to: a product is part of the catalog. */
function owningTab(route: Route): Route["name"] {
  return route.name === "product" ? "catalog" : route.name;
}

export function App() {
  const route = useRoute();
  const key = routeKey(route);
  const isProduct = route.name === "product";

  useEffect(() => {
    setBackButton(isProduct ? goBack : null);
  }, [isProduct]);

  return (
    <>
      <div className="backdrop" aria-hidden />
      <AnimatePresence
        mode="wait"
        initial={false}
        onExitComplete={() => {
          // Stop saving the old screen's scroll while the new one mounts.
          currentKey = "";
        }}
      >
        <Screen key={key} id={key}>
          {page(route)}
        </Screen>
      </AnimatePresence>
      <TabBar active={owningTab(route)} />
    </>
  );
}
