import { useCallback, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError, getSuggest, postWhatIf } from "../api/client";
import type {
  AuditResponse,
  Day,
  SuggestResponse,
  Suggestion,
  SuggestSource,
} from "../api/types";
import { HOURS, blockKey, deltaPts, hourLabel, pct } from "../lib/scale";
import { ProvenanceChip } from "./ProvenanceChip";

/**
 * SuggestPanel — "Suggest a better schedule" for the Audit screen.
 *
 * The clinic ticks the hours it currently opens on the selected day (we default
 * the first three), then asks the optimizer (GET /suggest) for up to k=3 moves.
 * Each suggestion shows the gain in people and visit-hours, a ProvenanceChip per
 * source (flagged "illustrative" when any source is), and a Preview button that
 * runs the existing what-if path (POST /whatif) to show before -> after.
 *
 * In mock mode /suggest returns 503; we surface the honest "needs real data"
 * message rather than a generic error. All copy comes from i18n.
 */

type SuggestState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "needsData" }
  | { kind: "error"; message: string }
  | { kind: "ready"; data: SuggestResponse };

type PreviewState =
  | { kind: "idle" }
  | { kind: "loading"; block: string }
  | { kind: "error"; message: string }
  | {
      kind: "ready";
      block: string;
      to: number;
      before: number;
      after: number;
    };

/** Default the first three clinic hours as the "current blocks" selection. */
const DEFAULT_BLOCK_COUNT = 3;

function anyIllustrative(sources: SuggestSource[]): boolean {
  return sources.some((s) => s.illustrative === true);
}

