/**
 * Textos estáticos da landing. Nada aqui é dado do Censo: são rótulos e descrições.
 * Regra do projeto: o Censo disponível é um retrato transversal de 2024 — nenhum texto pode
 * prometer evolução, tendência ou série temporal.
 */
import {
  BrainCircuit,
  Building2,
  CalendarDays,
  Database,
  FlaskConical,
  GraduationCap,
  Map,
  MapPin,
  MapPinned,
  Pentagon,
  ScanSearch,
  Sparkles,
  SlidersHorizontal,
  UsersRound,
  Waypoints,
  type LucideIcon,
} from "lucide-react";

type IconText = { icon: LucideIcon; title: string; text: string };

export const navItems = [
  ["Início", "#inicio"],
  ["Plataforma", "#plataforma"],
  ["Recursos", "#recursos"],
  ["Metodologia", "#metodologia"],
  ["Sobre", "#sobre"],
] as const;

export const heroHighlights = ["Dados do INEP", "Análise municipal", "Visualizações interativas"];

export const overviewCards: IconText[] = [
  {
    icon: Building2,
    title: "Instituições",
    text: "Explore a distribuição e as características das Instituições de Ensino Superior.",
  },
  {
    icon: GraduationCap,
    title: "Cursos",
    text: "Analise a oferta acadêmica por modalidade, área e localização.",
  },
  {
    icon: UsersRound,
    title: "Matrículas",
    text: "Examine matrículas, ingressantes e concluintes no retrato do Censo 2024.",
  },
  {
    icon: Map,
    title: "Território",
    text: "Observe padrões espaciais e diferenças entre municípios e regiões.",
  },
];

export const dashboardTabs = [
  "Visão Geral",
  "Instituições",
  "Cursos",
  "Matrículas e Fluxo",
  "Distribuição Territorial",
  "Comparações",
  "Analista IA",
];

export const dashboardFilters: Array<[name: string, value: string]> = [
  ["Região", "Todas"],
  ["UF", "Todas"],
  ["Município", "Todos"],
];

export const dashboardKpis = ["IES", "Cursos", "Matrículas", "Municípios analisados"];

export const mapModes: IconText[] = [
  {
    icon: ScanSearch,
    title: "Concentração",
    text: "Identifique padrões e áreas de maior densidade.",
  },
  {
    icon: MapPin,
    title: "Instituições",
    text: "Navegue por pontos e agrupamentos territoriais.",
  },
  {
    icon: Pentagon,
    title: "Municípios",
    text: "Compare recortes e limites administrativos.",
  },
];

export const mapHighlights = ["Zoom interativo", "Análise municipal", "Filtros territoriais"];

export const aiSuggestions = [
  "Compare duas cidades",
  "Analise a distribuição das matrículas por UF",
  "Encontre regiões com maior concentração de IES",
];

export const resources: IconText[] = [
  {
    icon: Waypoints,
    title: "Análise municipal",
    text: "Explore indicadores no nível dos municípios brasileiros.",
  },
  {
    icon: Map,
    title: "Mapas interativos",
    text: "Visualize padrões territoriais por concentração, pontos e áreas.",
  },
  {
    icon: CalendarDays,
    title: "Retrato do Censo 2024",
    text: "Indicadores de um único ano de referência, apresentados sem série temporal.",
  },
  { icon: UsersRound, title: "Comparações", text: "Compare municípios, estados e instituições." },
  {
    icon: SlidersHorizontal,
    title: "Filtros avançados",
    text: "Explore diferentes recortes acadêmicos e administrativos.",
  },
  {
    icon: Sparkles,
    title: "Analista IA",
    text: "Converse com os dados utilizando linguagem natural.",
  },
];

export const methodology = [
  "Censo da Educação Superior",
  "Integração e tratamento",
  "Indicadores",
  "Análise territorial",
  "Visualização",
  "Inteligência Artificial",
];

export const technology: Array<{ icon: LucideIcon; label: string; text: string }> = [
  { icon: Database, label: "Dados", text: "Censo da Educação Superior — INEP" },
  { icon: FlaskConical, label: "Análise", text: "Estatística e Ciência de Dados" },
  { icon: MapPinned, label: "Geoespacial", text: "Análise territorial em nível municipal" },
  { icon: BrainCircuit, label: "IA", text: "Modelos de linguagem integrados à camada analítica" },
];

export const aboutFields = ["Autor", "Orientador", "Instituição", "Curso e ano"];
