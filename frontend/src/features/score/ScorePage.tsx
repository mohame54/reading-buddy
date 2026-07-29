import { Link, useLocation } from "react-router-dom";
import type { FinalScoreResponse } from "../../types/api";
import { AppShell, PageLayout } from "../../components/Layout";

interface ScoreState {
  score: FinalScoreResponse;
  title?: string;
}

export function ScorePage() {
  const location = useLocation();
  const state = location.state as ScoreState | null;

  if (!state?.score) {
    return (
      <>
        <AppShell />
        <PageLayout title="Score">
          <p>No score data. Start reading from the library.</p>
          <Link to="/users" className="btn btn-primary">
            Go to library
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
      <PageLayout title={title ? `${title} — Results` : "Your score"}>
        <div className="score-card">
          <div className="score-big">{accuracyPct}%</div>
          <p className="score-label">Accuracy</p>

          <dl className="score-stats">
            <div>
              <dt>Words correct</dt>
              <dd>
                {score.words_correct} / {score.words_total}
              </dd>
            </div>
            <div>
              <dt>Pages completed</dt>
              <dd>
                {score.pages_completed} / {score.pages_total}
              </dd>
            </div>
          </dl>
        </div>

        <Link to="/users" className="btn btn-primary">
          Back to library
        </Link>
      </PageLayout>
    </>
  );
}
