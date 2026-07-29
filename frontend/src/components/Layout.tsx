import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { setAppLanguage, type AppLanguage } from "../i18n";

export function AppShell() {
  const { t, i18n } = useTranslation();
  const current = (i18n.language === "en" ? "en" : "ar") as AppLanguage;

  return (
    <header className="app-header">
      <Link to="/" className="brand">
        {t("brand")}
      </Link>
      <div className="header-actions">
        <div className="lang-toggle" role="group" aria-label="Language">
          <button
            type="button"
            className={current === "ar" ? "lang-btn active" : "lang-btn"}
            onClick={() => void setAppLanguage("ar")}
          >
            {t("nav.langAr")}
          </button>
          <button
            type="button"
            className={current === "en" ? "lang-btn active" : "lang-btn"}
            onClick={() => void setAppLanguage("en")}
          >
            {t("nav.langEn")}
          </button>
        </div>
        <nav className="mode-nav">
          <Link to="/admin">{t("nav.admin")}</Link>
          <Link to="/users">{t("nav.users")}</Link>
        </nav>
      </div>
    </header>
  );
}

export function PageLayout({
  title,
  children,
  actions,
}: {
  title: string;
  children: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <div className="page">
      <div className="page-header">
        <h1>{title}</h1>
        {actions && <div className="page-actions">{actions}</div>}
      </div>
      {children}
    </div>
  );
}

export function ErrorBanner({ message }: { message: string }) {
  return <div className="error-banner">{message}</div>;
}

export function LoadingState({ label }: { label?: string }) {
  const { t } = useTranslation();
  return <div className="loading">{label ?? t("common.loading")}</div>;
}

export function Pagination({
  offset,
  limit,
  total,
  onPageChange,
}: {
  offset: number;
  limit: number;
  total: number;
  onPageChange: (newOffset: number) => void;
}) {
  const { t } = useTranslation();
  const currentPage = Math.floor(offset / limit) + 1;
  const pageCount = Math.max(1, Math.ceil(total / limit));

  return (
    <div className="pagination">
      <button
        type="button"
        disabled={offset === 0}
        onClick={() => onPageChange(Math.max(0, offset - limit))}
      >
        {t("common.previous")}
      </button>
      <span>
        {t("common.pageOf", { current: currentPage, total: pageCount, count: total })}
      </span>
      <button
        type="button"
        disabled={offset + limit >= total}
        onClick={() => onPageChange(offset + limit)}
      >
        {t("common.next")}
      </button>
    </div>
  );
}
