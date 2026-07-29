import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { FinalScoreResponse } from "../../types/api";
import { AppShell, PageLayout } from "../../components/Layout";

interface ScoreState {
  score: FinalScoreResponse;
  title?: string;
}

export function ScorePage() {
  const { t } = useTranslation();
  const location = useLocation();
  const state = location.state as ScoreState | null;

  if (!state?.score) {
    return (
      <>
        <AppShell />
        <PageLayout title={t("score.title")}>
          <p>{t("score.noScore")}</p>
          <Link to="/users" className="btn btn-primary">
            {t("score.goToLibrary")}
          </Link>
        </PageLayout>
      </>
    );
  }

  const { score, title } = state;
  const accuracyPct = Math.round(score.accuracy * 100);

  return (
    <>
      <AppShell />
      <PageLayout title={title ? t("score.results", { title }) : t("score.yourScore")}>
        <div className="score-card">
          <div className="score-big">{accuracyPct}%</div>
          <p className="score-label">{t("score.accuracy")}</p>

          <dl className="score-stats">
            <div>
              <dt>{t("score.wordsCorrect")}</dt>
              <dd>
                {score.words_correct} / {score.words_total}
              </dd>
            </div>
            <div>
              <dt>{t("score.pagesCompleted")}</dt>
              <dd>
                {score.pages_completed} / {score.pages_total}
              </dd>
            </div>
          </dl>
        </div>

        <Link to="/users" className="btn btn-primary">
          {t("common.backToLibrary")}
        </Link>
      </PageLayout>
    </>
  );
}