export function SuggestPanel({
  clinic,
  day,
  community = "all",
  cells,
}: {
  clinic: string;
  day: Day;
  /** the community the audit is scoped to (all | county) */
  community?: string;
  /** the current audit cells, used to show before -> after on preview */
  cells: AuditResponse["cells"];
}) {
  const { t } = useTranslation();

  // Which hours the clinic runs now (defaults to the first three clinic hours).
  const [selected, setSelected] = useState<number[]>(() =>
    HOURS.slice(0, DEFAULT_BLOCK_COUNT),
  );
  const [state, setState] = useState<SuggestState>({ kind: "idle" });
  const [preview, setPreview] = useState<PreviewState>({ kind: "idle" });

  const dayName = t(`audit.days.${day}`);

  const toggleHour = useCallback((hour: number) => {
    setSelected((prev) =>
      prev.includes(hour)
        ? prev.filter((h) => h !== hour)
        : [...prev, hour].sort((a, b) => a - b),
    );
  }, []);

  const shareOfBlock = useCallback(
    (data: AuditResponse["cells"], block: string): number | null => {
      const cell = data.find((c) => blockKey(c.day, c.hour) === block);
      return cell ? cell.share : null;
    },
    [],
  );

  const runSuggest = useCallback(() => {
    if (!clinic) return;
    setPreview({ kind: "idle" });
    setState({ kind: "loading" });
    const ac = new AbortController();
    getSuggest({ clinic, day, k: 3, blocks: selected, community }, ac.signal)
      .then((data) => setState({ kind: "ready", data }))
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 503) {
          setState({ kind: "needsData" });
          return;
        }
        const message =
          err instanceof ApiError ? err.message : t("suggest.error");
        setState({ kind: "error", message });
      });
  }, [clinic, day, community, selected, t]);

  const runPreview = useCallback(
    (change: Suggestion["change"]) => {
      if (!clinic) return;
      const before = shareOfBlock(cells, change.block) ?? 0;
      setPreview({ kind: "loading", block: change.block });
      const ac = new AbortController();
      postWhatIf(
        { clinic, community, shift: { block: change.block, to: change.to } },
        ac.signal,
      )
        .then((next) => {
          const movedTo = blockKey(change.block.slice(0, 3) as Day, change.to);
          const after = shareOfBlock(next.cells, movedTo) ?? 0;
          setPreview({
            kind: "ready",
            block: change.block,
            to: change.to,
            before,
            after,
          });
        })
        .catch((err: unknown) => {
          const message =
            err instanceof ApiError ? err.message : t("suggest.error");
          setPreview({ kind: "error", message });
        });
    },
    [clinic, community, cells, shareOfBlock, t],
  );

  const changes = state.kind === "ready" ? state.data.changes : [];

  const checkboxes = useMemo(
    () =>
      HOURS.map((hour) => {
        const id = `suggest-block-${hour}`;
        return (
          <label key={hour} className="checkbox-item" htmlFor={id}>
            <input
              id={id}
              type="checkbox"
              checked={selected.includes(hour)}
              onChange={() => toggleHour(hour)}
            />
            <span>{hourLabel(hour)}</span>
          </label>
        );
      }),
    [selected, toggleHour],
  );

  return (
    <section className="panel suggest-panel" aria-labelledby="suggest-h">
      <h2 id="suggest-h">{t("suggest.title")}</h2>
      <p className="text-muted">{t("suggest.intro")}</p>

      <fieldset className="suggest-blocks">
        <legend>{t("suggest.blocksLegend")}</legend>
        <p id="suggest-blocks-hint" className="text-muted">
          {t("suggest.blocksHint", { day: dayName })}
        </p>
        <div className="checkbox-group" aria-describedby="suggest-blocks-hint">
          {checkboxes}
        </div>
      </fieldset>

      <button
        type="button"
        className="suggest-run"
        onClick={runSuggest}
        disabled={!clinic || selected.length === 0 || state.kind === "loading"}
      >
        {state.kind === "loading" ? t("suggest.loading") : t("suggest.run")}
      </button>

      {state.kind === "loading" && (
        <p className="status" role="status">
          {t("suggest.loading")}
        </p>
      )}

      {state.kind === "needsData" && (
        <p className="notice" role="status">
          {t("suggest.needsData")}
        </p>
      )}

      {state.kind === "error" && (
        <div className="status error" role="alert">
          {state.message}{" "}
          <button type="button" onClick={runSuggest}>
            {t("suggest.retry")}
          </button>
        </div>
      )}

      {state.kind === "ready" && changes.length === 0 && (
        <p className="status" role="status">
          {t("suggest.empty")}
        </p>
      )}

      {state.kind === "ready" && changes.length > 0 && (
        <ol className="suggest-list">
          {changes.map((s, i) => {
            const illustrative = anyIllustrative(s.sources);
            const toHour = hourLabel(s.change.to);
            return (
              <li key={`${s.change.block}-${s.change.to}-${i}`} className="suggest-item">
                <p className="suggest-change">
                  {t("suggest.change", {
                    block: `${t(`audit.days.${s.change.block.slice(0, 3)}`)} ${hourLabel(
                      Number(s.change.block.slice(4)),
                    )}`,
                    hour: toHour,
                  })}
                </p>
                <ul className="suggest-gains">
                  <li>
                    {t("suggest.gainPeople", { count: s.gain_people })}
                  </li>
                  <li>
                    {t("suggest.gainVisitHours", {
                      hours: s.gain_visit_hours.toFixed(1),
                    })}
                  </li>
                </ul>

                {illustrative && (
                  <p className="notice illustrative" role="note">
                    {t("suggest.illustrative")}
                  </p>
                )}

                <div
                  className="suggest-sources"
                  role="group"
                  aria-label={t("suggest.sourcesLabel")}
                >
                  {s.sources.map((src, j) => (
                    <ProvenanceChip
                      key={`${src.name}-${src.vintage}-${j}`}
                      source={src}
                    />
                  ))}
                </div>

                <button
                  type="button"
                  className="suggest-preview"
                  onClick={() => runPreview(s.change)}
                  disabled={preview.kind === "loading"}
                >
                  {preview.kind === "loading" && preview.block === s.change.block
                    ? t("suggest.previewing")
                    : t("suggest.preview")}
                </button>

                {preview.kind === "ready" &&
                  preview.block === s.change.block &&
                  preview.to === s.change.to && (
                    <div className="beforeafter" role="status">
                      <strong>
                        {t("suggest.previewTitle", {
                          block: preview.block,
                          hour: hourLabel(preview.to),
                        })}
                        :
                      </strong>
                      <span>
                        {t("suggest.before")} {pct(preview.before)}
                      </span>
                      <span aria-hidden="true">→</span>
                      <span>
                        {t("suggest.after")} {pct(preview.after)}
                      </span>
                      <span
                        className={`delta ${
                          preview.after >= preview.before ? "up" : "down"
                        }`}
                      >
                        {t("suggest.delta")}{" "}
                        {deltaPts(preview.before, preview.after)} pts
                      </span>
                    </div>
                  )}
              </li>
            );
          })}
        </ol>
      )}

      {preview.kind === "error" && (
        <div className="status error" role="alert">
          {preview.message}
        </div>
      )}
    </section>
  );
}
