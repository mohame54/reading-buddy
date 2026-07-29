import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import ar from "./locales/ar.json";
import en from "./locales/en.json";

export const LANG_STORAGE_KEY = "rb-lang";

export type AppLanguage = "ar" | "en";

function applyDocumentLanguage(lang: AppLanguage) {
  const root = document.documentElement;
  root.lang = lang;
  root.dir = lang === "ar" ? "rtl" : "ltr";
  document.title = lang === "ar" ? "رفيق القراءة" : "Reading Buddy";
}

function detectLanguage(): AppLanguage {
  const stored = localStorage.getItem(LANG_STORAGE_KEY);
  if (stored === "ar" || stored === "en") return stored;
  return "ar";
}

const initialLang = detectLanguage();
applyDocumentLanguage(initialLang);

void i18n.use(initReactI18next).init({
  resources: {
    ar: { translation: ar },
    en: { translation: en },
  },
  lng: initialLang,
  fallbackLng: "ar",
  interpolation: { escapeValue: false },
});

i18n.on("languageChanged", (lng) => {
  const lang = lng === "en" ? "en" : "ar";
  localStorage.setItem(LANG_STORAGE_KEY, lang);
  applyDocumentLanguage(lang);
});

export function setAppLanguage(lang: AppLanguage) {
  return i18n.changeLanguage(lang);
}

export default i18n;
