import { useEffect, useMemo, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
// MapLibre >= 5 runs its tile/GeoJSON processing in a module worker. Under Vite the
// pre-bundled copy cannot locate that worker ("Worker failed to load"), so no points
// ever render. Point it at the shipped worker file explicitly (Vite resolves ?url in
// dev and emits the asset in the build).
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import type { Feature, FeatureCollection, Point } from "geojson";
import { useTranslation } from "react-i18next";

import { getRural } from "../api/client";
import type { RuralResponse, RuralVerdict } from "../api/types";

/**
 * Block-group map with two lenses.
 *
 * - "reach": the OPTIONAL static GeoJSON `public/data/origins.geojson` (Point
 *   features: bg_geoid, carless_adults, ej_flag). If it is missing we show an
 *   accessible "map data not loaded" notice rather than crashing — the audit
 *   numbers above never depend on the map.
 * - "rural": GET /rural — every block group coloured by its "no option at all"
 *   verdict (transit | assisted_only | none | not_assessed), with a town filter,
 *   a text summary (no colour-only meaning) and the town's cited options.
 *
 * No basemap tiles from a paid or keyed service (ui-style.md): a blank style and
 * only our own points.
 */
maplibregl.setWorkerUrl(maplibreWorkerUrl);

const GEOJSON_URL = `${import.meta.env.BASE_URL}data/origins.geojson`;

type Lens = "reach" | "rural";

const VERDICTS: RuralVerdict[] = ["transit", "assisted_only", "none", "not_assessed"];
// Distinct from the EJ blues; each verdict also has a legend number and text.
const VERDICT_COLOR: Record<RuralVerdict, string> = {
  transit: "#2b8a3e",
  assisted_only: "#e8a33d",
  none: "#b42318",
  not_assessed: "#8a8f98",
};

const BLANK_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {},
  layers: [
    {
      id: "bg",
      type: "background",
      paint: { "background-color": "#e9edf1" },
    },
  ],
};

type CirclePaint = NonNullable<maplibregl.CircleLayerSpecification["paint"]>;

const REACH_PAINT: CirclePaint = {
  "circle-radius": 5,
  "circle-color": ["case", ["==", ["get", "ej_flag"], true], "#08519c", "#6baed6"],
  "circle-stroke-color": "#11181c",
  "circle-stroke-width": 1,
};

const RURAL_PAINT: CirclePaint = {
  "circle-radius": 5,
  "circle-color": [
    "match",
    ["get", "verdict"],
    "transit", VERDICT_COLOR.transit,
    "assisted_only", VERDICT_COLOR.assisted_only,
    "none", VERDICT_COLOR.none,
    VERDICT_COLOR.not_assessed,
  ],
  "circle-stroke-color": "#11181c",
  "circle-stroke-width": 1,
};

const EMPTY: FeatureCollection = { type: "FeatureCollection", features: [] };

function ruralToGeoJSON(r: RuralResponse): FeatureCollection {
  const features: Feature<Point>[] = r.features.map((f) => ({
    type: "Feature",
    geometry: { type: "Point", coordinates: [f.lon, f.lat] },
    properties: {
      bg_geoid: f.bg_geoid,
      town: f.town,
      verdict: f.verdict,
      carless_adults: f.carless_adults,
      transit_share: f.transit_share,
    },
  }));
  return { type: "FeatureCollection", features };
}

async function probeStatic(): Promise<FeatureCollection | null> {
  try {
    const res = await fetch(GEOJSON_URL, { headers: { Accept: "application/json" } });
    if (!res.ok) return null;
    const geojson = JSON.parse(await res.text()) as FeatureCollection;
    if (
      geojson.type !== "FeatureCollection" ||
      !Array.isArray(geojson.features) ||
      geojson.features.length === 0
    ) {
      return null;
    }
    return geojson;
  } catch {
    return null;
  }
}

type RuralLoad =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "ready"; data: RuralResponse };

