import { useState, type ReactElement } from "react";
import { useTranslation } from "react-i18next";
import type { PlanLeg, PlanResponse, OptionKind } from "../api/types";
import { ProvenanceChip } from "./ProvenanceChip";

/** Seconds since local midnight -> "HH:MM" clock time. GTFS times may exceed
 * 86400 (past midnight); we show the wall-clock hour with mod, never wrapping
 * the stored seconds (contracts.md convention). */
function clock(sec: number): string {
  const m = Math.floor((sec % 86400) / 60);
  const hh = String(Math.floor(m / 60)).padStart(2, "0");
  const mm = String(m % 60).padStart(2, "0");
  return `${hh}:${mm}`;
}

interface TransitSummary {
  leave_home: number;
  arrive_clinic: number;
  depart_clinic: number;
  arrive_home: number;
  last_bus_home: number | null;
  routes_out: (string | null)[];
  routes_ret: (string | null)[];
  buses: number;
  door_to_door_min: number;
}

/** "Thu 12 Nov, 15:30" in the active locale, from the option's ISO slot. */
function whenLabel(iso: string, lang: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat(lang, {
    weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
  }).format(d);
}

function routes(ids: (string | null)[]): string {
  // Collapse a transfer between two trips of the same route ("P20 → P20") to one name.
  const named = ids.filter((r): r is string => !!r).filter((r, i, a) => i === 0 || r !== a[i - 1]);
  return named.length ? named.join(" → ") : "—";
}

/** What makes THIS option different from the one above it: the date and time, and
 * the bus round trip behind it (leave, routes, back home, last bus). For a ride the
 * bus trip is only the travel-time estimate the escort rule was checked against. */
function OptionDetails({ details }: { details: Record<string, unknown> }) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const slot = typeof details.slot === "string" ? details.slot : null;
  const transit = (details.transit ?? details.transit_estimate) as TransitSummary | undefined;
  const isEstimate = !details.transit && !!details.transit_estimate;
  const rideMode = typeof details.ride_mode === "string" ? details.ride_mode : null;
  const alsoOn = Array.isArray(details.also_on) ? (details.also_on as string[]) : [];
  const sheet = typeof details.sheet === "string" ? details.sheet : null;
  const status = typeof details.template_status === "string" ? details.template_status : null;
  if (status) {
    return (
      <div className="option-detail-prep">
        <p className="text-muted">
          {status === "reviewed" ? t("planner.prep.reviewed") : t("planner.prep.pending")}
        </p>
        {sheet && (
          <details>
            <summary>{t("planner.prep.open")}</summary>
            <Sheet text={sheet} />
          </details>
        )}
      </div>
    );
  }
  if (!slot && !transit && !rideMode) return null;
  return (
    <dl className="option-detail">
      {slot && (
        <div>
          <dt>{t("planner.plan.detail.when")}</dt>
          <dd>{whenLabel(slot, lang)}</dd>
        </div>
      )}
      {alsoOn.length > 0 && (
        <div>
          <dt>{t("planner.plan.detail.alsoOn")}</dt>
          <dd>
            {alsoOn.slice(0, 4).map((d) => dateLabel(d, lang)).join(", ")}
            {alsoOn.length > 4 && ` ${t("planner.plan.detail.andMore", { n: alsoOn.length - 4 })}`}
          </dd>
        </div>
      )}
      {rideMode && (
        <div>
          <dt>{t("planner.plan.detail.rideMode")}</dt>
          <dd>{t(`planner.plan.detail.rideModes.${rideMode}`)}</dd>
        </div>
      )}
      {transit && (
        <>
          <div>
            <dt>{isEstimate ? t("planner.plan.detail.busEstimate") : t("planner.plan.detail.bus")}</dt>
            <dd>
              {t("planner.plan.detail.leave", { time: clock(transit.leave_home) })} → {" "}
              {t("planner.plan.detail.atClinic", { time: clock(transit.arrive_clinic) })} ({routes(transit.routes_out)})
            </dd>
          </div>
          <div>
            <dt>{t("planner.plan.detail.back")}</dt>
            <dd>
              {clock(transit.depart_clinic)} → {clock(transit.arrive_home)} ({routes(transit.routes_ret)})
              {transit.last_bus_home != null && (
                <> · {t("planner.plan.detail.lastBus", { time: clock(transit.last_bus_home) })}</>
              )}
            </dd>
          </div>
          <div>
            <dt>{t("planner.plan.detail.total")}</dt>
            <dd>{t("planner.plan.detail.totalValue", { buses: transit.buses, min: transit.door_to_door_min })}</dd>
          </div>
        </>
      )}
    </dl>
  );
}

