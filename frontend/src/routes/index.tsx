import { createFileRoute } from "@tanstack/react-router";

import { About } from "@/components/landing/About";
import { AIAnalystPreview } from "@/components/landing/AIAnalystPreview";
import { DashboardPreview } from "@/components/landing/DashboardPreview";
import { Features } from "@/components/landing/Features";
import { FinalCTA } from "@/components/landing/FinalCTA";
import { Hero } from "@/components/landing/Hero";
import { MapSection } from "@/components/landing/MapSection";
import { Methodology } from "@/components/landing/Methodology";
import { Overview } from "@/components/landing/Overview";
import { Technology } from "@/components/landing/Technology";
import { Footer } from "@/components/layout/Footer";
import { Navbar } from "@/components/layout/Navbar";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Observatório Inteligente da Educação Superior" },
      {
        name: "description",
        content:
          "Plataforma acadêmica para análise estatística e territorial da Educação Superior brasileira com dados do INEP.",
      },
      { property: "og:title", content: "Observatório Inteligente da Educação Superior" },
      {
        property: "og:description",
        content:
          "Dados, território e inteligência para compreender a Educação Superior brasileira.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

/** Landing ilustrativa: não consulta a API e funciona com ela fora do ar. */
function Index() {
  return (
    <>
      <Navbar />
      <main>
        <Hero />
        <Overview />
        <DashboardPreview />
        <MapSection />
        <AIAnalystPreview />
        <Features />
        <Methodology />
        <Technology />
        <About />
        <FinalCTA />
      </main>
      <Footer />
    </>
  );
}
