import { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError, postPlan } from "../api/client";
import type { PlanBarriers, PlanRequest, PlanResponse } from "../api/types";
import { BarrierCheck } from "../components/BarrierCheck";
import { PlanView } from "../components/PlanView";
import { ProvenanceDrawer } from "../components/ProvenanceDrawer";
import { ProvenanceContext } from "../components/provenance-context";
import type { OpenProvenance } from "../components/provenance-context";

/** Visit types the planner knows (labels in plain words, UP-1.2). The keys match
 * the rulebook visit_type; the demo set mirrors planner/visit_rules.yaml. */
const VISIT_TYPES = ["colonoscopy", "prenatal", "dialysis", "chemo"] as const;

/** Fixed SYNTHETIC demo patient — the UI never collects PHI (product.md). */
const SYNTHETIC_PATIENT = { id: "maria", origin_bg: "250138121032" };

type Phase =
  | { k: "pick" }
  | { k: "barriers"; visitType: string }
  | { k: "loading"; visitType: string }
  | { k: "error"; visitType: string; message: string }
  | { k: "plan"; visitType: string; plan: PlanResponse };

export function Planner() {
  const { t, i18n } = useTranslation();
  const [phase, setPhase] = useState<Phase>({ k: "pick" });
  const [visitType, setVisitType] = useState<string>(VISIT_TYPES[0]);
  const [largeType, setLargeType] = useState(false);

  // Provenance drawer state.
  const [prov, setProv] = useState<{ id: string; opener: HTMLElement | null } | null>(
    null,
  );
  const openProvenance = useCallback<OpenProvenance>((id, opener) => {
    setProv({ id, opener });
  }, []);

  const submit = useCallback(
    (barriers: PlanBarriers) => {
      const vt = phase.k === "barriers" ? phase.visitType : visitType;
      const body: PlanRequest = {
        patient: { ...SYNTHETIC_PATIENT, lang: barriers.language },
        visit_type: vt,
        barriers,
      };
      setPhase({ k: "loading", visitType: vt });
      postPlan(body)
        .then((plan) => setPhase({ k: "plan", visitType: vt, plan }))
        .catch((err: unknown) => {
          const message =
            err instanceof ApiError ? err.message : t("planner.plan.error");
          setPhase({ k: "error", visitType: vt, message });
        });
    },
    [phase, visitType, t],
  );

  const lang = i18n.resolvedLanguage ?? "en";

  return (
    <ProvenanceContext.Provider value={openProvenance}>
      <div className={largeType ? "planner large-type" : "planner"}>
        <div className="planner-head">
          <h1>{t("planner.title")}</h1>
          <label className="large-type-toggle">
            <input
              type="checkbox"
              checked={largeType}
              onChange={(e) => setLargeType(e.target.checked)}
            />
            {t("planner.largeType")}
          </label>
        </div>
        <p>{t("planner.intro")}</p>
        <p className="notice" role="note">
          {t("planner.logisticsNote")} {t("planner.synthetic")}
        </p>

        {phase.k === "pick" && (
          <section aria-labelledby="pick-title">
            <fieldset>
              <legend id="pick-title">{t("planner.pickVisit.legend")}</legend>
              <p className="text-muted">{t("planner.pickVisit.hint")}</p>
              <div className="visit-types" role="radiogroup" aria-labelledby="pick-title">
                {VISIT_TYPES.map((vt) => (
                  <button
                    key={vt}
                    type="button"
                    className="tap"
                    role="radio"
                    aria-checked={visitType === vt}
                    onClick={() => setVisitType(vt)}
                    data-testid={`visit-${vt}`}
                  >
                    {vt}
                  </button>
                ))}
              </div>
            </fieldset>
            <button
              type="button"
              className="btn-primary"
              onClick={() => setPhase({ k: "barriers", visitType })}
              data-testid="start-barriers"
            >
              {t("planner.pickVisit.next")}
            </button>
          </section>
        )}

        {phase.k === "barriers" && (
          <BarrierCheck
            lang={lang}
            onSubmit={submit}
            onBack={() => setPhase({ k: "pick" })}
          />
        )}

        {phase.k === "loading" && (
          <div className="status" role="status">
            {t("planner.plan.loading")}
          </div>
        )}

        {phase.k === "error" && (
          <div className="status error" role="alert">
            {phase.message}{" "}
            <button
              type="button"
              onClick={() => setPhase({ k: "barriers", visitType: phase.visitType })}
            >
              {t("planner.plan.retry")}
            </button>
          </div>
        )}

        {phase.k === "plan" && <PlanView plan={phase.plan} />}

        {prov && (
          <ProvenanceDrawer
            id={prov.id}
            restoreFocusTo={prov.opener}
            onClose={() => setProv(null)}
          />
        )}
      </div>
    </ProvenanceContext.Provider>
  );
}
