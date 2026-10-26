// Contract types — hand-mirrored from docs/contracts.md §3 and cross-checked
// against the generated OpenAPI schema (./schema.d.ts). These are the shapes the
// UI renders; a drift between this file and schema.d.ts is a bug.
//
// Times are integer seconds since local-midnight of the service date and may
// exceed 86400 (never wrapped) — see docs/contracts.md conventions.

import type { components } from "./schema";

export type Day = "mon" | "tue" | "wed" | "thu" | "fri" | "sat" | "sun";

/** One hour cell of the audit grid. `share = reached / n`. */
export interface AuditCell {
  day: Day;
  /** appointment start hour, 24h local (7..18) */
  hour: number;
  /** reached / n, 0.0..1.0 */
  share: number;
  /** car-less adults in the community */
  n: number;
  /** how many of them can reach the clinic for this hour */
  reached: number;
}

/** One equity split: a share of a subpopulation of size n. */
export interface EquityGroup {
  share: number;
  n: number;
}

/** The four equity splits shown in the EquityPanel. */
export interface Equity {
  ej: EquityGroup;
  lep: EquityGroup;
  age65: EquityGroup;
  zero_veh: EquityGroup;
}

/** A citation for an on-screen number: name + vintage, optional link. */
export interface SourceRef {
  name: string;
  vintage: string;
  url?: string | null;
}

/** GET /audit and POST /whatif both return this shape. */
export interface AuditResponse {
  cells: AuditCell[];
  equity: Equity;
  sources: SourceRef[];
}

/** POST /whatif request body. */
export interface WhatIfRequest {
  clinic: string;
  shift: {
    /** e.g. "mon-08" — a (day, hour) block */
    block: string;
    /** new start hour, 24h local */
    to: number;
  };
  /** same scope as the audit on screen; omitted = all */
  community?: string;
}

/** GET /clinics — the clinics the audit covers. */
export interface Clinic {
  clinic_id: string;
  clinic_name: string;
  visit_type: string;
  visit_minutes: number;
  stop_id: string;
  is_demo_anchor: boolean;
}

export interface ClinicsResponse {
  clinics: Clinic[];
  sources: SourceRef[];
}

/** GET /audit/blockgroups — per-block-group reachable share for the map. */
export interface BlockGroupFeature {
  bg_geoid: string;
  lat: number;
  lon: number;
  carless_adults: number;
  share: number;
  /** transit desert for this clinic/day/hour */
  desert: boolean;
}

export interface BlockGroupsResponse {
  features: BlockGroupFeature[];
  sources: SourceRef[];
}

/** One top-k schedule change the optimizer proposes (GET /suggest). */
export interface SuggestChange {
  /** optimizer move kind, e.g. "move_block" */
  kind: string;
  day: string;
  /** block key the change acts on, e.g. "mon-08" */
  block: string;
  /** new start hour, 24h local */
  to: number;
}

/** One suggestion: a change plus the gain it buys and its citations. */
export interface Suggestion {
  change: SuggestChange;
  /** extra visit-hours of reach this change buys */
  gain_visit_hours: number;
  /** extra car-less adults reached by this change */
  gain_people: number;
  /** provenance for every number in this suggestion; a source may carry
   * `illustrative: true` when it is not yet backed by real data. */
  sources: SuggestSource[];
}

/** A source ref on a suggestion. Superset of SourceRef: the optimizer may flag
 * a source as illustrative (synthetic/placeholder, not real-data-backed). */
export interface SuggestSource extends SourceRef {
  illustrative?: boolean;
}

/** GET /suggest?clinic&day&k&blocks — top-k schedule changes. */
export interface SuggestResponse {
  clinic: string;
  day: string;
  k: number;
  baseline_score: number;
  suggested_score: number;
  baseline_blocks: number[];
  suggested_blocks: number[];
  open_hours: number[];
  changes: Suggestion[];
  sources: SuggestSource[];
}

// --------------------------------------------------------------------------- //
// POST /plan (M4) — docs/contracts.md §3
// --------------------------------------------------------------------------- //

/** Synthetic patient only — never real PHI. */
export interface PlanPatient {
  id: string;
  /** 12-digit Census block-group GEOID */
  origin_bg: string;
  lang: string;
}

