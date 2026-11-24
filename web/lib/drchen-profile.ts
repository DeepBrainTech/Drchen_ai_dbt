/**
 * Dr. Chen AI — simplified standalone UI profile.
 *
 * Dr. Chen AI's first version is a focused learning tool: tutor chat,
 * step-by-step solving, practice quizzes, study plans (Mastery Path) and
 * learning from uploaded documents. Everything else DeepTutor ships is
 * HIDDEN here, not deleted: routes, backend services, stored data and
 * module manifests are untouched, so any feature can come back by removing
 * it from the lists below.
 *
 * Set NEXT_PUBLIC_DRCHEN_SIMPLIFIED=false (e.g. in web/.env.local) to show
 * the full DeepTutor interface again without changing code.
 */
export const DRCHEN_SIMPLIFIED = process.env.NEXT_PUBLIC_DRCHEN_SIMPLIFIED !== 'false'

/** Route roots hidden from navigation and blocked by the route gate. */
export const DRCHEN_HIDDEN_ROUTES: readonly string[] = [
  // Partners and agent groups
  '/partners',
  // Calendar and task management
  '/calendar',
  '/kanban',
  // Other advanced workspace features
  '/co-writer',
  '/whisper',
  // Book generation and video watching
  '/books',
  '/learning/books',
  '/learning/watching',
  // Advanced personalization, agents, skills, MCP and CLI apps
  '/personalization',
  '/agents',
  '/memory',
  '/space/personas',
  '/space/skills',
  '/space/mcp',
  '/space/cli-apps',
]

/** Chat modes (backend capabilities) hidden from the chat mode picker. */
export const DRCHEN_HIDDEN_CAPABILITIES: readonly string[] = [
  'deep_research',
  'math_animator',
  'video_lesson',
]

function pathOf(href: string): string {
  return href.split(/[?#]/, 1)[0]
}

/** True when this link or pathname belongs to a feature Dr. Chen AI hides. */
export function isDrChenHiddenRoute(href: string, enabled = DRCHEN_SIMPLIFIED): boolean {
  if (!enabled) return false
  const path = pathOf(href)
  return DRCHEN_HIDDEN_ROUTES.some(root => path === root || path.startsWith(`${root}/`))
}

/** True when this chat capability is hidden in Dr. Chen AI. */
export function isDrChenHiddenCapability(value: string, enabled = DRCHEN_SIMPLIFIED): boolean {
  return enabled && DRCHEN_HIDDEN_CAPABILITIES.includes(value)
}
