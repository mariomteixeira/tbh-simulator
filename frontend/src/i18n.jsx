import React, { createContext, useContext, useState, useCallback } from "react";

/* i18n simples e inline: cada string carrega os dois idiomas no ponto de uso —
   t("English", "Português"). Padrão = inglês. Sem dicionário central (zero
   conflito entre componentes). A escolha persiste em localStorage. */
const LangCtx = createContext({ lang: "en", setLang: () => {} });

/* espelho do idioma fora do React, p/ funções puras (ex.: statPt no gemFormat)
   traduzirem sem virar hook. tr(en, pt) lê isto. */
export const L = { lang: "en" };
export const tr = (en, pt) => (L.lang === "pt" && pt != null ? pt : en);

/* rótulos gerados pelo backend em pt (rating/veredito) — traduz no front */
export const ratingLabel = (r) => ({
  seguro: tr("safe", "seguro"), apertado: tr("tight", "apertado"),
  arriscado: tr("risky", "arriscado"), passa: tr("pass", "passa"),
}[r] || r);

export function LangProvider({ children }) {
  const [lang, setLangState] = useState(() => {
    try { return localStorage.getItem("tbh_lang") || "en"; } catch { return "en"; }
  });
  L.lang = lang;   // sincroniza o espelho a cada render (antes dos filhos)
  const setLang = useCallback((l) => {
    setLangState(l);
    try { localStorage.setItem("tbh_lang", l); } catch { /* ignore */ }
  }, []);
  return <LangCtx.Provider value={{ lang, setLang }}>{children}</LangCtx.Provider>;
}

export function useLang() { return useContext(LangCtx); }

/* hook que devolve a função de tradução ligada ao idioma atual.
   uso: const t = useT();  ...  {t("Search", "Buscar")} */
export function useT() {
  const { lang } = useContext(LangCtx);
  return useCallback((en, pt) => (lang === "pt" && pt != null ? pt : en), [lang]);
}
