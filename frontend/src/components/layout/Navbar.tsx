import { useEffect, useRef, useState } from "react";
import { Link } from "@tanstack/react-router";
import { Menu, X, ArrowUpRight } from "lucide-react";

import { navItems } from "@/data/landing";

import { Brand } from "./Brand";
import { Container } from "./Container";

const MOBILE_MENU_ID = "menu-movel";

/** Barra de navegação da landing (âncoras da própria página + CTA para o painel). */
export function Navbar() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const toggleRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      toggleRef.current?.focus();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open]);

  return (
    <header
      className={`fixed inset-x-0 top-0 z-50 transition-all ${scrolled ? "border-b border-border/70 bg-background/95 shadow-hairline backdrop-blur-md" : "bg-background/75 backdrop-blur-sm"}`}
    >
      <Container className="flex h-20 items-center justify-between">
        <Brand href="#inicio" />
        <nav className="hidden items-center gap-7 lg:flex" aria-label="Navegação principal">
          {navItems.map(([label, href]) => (
            <a
              key={href}
              href={href}
              className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              {label}
            </a>
          ))}
        </nav>
        <Link
          to="/painel"
          className="hidden items-center gap-2 rounded-md bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground transition-transform hover:-translate-y-0.5 lg:inline-flex"
        >
          Explorar plataforma <ArrowUpRight className="size-4" aria-hidden="true" />
        </Link>
        <button
          ref={toggleRef}
          type="button"
          className="grid size-10 place-items-center rounded-md border border-border bg-background text-foreground lg:hidden"
          onClick={() => setOpen(!open)}
          aria-label={open ? "Fechar menu" : "Abrir menu"}
          aria-expanded={open}
          aria-controls={MOBILE_MENU_ID}
        >
          {open ? (
            <X className="size-5" aria-hidden="true" />
          ) : (
            <Menu className="size-5" aria-hidden="true" />
          )}
        </button>
      </Container>
      <nav
        id={MOBILE_MENU_ID}
        hidden={!open}
        className="border-t border-border bg-background px-5 pb-5 lg:hidden"
        aria-label="Navegação móvel"
      >
        <div className="mx-auto flex max-w-7xl flex-col py-3">
          {navItems.map(([label, href]) => (
            <a
              key={href}
              href={href}
              onClick={() => setOpen(false)}
              className="border-b border-border/60 py-3 text-sm font-medium text-foreground"
            >
              {label}
            </a>
          ))}
          <Link
            to="/painel"
            onClick={() => setOpen(false)}
            className="mt-4 inline-flex items-center justify-center gap-2 rounded-md bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground"
          >
            Explorar plataforma <ArrowUpRight className="size-4" aria-hidden="true" />
          </Link>
        </div>
      </nav>
    </header>
  );
}
