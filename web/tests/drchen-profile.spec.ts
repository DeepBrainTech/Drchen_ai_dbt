import { beforeAll, expect, it, vi } from "vitest";

// vitest.config.mts runs the other suites with the profile off; switch it on
// here and load fresh copies of the modules that read it at import time.
vi.stubEnv("NEXT_PUBLIC_DRCHEN_SIMPLIFIED", "true");

let profile: typeof import("@/lib/drchen-profile");
let nav: typeof import("@/components/sidebar/nav-entries");
let sections: typeof import("@/components/sidebar/page-sections");
let surfaces: typeof import("@/components/learning/surfaces");
let groups: typeof import("@/components/space/dashboard-groups");
let presentation: typeof import("@/features/capabilities/presentation");

beforeAll(async () => {
  vi.resetModules();
  profile = await import("@/lib/drchen-profile");
  nav = await import("@/components/sidebar/nav-entries");
  sections = await import("@/components/sidebar/page-sections");
  surfaces = await import("@/components/learning/surfaces");
  groups = await import("@/components/space/dashboard-groups");
  presentation = await import("@/features/capabilities/presentation");
});

it("is on in this suite", () => {
  expect(profile.DRCHEN_SIMPLIFIED).toBe(true);
});

it("hides feature roots and their detail pages, ignoring query strings", () => {
  expect(profile.isDrChenHiddenRoute("/partners")).toBe(true);
  expect(profile.isDrChenHiddenRoute("/partners/abc?session=1")).toBe(true);
  expect(profile.isDrChenHiddenRoute("/learning/books/123")).toBe(true);
  expect(profile.isDrChenHiddenRoute("/space/mcp")).toBe(true);
});

it("keeps the Dr. Chen AI core features visible", () => {
  for (const href of [
    "/chat",
    "/learning",
    "/learning/practice",
    "/learning/mastery",
    "/learning/reading",
    "/knowledge-bases",
    "/space",
    "/settings",
  ]) {
    expect(profile.isDrChenHiddenRoute(href)).toBe(false);
  }
  // A prefix match must stop at a path segment.
  expect(profile.isDrChenHiddenRoute("/memoryless")).toBe(false);
});

it("can be switched off to restore the full DeepTutor interface", () => {
  expect(profile.isDrChenHiddenRoute("/partners", false)).toBe(false);
  expect(profile.isDrChenHiddenCapability("deep_research", false)).toBe(false);
});

it("removes hidden features from every navigation source", () => {
  for (const href of profile.DRCHEN_HIDDEN_ROUTES) {
    expect(nav.navVisibleUnderPolicy(href, null)).toBe(false);
  }
  expect(nav.navVisibleUnderPolicy("/settings", null)).toBe(true);
  expect(nav.PRIMARY_NAV_HREFS.filter((href) => nav.navVisibleUnderPolicy(href, null))).toEqual([
    "/chat",
    "/learning",
    "/space",
  ]);

  const shelfHrefs = groups
    .visibleGroups([...groups.DASHBOARD_GROUPS, ...groups.PERSONALIZATION_GROUPS], () => true)
    .flatMap((group) => group.items.map((item) => item.href));
  expect(shelfHrefs.some((href) => profile.isDrChenHiddenRoute(href))).toBe(false);
  expect(shelfHrefs).toContain("/knowledge-bases");

  const pageHrefs = sections
    .pageSections({ t: (key) => key, zh: false, allowedSurfaces: null, isAvailable: () => true })
    .flatMap((section) => section.pages.map((page) => page.href));
  expect(pageHrefs.some((href) => profile.isDrChenHiddenRoute(href))).toBe(false);
  expect(pageHrefs).toContain("/chat");

  expect(surfaces.VISIBLE_LEARNING_SURFACES.map((surface) => surface.kind)).not.toContain("books");
});

it("hides research, animation and video lesson modes from the chat picker", () => {
  const shown = presentation
    .visibleCapabilityPresentations(
      ["", "deep_solve", "deep_question", "deep_research", "math_animator", "video_lesson"].map(
        (value) => ({ value }) as never,
      ),
    )
    .map((capability) => capability.value);
  expect(shown).toEqual(["", "deep_solve", "deep_question"]);
});
