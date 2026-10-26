import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * Planner e2e (ui-planner). The app calls same-origin "/api/*"
 * (VITE_API_BASE=/api, see playwright.config.ts), so page.route stubs it and no
 * backend runs. The plan fixture is Maria's escort colonoscopy: an escort-aware
 * RIDE (never a transit-only slot), a bus itinerary, a Spanish PREP sheet and a
 * PT-1 pre-fill. /provenance answers the RT-8 round-trip rule.
 */

// Maria: escort required -> RIDE first, never a SLOT (VP-5 / UP-3.4).
const PLAN_RESPONSE = {
  options: [
    {
      kind: "ride",
      details: {
        slot: "2026-11-12T15:30:00",
        clinic_id: "BAY_GI_SPRINGFIELD",
        escort_required: true,
        has_escort: true,
        pt1_request: true,
        recurrence: null,
      },
      why: "This visit type requires an escort home, so a transit-only plan is not offered. Request an escort-aware ride.",
    },
    {
      kind: "prep",
      details: { language: "es", template_status: "pending_review" },
      why: "This visit type has a prep sheet. Attach the reviewed version in the preferred language.",
    },
  ],
  itinerary: {
    out_legs: [
      { kind: "walk", from_stop: "origin", to_stop: "S1", route_id: null, dep: 50400, arr: 50700 },
      { kind: "bus", from_stop: "S1", to_stop: "S2", route_id: "B43", dep: 50700, arr: 53100 },
    ],
    ret_legs: [
      { kind: "bus", from_stop: "S2", to_stop: "S1", route_id: "B43", dep: 64800, arr: 67200 },
      { kind: "walk", from_stop: "S1", to_stop: "origin", route_id: null, dep: 67200, arr: 67500 },
    ],
    last_bus_home: 64800,
    plan_b: null,
  },
  pt1_prefill: {
    member_id: "maria",
    appointment_time: "15:30",
    escort_name: null,
  },
};

const PROVENANCE_RT8 = {
  source: { name: "PVTA GTFS", vintage: "2026-09-18" },
  requirement_id: "RT-8",
  properties: [
    { name: "round-trip soundness", status: "pass" },
    { name: "midnight safety", status: "pass" },
  ],
  spec_link: ".kiro/specs/raptor-router/requirements.md#RT-8",
};

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function mockPlannerApi(page: Page): Promise<void> {
  await page.route(
    (url) => url.pathname.startsWith("/api/"),
    async (route) => {
      const url = new URL(route.request().url());
      const path = url.pathname.replace(/^\/api/, "");
      if (path === "/plan" && route.request().method() === "POST") {
        return json(route, PLAN_RESPONSE);
      }
      if (path === "/provenance") {
        const id = url.searchParams.get("id");
        if (id === "RT-8") return json(route, PROVENANCE_RT8);
        return json(route, { detail: "unknown id" }, 404);
      }
      return json(route, { detail: "not found" }, 404);
    },
  );
}

/** Walk the 6-tap barrier check for Maria: no transport, shift 7-15, no
 * childcare, has escort, cost worry, Spanish. */
async function runBarrierCheck(page: Page): Promise<void> {
  await page.getByTestId("visit-colonoscopy").click();
  await page.getByTestId("start-barriers").click();
  // transport: no
  await page.getByTestId("transport-no").click();
  await page.getByTestId("barrier-next").click();
  // work_shift: default "none" is fine
  await page.getByTestId("barrier-next").click();
  // childcare: none
  await page.getByTestId("childcare-none").click();
  await page.getByTestId("barrier-next").click();
  // escort: yes
  await page.getByTestId("escort-yes").click();
  await page.getByTestId("barrier-next").click();
  // cost: yes
  await page.getByTestId("cost-yes").click();
  await page.getByTestId("barrier-next").click();
  // language: es
  await page.getByTestId("language-es").click();
  await page.getByTestId("barrier-submit").click();
}