function dateLabel(isoDate: string, lang: string): string {
  const d = new Date(`${isoDate}T12:00:00`);
  if (Number.isNaN(d.getTime())) return isoDate;
  return new Intl.DateTimeFormat(lang, { weekday: "short", day: "numeric", month: "short" }).format(d);
}

/** The ride's timeline, from the rulebook's numbers only (no invented drive times). */
function RideTimeline({ details, compact = false }: { details: Record<string, unknown>; compact?: boolean }) {
  const { t, i18n } = useTranslation();
  const slot = typeof details.slot === "string" ? details.slot : null;
  const checkIn = typeof details.check_in_by === "number" ? details.check_in_by : null;
  const ends = typeof details.visit_ends === "number" ? details.visit_ends : null;
  if (!slot) return null;
  const items = [
    t("planner.ride.appointment", { when: whenLabel(slot, i18n.language) }),
    checkIn != null ? t("planner.ride.checkIn", { time: clock(checkIn) }) : null,
    ends != null ? t("planner.ride.ends", { time: clock(ends) }) : null,
    details.escort_required ? t("planner.ride.escort") : null,
    t("planner.ride.pickup"),
  ].filter((x): x is string => !!x);
  return (
    <ol className={compact ? "phone-legs" : "ride-timeline"}>
      {items.map((line) => (
        <li key={line}>{line}</li>
      ))}
    </ol>
  );
}

/** Render the reviewed prep-sheet markdown (headings, bullets, **bold**) as plain
 * elements. The text is the template's; only token values were filled server-side. */
function Sheet({ text }: { text: string }) {
  const bold = (line: string) =>
    line.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
      part.startsWith("**") && part.endsWith("**") ? <strong key={i}>{part.slice(2, -2)}</strong> : part,
    );
  const out: ReactElement[] = [];
  let bullets: string[] = [];
  const flush = () => {
    if (bullets.length) {
      out.push(<ul key={`ul-${out.length}`}>{bullets.map((b, i) => <li key={i}>{bold(b)}</li>)}</ul>);
      bullets = [];
    }
  };
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    if (line.startsWith("- ")) { bullets.push(line.slice(2)); continue; }
    flush();
    if (!line) continue;
    if (line.startsWith("## ")) out.push(<h5 key={out.length}>{line.slice(3)}</h5>);
    else if (line.startsWith("# ")) out.push(<h4 key={out.length}>{line.slice(2)}</h4>);
    else if (line.startsWith("*") && line.endsWith("*") && !line.startsWith("**"))
      out.push(<p key={out.length}><em>{line.slice(1, -1)}</em></p>);
    else out.push(<p key={out.length}>{bold(line)}</p>);
  }
  flush();
  return <div className="prep-sheet">{out}</div>;
}

/** A per-option icon/shape so meaning is never colour-only (UP-P4). */
const KIND_ICON: Record<OptionKind, string> = {
  slot: "🚌",
  ride: "🚐",
  tele: "📞",
  prep: "📄",
  none: "🧭",
};

function Leg({ leg }: { leg: PlanLeg }) {
  const { t } = useTranslation();
  const mode =
    leg.kind === "bus"
      ? t("planner.itinerary.bus", { route: leg.route_id ?? "" })
      : t("planner.itinerary.walk");
  return (
    <li className="leg">
      <span className="leg-mode">{mode}</span>{" "}
      <span className="leg-detail">
        {t("planner.itinerary.from", { stop: leg.from_stop })}{" "}
        {t("planner.itinerary.to", { stop: leg.to_stop })}{" "}
        {t("planner.itinerary.at", { time: clock(leg.dep) })}
      </span>
    </li>
  );
}

