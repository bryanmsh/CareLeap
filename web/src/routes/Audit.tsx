import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  ApiError,
  getAudit,
  getClinics,
  postWhatIf,
} from "../api/client";
import type { AuditResponse, Clinic, Day } from "../api/types";
import { DAYS, blockKey, deltaPts, hourLabel, pct } from "../lib/scale";
import { WeekGrid } from "../components/WeekGrid";
import { DayRibbon } from "../components/DayRibbon";
import { SuggestPanel } from "../components/SuggestPanel";
import { EquityPanel } from "../components/EquityPanel";
import { BlockGroupMap } from "../components/BlockGroupMap";
import { SourcesFooter } from "../components/SourcesFooter";
import { ScaleLegend } from "../components/ScaleLegend";
import { ProvenanceChip } from "../components/ProvenanceChip";

type Load =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; data: AuditResponse };

// Communities the audit can scope to: the whole service area or one county.
// These are exactly what engine.audit.filter_community accepts. (Equity groups
// such as EJ or limited-English are not filters; the Equity panel shows them.)
const COMMUNITIES = ["all", "hampden", "hampshire", "franklin"] as const;

export function Audit() {
  const { t } = useTranslation();

  const [clinics, setClinics] = useState<Clinic[] | null>(null);
  const [clinic, setClinic] = useState<string>("");
  const [community, setCommunity] = useState<string>("all");
  const [day, setDay] = useState<Day>("mon");

  const [load, setLoad] = useState<Load>({ kind: "loading" });
  const [busy, setBusy] = useState(false);
  const [focusDay, setFocusDay] = useState<Day>("mon");
  const [announce, setAnnounce] = useState("");
  // before/after share for the moved block, shown after a what-if
  const [lastMove, setLastMove] = useState<{
    block: string;
    before: number;
    after: number;
  } | null>(null);

  const shareOfBlock = useCallback(
    (data: AuditResponse | undefined, block: string): number | null => {
      if (!data) return null;
      const cell = data.cells.find((c) => blockKey(c.day, c.hour) === block);
      return cell ? cell.share : null;
    },
    [],
  );

  // Load clinics once.
  useEffect(() => {
    const ac = new AbortController();
    getClinics(ac.signal)
      .then((r) => {
        setClinics(r.clinics);
        if (r.clinics.length > 0) setClinic(r.clinics[0].clinic_id);
      })
      .catch(() => setClinics([]));
    return () => ac.abort();
  }, []);

  // Load the audit whenever clinic/community/day change.
  useEffect(() => {
    if (!clinic) return;
    const ac = new AbortController();
    setLoad({ kind: "loading" });
    setLastMove(null);
    getAudit({ clinic, community, day }, ac.signal)
      .then((data) => setLoad({ kind: "ready", data }))
      .catch((err: unknown) => {
        if (ac.signal.aborted) return;
        const message =
          err instanceof ApiError ? err.message : t("audit.error");
        setLoad({ kind: "error", message });
      });
    return () => ac.abort();
  }, [clinic, community, day, t]);

  const data = load.kind === "ready" ? load.data : undefined;

  const onMove = useCallback(
    (block: string, toHour: number) => {
      if (!clinic || busy) return;
      const before = shareOfBlock(data, block) ?? 0;
      setBusy(true);
      setAnnounce(t("audit.whatif.moving"));
      const ac = new AbortController();
      postWhatIf({ clinic, community, shift: { block, to: toHour } }, ac.signal)
        .then((next) => {
          setLoad({ kind: "ready", data: next });
          const movedTo = blockKey(block.slice(0, 3) as Day, toHour);
          const after = shareOfBlock(next, movedTo) ?? 0;
          setLastMove({ block: movedTo, before, after });
          const dayName = t(`audit.days.${block.slice(0, 3) as Day}`);
          setAnnounce(
            t("audit.whatif.dropped", { day: dayName, hour: hourLabel(toHour) }),
          );
        })
        .catch((err: unknown) => {
          const message =
            err instanceof ApiError ? err.message : t("audit.error");
          setLoad({ kind: "error", message });
        })
        .finally(() => setBusy(false));
    },
    [clinic, busy, data, shareOfBlock, t],
  );

  const liveRef = useRef<HTMLParagraphElement | null>(null);

  const clinicOptions = useMemo(
    () =>
      (clinics ?? []).map((c) => (
        <option key={c.clinic_id} value={c.clinic_id}>
          {c.clinic_name} · {c.visit_type}
        </option>
      )),
    [clinics],
  );

  return (
    <>
      <div className="page-heading">
        <p className="eyebrow">{t("design.auditEyebrow")}</p>
        <h1>{t("audit.title")}</h1>
        <p className="page-intro">{t("audit.intro")}</p>
      </div>

      <div className="controls">
        <div className="field">
          <label htmlFor="clinic-select">{t("audit.clinic")}</label>
          <select
            id="clinic-select"
            value={clinic}
            onChange={(e) => setClinic(e.target.value)}
          >
            {clinics == null ? (
              <option>{t("audit.loading")}</option>
            ) : (
              clinicOptions
            )}
          </select>
        </div>

        <div className="field">
          <label htmlFor="community-select">{t("audit.community")}</label>
          <select
            id="community-select"
            value={community}
            onChange={(e) => setCommunity(e.target.value)}
          >
            {COMMUNITIES.map((c) => (
              <option key={c} value={c}>
                {t(`audit.communities.${c}`)}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label htmlFor="day-select">{t("audit.day")}</label>
          <select
            id="day-select"
            value={day}
            onChange={(e) => setDay(e.target.value as Day)}
          >
            {DAYS.map((d) => (
              <option key={d} value={d}>
                {t(`audit.days.${d}`)}
              </option>
            ))}
          </select>
        </div>
      </div>



      {/* aria-live region for what-if updates (accessibility.md) */}
      <p
        ref={liveRef}
        className="visually-hidden"
        aria-live="polite"
        role="status"
      >
        {announce}
      </p>

      {load.kind === "error" && (
        <div className="status error" role="alert">
          {load.message}{" "}
          <button type="button" onClick={() => setDay((d) => d)}>
            {t("audit.retry")}
          </button>
        </div>
      )}

      {load.kind === "loading" && (
        <div className="status" role="status">
          {t("audit.loading")}
        </div>
      )}

      {load.kind === "ready" && load.data.cells.length === 0 && (
        <div className="status" role="status">
          {t("audit.empty")}
        </div>
      )}

      {data && data.cells.length > 0 && (
        <>
          <AuditSummary data={data} />

          <section className="schedule-surface" aria-labelledby="schedule-title">
          <div className="section-heading">
            <div><h2 id="schedule-title">{t("design.scheduleTitle")}</h2>
            <p className="text-muted">{t("design.scheduleHint")}</p></div>
            <details className="grid-help"><summary>{t("design.gridHelp")}</summary>
              <p id="grid-help">{t("audit.pickUpHint")}</p>
            </details>
          </div>
          <ScaleLegend />

          {lastMove && (
            <div className="beforeafter" role="status">
              <strong>{t("audit.whatif.movedTitle")}:</strong>
              <span>
                {t("audit.whatif.before")} {pct(lastMove.before)}
              </span>
              <span aria-hidden="true">→</span>
              <span>
                {t("audit.whatif.after")} {pct(lastMove.after)}
              </span>
              <span
                className={`delta ${
                  lastMove.after >= lastMove.before ? "up" : "down"
                }`}
              >
                {t("audit.whatif.change")}{" "}
                {deltaPts(lastMove.before, lastMove.after)} pts
              </span>
            </div>
          )}

          <p className="grid-scroll-hint">{t("design.scrollHint")}</p>
          <div className="grid-scroll" role="region" aria-label={t("audit.gridCaption")} tabIndex={0}>
          <WeekGrid
            cells={data.cells}
            busy={busy}
            pickedBlock={null}
            onCellFocus={(d) => setFocusDay(d)}
            onMove={onMove}
          />

          </div>
          </section>
          <div className="section-heading details-heading"><div>
            <h2>{t("design.detailsTitle")}</h2>
            <p className="text-muted">{t("design.detailsHint")}</p>
          </div></div>
          <div className="panels">
            <DayRibbon day={focusDay} cells={data.cells} />
            <SuggestPanel clinic={clinic} day={day} community={community} cells={data.cells} />
            <EquityPanel equity={data.equity} />
            <BlockGroupMap />
          </div>

          <SourcesFooter sources={data.sources} />
        </>
      )}
    </>
  );
}

/**
 * Three headline numbers above the grid: the best hour, the hardest hour and how
 * many car-less adults the share is out of. All three are read straight from the
 * /audit cells (never computed from anything else), and each carries the audit's
 * first source as its ProvenanceChip (ui-style.md provenance rule).
 */
function AuditSummary({ data }: { data: AuditResponse }) {
  const { t } = useTranslation();
  const cells = data.cells;
  const best = cells.reduce((a, c) => (c.share > a.share ? c : a), cells[0]);
  const worst = cells.reduce((a, c) => (c.share < a.share ? c : a), cells[0]);
  const people = Math.max(...cells.map((c) => c.n));
  const src = data.sources[0];
  const when = (c: AuditResponse["cells"][number]) =>
    `${t(`audit.days.${c.day}`)} ${hourLabel(c.hour)}`;
  return (
    <section className="summary" aria-label={t("audit.summary.title")}>
      <div className="summary-card summary-best">
        <span className="summary-label">{t("audit.summary.best")}</span>
        <span className="summary-value">{pct(best.share)}</span>
        <span className="summary-hint">
          {when(best)} · {t("audit.summary.hint")}
        </span>
        {src && <ProvenanceChip source={src} />}
      </div>
      <div className="summary-card summary-worst">
        <span className="summary-label">{t("audit.summary.worst")}</span>
        <span className="summary-value">{pct(worst.share)}</span>
        <span className="summary-hint">
          {when(worst)} · {t("audit.summary.hint")}
        </span>
        {src && <ProvenanceChip source={src} />}
      </div>
      <div className="summary-card">
        <span className="summary-label">{t("audit.summary.people")}</span>
        <span className="summary-value">{people.toLocaleString()}</span>
        {src && <ProvenanceChip source={src} />}
      </div>
    </section>
  );
}