/** Barrier-check answers. `work_shift` / `childcare_window` are [start, end] hours
 * (24h local), may cross midnight, or null when not given (VP-20). */
export interface PlanBarriers {
  has_transport: boolean;
  work_shift: [number, number] | null;
  childcare: boolean;
  has_escort: boolean;
  cost_worry: boolean;
  language: string;
  childcare_window?: [number, number] | null;
}

export interface PlanRequest {
  patient: PlanPatient;
  visit_type: string;
  barriers: PlanBarriers;
}

/** Fixed contract option kinds, in render order. */
export type OptionKind = "slot" | "ride" | "tele" | "prep" | "none";

/** One plan option. `details` is an open bag the API fills per kind. */
export interface PlanOption {
  kind: OptionKind;
  details: Record<string, unknown>;
  /** plain-language, logistics-only reason this option is offered */
  why: string;
}

/** One journey leg (Leg, contracts.md §2). Times are seconds since local
 * midnight and may exceed 86400 (never wrapped). */
export interface PlanLeg {
  kind: "walk" | "bus";
  from_stop: string;
  to_stop: string;
  route_id: string | null;
  dep: number;
  arr: number;
}

export interface PlanItinerary {
  out_legs: PlanLeg[];
  ret_legs: PlanLeg[];
  last_bus_home: number | null;
  /** patient-facing; null until reviewed templates (M3) exist */
  plan_b: string | null;
}

export interface PlanResponse {
  options: PlanOption[];
  itinerary: PlanItinerary;
  pt1_prefill: Record<string, unknown>;
}

// --------------------------------------------------------------------------- //
// GET /provenance?id (M4 with M1) — docs/contracts.md §3
// --------------------------------------------------------------------------- //

export type PropertyState = "pass" | "fail" | "pending";

export interface ProvenanceProperty {
  name: string;
  status: PropertyState;
}

export interface ProvenanceResponse {
  source: { name: string; vintage: string };
  requirement_id: string;
  properties: ProvenanceProperty[];
  spec_link: string;
}

// --- Compile-time assertions that our hand types match the generated schema.
// If the OpenAPI schema drifts from this file, one of these lines fails to
// typecheck, which fails `npm run build`.
type _AssertAssignable<A extends B, B> = [A] extends [B] ? true : never;
export type _AuditOk = _AssertAssignable<
  components["schemas"]["AuditResponse"],
  AuditResponse
>;
export type _CellOk = _AssertAssignable<
  components["schemas"]["AuditCell"],
  AuditCell
>;
export type _EquityOk = _AssertAssignable<
  components["schemas"]["Equity"],
  Equity
>;
export type _SourceOk = _AssertAssignable<
  components["schemas"]["SourceRef"],
  SourceRef
>;
export type _ClinicsOk = _AssertAssignable<
  components["schemas"]["ClinicsResponse"],
  ClinicsResponse
>;
export type _BgOk = _AssertAssignable<
  components["schemas"]["BlockGroupsResponse"],
  BlockGroupsResponse
>;

/** GET /rural — rural lens (docs/contracts.md §3). */
export type RuralVerdict = "transit" | "assisted_only" | "none" | "not_assessed";

export interface RuralFeature {
  bg_geoid: string;
  town: string;
  county: string;
  lat: number;
  lon: number;
  carless_adults: number;
  /** share of ALL cube cells (every clinic × day × hour) that are reachable, 0..1 */
  transit_share: number;
  /** no PVTA/FRTA stop within the walk limit */
  desert: boolean;
  verdict: RuralVerdict;
  coverage_tier: string;
}

export interface RuralVerdictCount {
  n_bg: number;
  carless_adults: number;
}

export interface RuralSummary {
  n_bg: number;
  carless_adults: number;
  by_verdict: Record<string, RuralVerdictCount>;
}

/** One town's row from the hand-collected rural tables, with its citation. */
export interface RuralOption {
  town: string;
  county?: string | null;
  coverage_tier?: string | null;
  has_any_option: boolean;
  dial_a_ride?: string | null;
  coa_driver?: string | null;
  pt1?: string | null;
  source_url?: string | null;
  verified_by?: string | null;
  date?: string | null;
}

export interface RuralResponse {
  town?: string | null;
  features: RuralFeature[];
  summary: RuralSummary;
  options: RuralOption[];
  towns_available: string[];
  sources: SourceRef[];
}
