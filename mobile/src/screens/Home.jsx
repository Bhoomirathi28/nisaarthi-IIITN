import { useT } from "../i18n";
import SunButton from "../components/SunButton";
import ScoreRing from "../components/ScoreRing";
import ConfidenceChip from "../components/ConfidenceChip";
import { IconGear } from "../components/Icons";
import { aged } from "../lib/labels";
import { clock, minutesSince } from "../lib/time";

export default function Home({ plan, online, sosHint, onSos, goPlan, goSettings }) {
  const { t } = useT();
  const best = plan?.routes?.[0];
  return (
    <div className="home">
      <header className="topbar">
        <div>
          <h1 className="brand">NISAARTHI</h1>
          <p className="tagline">{t("tagline")}</p>
        </div>
        <button className="icon-btn" onClick={goSettings} aria-label={t("settings")}><IconGear /></button>
      </header>

      {!online && <p className="banner">{t("offline_banner")}</p>}

      <section className="sos-wrap">
        <SunButton onPress={onSos} />
        <p className="sos-hint">{t(sosHint)}</p>
      </section>

      <section className="panel panel-framed">
        <h2>{t("going_home")}</h2>
        <p className="muted">{t("going_home_sub")}</p>
        <button className="btn btn-primary btn-block" onClick={goPlan}>{t("plan_route")}</button>
      </section>

      {best && (
        <button className="panel last-plan" onClick={goPlan}>
          <ScoreRing value={best.reliability} size={64} />
          <div>
            <p className="last-title">{t("last_plan")}</p>
            <p>{t("arrive", { time: clock(best.feasibility.arrival) })}</p>
            <p className="muted small">
              {t("updated", { ago: minutesSince(plan.generated_at) < 1 ? t("just_now") : t("min_ago", { n: minutesSince(plan.generated_at) }) })}
            </p>
          </div>
          <ConfidenceChip label={aged(best.confidence, plan.generated_at, plan.fresh_minutes)} small />
        </button>
      )}
    </div>
  );
}
