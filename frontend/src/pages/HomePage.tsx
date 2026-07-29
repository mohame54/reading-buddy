import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { checkHealth } from "../api/client";
import { AppShell } from "../components/Layout";

export function HomePage() {
  const { t } = useTranslation();
  const [healthy, setHealthy] = useState<boolean | null>(null);

  useEffect(() => {
    checkHealth().then(setHealthy);
  }, []);

  return (
    <>
      <AppShell />
      <main className="home">
        <h1>{t("brand")}</h1>
        <p>{t("home.tagline")}</p>
        {healthy === false && (
          <p className="error-banner">{t("home.apiUnreachable")}</p>
        )}
        <div className="home-links">
          <Link to="/admin" className="home-card">
            <h2>{t("home.adminTitle")}</h2>
            <p>{t("home.adminDesc")}</p>
          </Link>
          <Link to="/users" className="home-card">
            <h2>{t("home.usersTitle")}</h2>
            <p>{t("home.usersDesc")}</p>
          </Link>
        </div>
      </main>
    </>
  );
}