export function BlockGroupMap() {
  const { t } = useTranslation();
  const ref = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [lens, setLens] = useState<Lens>("reach");
  const [town, setTown] = useState<string>("");
  const [staticGeo, setStaticGeo] = useState<FeatureCollection | null | "probing">("probing");
  const [rural, setRural] = useState<RuralLoad>({ kind: "idle" });
  const [mapReady, setMapReady] = useState(false);

  // 1. probe the optional static file once
  useEffect(() => {
    let cancelled = false;
    void probeStatic().then((g) => {
      if (!cancelled) setStaticGeo(g);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // 2. fetch the rural lens when selected (and whenever the town filter changes)
  useEffect(() => {
    if (lens !== "rural") return;
    const ctrl = new AbortController();
    setRural({ kind: "loading" });
    getRural(town ? { town } : {}, ctrl.signal)
      .then((data) => setRural({ kind: "ready", data }))
      .catch((err: unknown) => {
        if ((err as { name?: string })?.name === "AbortError") return;
        setRural({ kind: "error" });
      });
    return () => ctrl.abort();
  }, [lens, town]);

  const activeData: FeatureCollection | null = useMemo(() => {
    if (lens === "rural") {
      return rural.kind === "ready" && rural.data.features.length > 0
        ? ruralToGeoJSON(rural.data)
        : null;
    }
    return staticGeo && staticGeo !== "probing" ? staticGeo : null;
  }, [lens, rural, staticGeo]);

  // 3. create the map once we have something to draw; then just swap data/paint
  useEffect(() => {
    if (!activeData || !ref.current) return;
    const paint = lens === "rural" ? RURAL_PAINT : REACH_PAINT;
    if (mapRef.current) {
      const map = mapRef.current;
      const src = map.getSource("origins") as maplibregl.GeoJSONSource | undefined;
      if (src) {
        src.setData(activeData);
        for (const [k, v] of Object.entries(paint)) {
          map.setPaintProperty("origins-circles", k as keyof CirclePaint, v);
        }
        map.resize(); // the container may have been display:none while data loaded
      }
      return;
    }
    const map = new maplibregl.Map({
      container: ref.current,
      style: BLANK_STYLE,
      center: [-72.59, 42.25],
      zoom: 8.5,
      attributionControl: false,
    });
    map.addControl(new maplibregl.NavigationControl({}), "top-right");
    map.on("load", () => {
      map.addSource("origins", { type: "geojson", data: activeData ?? EMPTY });
      map.addLayer({ id: "origins-circles", type: "circle", source: "origins", paint });
      setMapReady(true);
    });
    mapRef.current = map;
  }, [activeData, lens]);

  useEffect(
    () => () => {
      mapRef.current?.remove();
      mapRef.current = null;
    },
    [],
  );

  const summary = rural.kind === "ready" ? rural.data.summary : null;
  const count = (v: RuralVerdict) => summary?.by_verdict[v]?.n_bg ?? 0;

  const lensToggle = (
    <div className="lens-toggle" role="group" aria-label={t("map.lensTitle")}>
      <button
        type="button"
        aria-pressed={lens === "reach"}
        onClick={() => setLens("reach")}
      >
        {t("map.lensReach")}
      </button>
      <button
        type="button"
        aria-pressed={lens === "rural"}
        onClick={() => setLens("rural")}
      >
        {t("map.lensRural")}
      </button>
    </div>
  );

  const showMap = activeData !== null;

  return (
    <section className="panel" aria-labelledby="map-h">
      <h2 id="map-h">{t("map.title")}</h2>
      {lensToggle}

      {lens === "rural" && rural.kind === "ready" && (
        <label className="field">
          {t("map.town")}{" "}
          <select value={town} onChange={(e) => setTown(e.target.value)}>
            <option value="">{t("map.allTowns")}</option>
            {rural.data.towns_available.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
      )}

      {lens === "reach" && staticGeo === null && (
        <p className="notice" role="note">
          {t("map.notLoaded")}
        </p>
      )}
      {lens === "rural" && rural.kind === "loading" && (
        <p className="status" role="status">
          {t("map.ruralLoading")}
        </p>
      )}
      {lens === "rural" &&
        (rural.kind === "error" ||
          (rural.kind === "ready" && rural.data.features.length === 0)) && (
          <p className="notice" role="note">
            {t("map.ruralUnavailable")}
          </p>
        )}

      {/* Always mounted (hidden when there is nothing to draw) so the MapLibre
          instance keeps its container across lens switches and data loads. */}
      <div
        className="map-wrap"
        ref={ref}
        role="group"
        aria-label={t("map.title")}
        data-ready={mapReady ? "true" : "false"}
        style={{ display: showMap ? undefined : "none" }}
      />

      {lens === "reach" && showMap && (
        <ol className="legend" aria-label={t("map.legendTitle")}>
          <li className="swatch">
            <span className="box" style={{ background: "#08519c" }} aria-hidden="true" />
            1. {t("equity.groups.ej")}
          </li>
          <li className="swatch">
            <span className="box" style={{ background: "#6baed6" }} aria-hidden="true" />
            2. {t("equity.groups.zero_veh")}
          </li>
        </ol>
      )}

      {lens === "rural" && summary && (
        <>
          <ol className="legend" aria-label={t("map.lensRural")}>
            {VERDICTS.map((v, i) => (
              <li key={v} className="swatch">
                <span
                  className="box"
                  style={{ background: VERDICT_COLOR[v] }}
                  aria-hidden="true"
                />
                {i + 1}. {t(`map.verdict.${v}`)} ({count(v)})
              </li>
            ))}
          </ol>
          <p className="rural-summary">
            {t("map.ruralSummary", {
              none: count("none"),
              noneAdults: summary.by_verdict.none?.carless_adults ?? 0,
              assisted: count("assisted_only"),
              transit: count("transit"),
              notAssessed: count("not_assessed"),
            })}
          </p>
          {rural.kind === "ready" && town && rural.data.options.length > 0 && (
            <div className="rural-options">
              <h3>{t("map.optionsTitle")}</h3>
              <ul>
                {rural.data.options.map((o) => (
                  <li key={o.town}>
                    <strong>{o.town}</strong>: {o.dial_a_ride || "—"}; {o.coa_driver || "—"};{" "}
                    {o.pt1 || "—"}{" "}
                    {o.source_url && (
                      <a href={o.source_url} target="_blank" rel="noreferrer">
                        ({t("map.optionsSource")}, {o.date ?? ""})
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </section>
  );
}
