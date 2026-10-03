"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { COPY, Lang, SHELL } from "@/lib/landingCopy";

type AsStrings<T> = { [K in keyof T]: string };
type Messages = AsStrings<(typeof COPY)["en"]> & AsStrings<(typeof SHELL)["en"]>;

type LandingLangValue = {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: Messages;
};

const LandingLangContext = createContext<LandingLangValue | null>(null);

export function LandingLangProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>("en");

  useEffect(() => {
    try {
      const saved = localStorage.getItem("ct-lang");
      if (saved === "sw" || saved === "en") {
        setLangState(saved);
        return;
      }
      if (/^sw/i.test(navigator.language || "")) setLangState("sw");
    } catch {
      /* keep English when storage is blocked */
    }
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const value = useMemo<LandingLangValue>(
    () => ({
      lang,
      setLang: (next) => {
        setLangState(next);
        try {
          localStorage.setItem("ct-lang", next);
        } catch {
          /* the choice still applies for this visit */
        }
      },
      t: { ...COPY[lang], ...SHELL[lang] },
    }),
    [lang],
  );

  return <LandingLangContext.Provider value={value}>{children}</LandingLangContext.Provider>;
}

export function useLandingLang(): LandingLangValue {
  const value = useContext(LandingLangContext);
  if (!value) throw new Error("Landing language is missing");
  return value;
}

export function LangSwitch() {
  const { lang, setLang } = useLandingLang();
  return (
    <div className="lang-switch" role="group" aria-label="Language">
      <button type="button" aria-pressed={lang === "sw"} onClick={() => setLang("sw")}>
        Kiswahili
      </button>
      <button type="button" aria-pressed={lang === "en"} onClick={() => setLang("en")}>
        English
      </button>
    </div>
  );
}

export function MenuButton({ open, label, onToggle }: { open: boolean; label: string; onToggle: () => void }) {
  return (
    <button type="button" className={`menu-btn ${open ? "open" : ""}`} aria-expanded={open} aria-label={label} onClick={onToggle}>
      <span />
      <span />
      <span />
    </button>
  );
}
