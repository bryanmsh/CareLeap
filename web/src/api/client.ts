// Typed API client. Every UI number comes from here (ui-style.md: all data from
// our API; never call live third-party routing/geocoding from the browser).
//
// Base URL: VITE_API_BASE, default http://127.0.0.1:8000. In dev, vite proxies
// "/api" -> FastAPI; set VITE_API_BASE="/api" to use that proxy instead.

import type {
  RuralResponse,
  AuditResponse,
  BlockGroupsResponse,
  ClinicsResponse,
  Day,
  PlanRequest,
  PlanResponse,
  ProvenanceResponse,
  SuggestResponse,
  WhatIfRequest,
} from "./types";

export * from "./types";

const BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined) ??
  "http://127.0.0.1:8000";

/** Thrown for any non-2xx or transport failure; carries the HTTP status. */
export class ApiError extends Error {
  readonly status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function joinUrl(path: string): string {
  const base = BASE.replace(/\/+$/, "");
  return `${base}${path}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(joinUrl(path), {
      ...init,
      headers: { Accept: "application/json", ...(init?.headers ?? {}) },
    });
  } catch (cause) {
    throw new ApiError(
      `Network error contacting the API at ${BASE}`,
      0,
    );
  }
  if (!res.ok) {
    let detail = "";
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (body && typeof body.detail === "string") detail = `: ${body.detail}`;
    } catch {
      // non-JSON error body; ignore
    }
    throw new ApiError(`Request failed (${res.status})${detail}`, res.status);
  }
  return (await res.json()) as T;
}

export interface AuditQuery {
  clinic: string;
  community: string;
  day: Day;
}

/** GET /audit?clinic&community&day */
export function getAudit(
  { clinic, community, day }: AuditQuery,
  signal?: AbortSignal,
): Promise<AuditResponse> {
  const q = new URLSearchParams({ clinic, community, day });
  return request<AuditResponse>(`/audit?${q.toString()}`, { signal });
}

/** POST /whatif — returns the same shape as /audit so the UI reuses one renderer. */
export function postWhatIf(
  body: WhatIfRequest,
  signal?: AbortSignal,
): Promise<AuditResponse> {
  return request<AuditResponse>(`/whatif`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
}

/** GET /clinics */
export function getClinics(signal?: AbortSignal): Promise<ClinicsResponse> {
  return request<ClinicsResponse>(`/clinics`, { signal });
}

export interface BlockGroupsQuery {
  clinic: string;
  day: Day;
  hour?: number;
  community?: string;
}

/** GET /audit/blockgroups — per-block-group share for the map. */
export function getBlockGroups(
  { clinic, day, hour, community }: BlockGroupsQuery,
  signal?: AbortSignal,
): Promise<BlockGroupsResponse> {
  const q = new URLSearchParams({ clinic, day });
  if (hour != null) q.set("hour", String(hour));
  if (community) q.set("community", community);
  return request<BlockGroupsResponse>(
    `/audit/blockgroups?${q.toString()}`,
    { signal },
  );
}

export interface SuggestQuery {
  clinic: string;
  day: Day;
  /** top-k changes to return (1..10). Defaults to 3. */
  k?: number;
  /** the clinic's CURRENT block start hours for that day, e.g. [7, 8, 17]. */
  blocks?: number[];
  /** optimize for this community (all | county); defaults to all. */
  community?: string;
}

/** GET /suggest?clinic&day&k&blocks — top-k schedule changes (optimizer).
 * Returns 503 in mock mode (no real cube): the UI shows "needs real data". */
export function getSuggest(
  { clinic, day, k = 3, blocks, community }: SuggestQuery,
  signal?: AbortSignal,
): Promise<SuggestResponse> {
  const q = new URLSearchParams({ clinic, day, k: String(k) });
  if (blocks && blocks.length > 0) q.set("blocks", blocks.join(","));
  if (community && community !== "all") q.set("community", community);
  return request<SuggestResponse>(`/suggest?${q.toString()}`, { signal });
}

export interface RuralQuery {
  /** optional town filter (case-insensitive); omit for every block group */
  town?: string;
}

/** GET /rural?town — rural lens: per-block-group "no option at all" verdict.
 * Mock mode returns an empty, labelled answer: the map shows "needs real data". */
export function getRural(
  { town }: RuralQuery = {},
  signal?: AbortSignal,
): Promise<RuralResponse> {
  const q = new URLSearchParams();
  if (town) q.set("town", town);
  const qs = q.toString();
  return request<RuralResponse>(`/rural${qs ? `?${qs}` : ""}`, { signal });
}

/** POST /plan — build a Visit Planner plan (M4). Synthetic patient only. */
export function postPlan(
  body: PlanRequest,
  signal?: AbortSignal,
): Promise<PlanResponse> {
  return request<PlanResponse>(`/plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
}

/** GET /provenance?id — the "How we know this is right" drawer source (M4). */
export function getProvenance(
  id: string,
  signal?: AbortSignal,
): Promise<ProvenanceResponse> {
  const q = new URLSearchParams({ id });
  return request<ProvenanceResponse>(`/provenance?${q.toString()}`, { signal });
}

export const apiBase = BASE;