test("Maria gets an escort ride, never a transit slot (UP-3.4)", async ({ page }) => {
  await mockPlannerApi(page);
  await page.goto("/#/planner");
  await runBarrierCheck(page);

  // Options render; the first is the ride, and no transit-only slot appears.
  await expect(page.locator(".plan-view")).toBeVisible();
  const first = page.locator(".option").first();
  await expect(first).toHaveClass(/option-ride/);
  await expect(page.locator(".option-slot")).toHaveCount(0);
  // Recommended badge on the top option.
  await expect(first.locator(".badge")).toBeVisible();
});

test("every option shows a reason (UP-P2)", async ({ page }) => {
  await mockPlannerApi(page);
  await page.goto("/#/planner");
  await runBarrierCheck(page);
  const reasons = page.locator(".option .option-why");
  // count() does not auto-wait: let the first option render before counting.
  await expect(reasons.first()).toBeVisible();
  const count = await reasons.count();
  expect(count).toBeGreaterThan(0);
  for (let i = 0; i < count; i++) {
    expect((await reasons.nth(i).innerText()).trim().length).toBeGreaterThan(0);
  }
});

test("itinerary + phone preview render (UP-4)", async ({ page }) => {
  await mockPlannerApi(page);
  await page.goto("/#/planner");
  await runBarrierCheck(page);

  await expect(page.locator(".itinerary")).toBeVisible();
  // Out and return legs rendered.
  await expect(page.locator(".itin-cols .legs li").first()).toBeVisible();
  // Last bus home shows the clock time 18:00 (64800s).
  await expect(page.locator(".last-bus")).toContainText("18:00");
  // Phone-sized preview present.
  await expect(page.getByTestId("phone-preview")).toBeVisible();
});

test("PT-1 summary lists fields and marks blanks (UP-5)", async ({ page }) => {
  await mockPlannerApi(page);
  await page.goto("/#/planner");
  await runBarrierCheck(page);

  const summary = page.locator(".pt1-summary");
  await expect(summary).toBeVisible();
  // Known fields show their readable label (planner.pt1.fields.*), not the raw key.
  await expect(summary).toContainText("MassHealth member ID");
  // escort_name is null -> shown as "for a person to complete".
  await expect(summary.locator(".pt1-todo")).toHaveCount(1);
  await expect(summary.locator(".pt1-todo").first()).toBeVisible();
});

test("provenance drawer opens, shows source->status, closes on Esc (UP-6)", async ({
  page,
}) => {
  await mockPlannerApi(page);
  await page.goto("/#/planner");
  await runBarrierCheck(page);

  await page.locator(".chip-button").first().click();
  const drawer = page.getByRole("dialog");
  await expect(drawer).toBeVisible();
  await expect(drawer).toContainText("PVTA GTFS");
  await expect(drawer).toContainText("RT-8");
  await expect(drawer.locator(".prov-prop")).toHaveCount(2);

  // Esc closes and focus returns to the chip.
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.locator(".chip-button").first()).toBeFocused();
});

test("Spanish run has no raw i18n keys (UP-P3)", async ({ page }) => {
  await mockPlannerApi(page);
  await page.goto("/#/planner");
  // Switch to Spanish via the header language switch.
  await page.getByRole("button", { name: "ES", exact: true }).click();
  await runBarrierCheck(page);
  await expect(page.locator(".plan-view")).toBeVisible();
  // No un-resolved keys like "planner.plan.heading" leak to the DOM.
  await expect(page.locator("body")).not.toContainText(/planner\.[a-z]+\./);
});

test("planner screen + open drawer have no serious/critical a11y violations (UP-P5)", async ({
  page,
}) => {
  await mockPlannerApi(page);
  await page.goto("/#/planner");
  await runBarrierCheck(page);
  await page.locator(".chip-button").first().click();
  await expect(page.getByRole("dialog")).toBeVisible();

  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  const blocking = results.violations.filter(
    (v) => v.impact === "serious" || v.impact === "critical",
  );
  if (blocking.length > 0) {
    console.log(
      "a11y violations:\n" +
        JSON.stringify(
          blocking.map((v) => ({ id: v.id, nodes: v.nodes.map((n) => n.target) })),
          null,
          2,
        ),
    );
  }
  expect(blocking).toEqual([]);
});