export function PlanView({ plan }: { plan: PlanResponse }) {
  const { t } = useTranslation();
  const topRide = plan.options[0]?.kind === "ride" ? plan.options[0] : null;
  const it = plan.itinerary;
  const hasItinerary = it.out_legs.length > 0 || it.ret_legs.length > 0;
  const pt1Entries = Object.entries(plan.pt1_prefill ?? {});
  // Real data can return one ride per bookable date; show the top few, keep the rest
  // one click away (ranking is the solver's, the UI never reorders).
  const SHOW = 3;
  const [showAll, setShowAll] = useState(false);
  // The prep sheet is not an alternative to the trip, it goes WITH it: never hide it.
  const choices = plan.options.filter((o) => o.kind !== "prep");
  const preps = plan.options.filter((o) => o.kind === "prep");
  const visible = [...(showAll ? choices : choices.slice(0, SHOW)), ...preps];
  const hidden = plan.options.length - visible.length;

  return (
    <section aria-labelledby="plan-heading" className="plan-view">
      <h2 id="plan-heading">{t("planner.plan.heading")}</h2>

      <ol className="option-list">
        {visible.map((o, idx) => {
          const rec =
            (o.details?.recurrence as { per_week?: number } | undefined) ?? null;
          return (
            <li key={`${o.kind}-${idx}`} className={`option option-${o.kind}`}>
              <div className="option-head">
                <span aria-hidden="true" className="option-icon">
                  {KIND_ICON[o.kind]}
                </span>
                <span className="option-kind">
                  {t(`planner.plan.optionKinds.${o.kind}`)}
                </span>
                {idx === 0 && o.kind !== "none" && (
                  <span className="badge">{t("planner.plan.recommended")}</span>
                )}
              </div>
              <p className="option-why">
                <span className="option-why-label">
                  {t("planner.plan.whichReason")}:
                </span>{" "}
                {o.why}
              </p>
              <OptionDetails details={o.details} />
              {rec?.per_week != null && (
                <p className="option-recurrence">
                  {t("planner.plan.recurrence", { count: rec.per_week })}
                </p>
              )}
            </li>
          );
        })}
      </ol>
      {choices.length > SHOW && (
        <button
          type="button"
          className="show-more"
          aria-expanded={showAll}
          onClick={() => setShowAll((v) => !v)}
        >
          {showAll
            ? t("planner.plan.showLess")
            : t("planner.plan.showMore", { n: hidden })}
        </button>
      )}

      {/* Itinerary */}
      <section aria-labelledby="itin-heading" className="itinerary">
        <h3 id="itin-heading">{t("planner.itinerary.title")}</h3>
        {hasItinerary ? (
          <div className="itin-cols">
            <div>
              <h4>{t("planner.itinerary.out")}</h4>
              <ol className="legs">
                {it.out_legs.map((leg, k) => (
                  <Leg key={`out-${k}`} leg={leg} />
                ))}
              </ol>
            </div>
            <div>
              <h4>{t("planner.itinerary.ret")}</h4>
              <ol className="legs">
                {it.ret_legs.map((leg, k) => (
                  <Leg key={`ret-${k}`} leg={leg} />
                ))}
              </ol>
              {it.last_bus_home != null && (
                <p className="last-bus">
                  {t("planner.itinerary.lastBus", {
                    time: clock(it.last_bus_home),
                  })}
                </p>
              )}
            </div>
          </div>
        ) : (
          topRide ? (
            <RideTimeline details={topRide.details} />
          ) : (
            <p className="text-muted">{t("planner.itinerary.none")}</p>
          )
        )}
        {/* plan_b renders ONLY when the API supplies it (reviewed templates, M3). */}
        {it.plan_b && <p className="plan-b">{it.plan_b}</p>}
      </section>

      {/* Phone-sized preview */}
      <section aria-labelledby="phone-heading" className="phone-preview-wrap">
        <h3 id="phone-heading">{t("planner.phone.title")}</h3>
        <p className="text-muted">{t("planner.phone.help")}</p>
        <div className="phone-frame" data-testid="phone-preview">
          <div className="phone-screen">
            <p className="phone-title">
              {t(`planner.plan.optionKinds.${plan.options[0]?.kind ?? "none"}`)}
            </p>
            {hasItinerary ? (
              <ol className="phone-legs">
                {[...it.out_legs, ...it.ret_legs].map((leg, k) => (
                  <li key={`p-${k}`}>
                    {leg.kind === "bus"
                      ? t("planner.itinerary.bus", { route: leg.route_id ?? "" })
                      : t("planner.itinerary.walk")}{" "}
                    {clock(leg.dep)}
                  </li>
                ))}
              </ol>
            ) : (
              topRide ? (
                <RideTimeline details={topRide.details} compact />
              ) : (
                <p>{t("planner.itinerary.none")}</p>
              )
            )}
          </div>
        </div>
      </section>

      {/* PT-1 pre-fill summary */}
      <section aria-labelledby="pt1-heading" className="pt1-summary">
        <h3 id="pt1-heading">{t("planner.pt1.title")}</h3>
        <p className="text-muted">{t("planner.pt1.note")}</p>
        {pt1Entries.length > 0 ? (
          <dl className="pt1-list">
            {pt1Entries.map(([k, v]) => (
              <div key={k} className="pt1-row">
                <dt>{t(`planner.pt1.fields.${k}`, { defaultValue: k })}</dt>
                <dd>
                  {v == null || v === "" ? (
                    <em className="pt1-todo">{t("planner.pt1.toComplete")}</em>
                  ) : (
                    String(v)
                  )}
                </dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="text-muted">{t("planner.pt1.empty")}</p>
        )}
      </section>

      {/* Provenance: the plan's reachability rests on the router's round-trip
          rule. The chip opens the drawer (RT-8 from the raptor-router spec). */}
      <ProvenanceChip
        source={{ name: "PVTA GTFS", vintage: "2026-09-18" }}
        provId="RT-8"
      />
    </section>
  );
}
