import { Activity, Archive, BarChart3, Bot, Settings2, Mic, UserRound } from 'lucide-react'
import {
  SETTINGS_CATEGORIES,
  isSettingsCategoryVisible,
  isSettingsLeafVisible,
  resolveSettingsKey,
  type Lang,
  type SettingsLeaf,
} from './settings-nav'
import type { LucideIcon } from 'lucide-react'
import type { SettingsAccess } from './settings-access'

export const SETTINGS_PAGE_GROUPS: { label: Lang; keys: string[] }[] = [
  {
    label: { en: 'Preferences', zh: 'Preferences' },
    keys: ['general', 'appearance', 'learner-profile', 'customer-voice'],
  },
  {
    label: { en: 'Learning', zh: 'Learning' },
    keys: ['progress', 'guardian'],
  },
  {
    label: { en: 'Privacy & data', zh: 'Privacy & data' },
    keys: ['account', 'archive'],
  },
  {
    label: { en: 'Support', zh: 'Support' },
    keys: ['about'],
  },
]

/**
 * Pages laid out as master–detail (a list rail beside an editor). They need the
 * width for both columns: at the shared 960px cap the editor column came out
 * around 590px, so its fields sat in one cramped stack with hundreds of unused
 * pixels beside them. Text-only preference pages stay narrow on purpose.
 */
const WIDE_SETTINGS_PAGES = new Set([
  'connections',
  'llm',
  'embedding',
  'search',
  'voice',
  'multimodal',
])

export function isWideSettingsPage(key: string): boolean {
  return WIDE_SETTINGS_PAGES.has(resolveSettingsKey(key))
}

/** Related service pages share a compact navigation row, with explicit tabs. */
export const SETTINGS_PAGE_FAMILIES: string[][] = [
  SETTINGS_CATEGORIES.find(category => category.key === 'agents')!.children!.map(leaf => leaf.key),
]

export function settingsPageFamily(key: string): string[] {
  return SETTINGS_PAGE_FAMILIES.find(family => family.includes(key)) ?? [key]
}

const extraPages: SettingsLeaf[] = [
  {
    key: 'account',
    label: { en: 'Account', zh: 'Account' },
    blurb: { en: 'Manage your account and profile', zh: 'Account preferences' },
    icon: UserRound,
    href: '/settings/account',
    tile: '',
  },
  {
    key: 'customer-voice',
    label: { en: 'Voice', zh: 'Voice' },
    blurb: { en: 'Manage spoken replies and playback preferences', zh: 'Voice preferences' },
    icon: Mic,
    href: '/settings/customer-voice',
    tile: '',
  },
  {
    key: 'progress',
    label: { en: 'Learning progress', zh: '学习进度' },
    blurb: { en: 'Reading progress and recent learning actions', zh: '阅读进度与近期学习操作' },
    icon: BarChart3,
    href: '/settings/progress',
    tile: '',
  },
  {
    key: 'data-migration',
    label: { en: 'Data migration', zh: '数据迁移' },
    blurb: { en: 'Discover, migrate and export learning data', zh: '查找、迁移和导出学习数据' },
    icon: Archive,
    href: '/settings/data-migration',
    tile: '',
  },
  {
    key: 'usage',
    label: { en: 'Usage statistics', zh: '用量统计' },
    blurb: { en: 'Model usage and conversation activity', zh: '模型用量与对话活跃情况' },
    icon: BarChart3,
    href: '/settings/usage',
    tile: '',
  },
  {
    key: 'archive',
    label: { en: 'Archived chats', zh: '已归档的聊天' },
    blurb: {
      en: 'Search, unarchive, or permanently delete archived conversations',
      zh: '搜索、取消归档或永久删除已归档的对话',
    },
    icon: Archive,
    href: '/settings/archive',
    tile: '',
  },
  {
    key: 'general',
    label: { en: 'General', zh: '常规' },
    blurb: {
      en: 'Manage your language and response preferences',
      zh: '界面语言、布局、回复语言与配置帮助',
    },
    icon: Settings2,
    href: '/settings/general',
    tile: '',
  },
  {
    key: 'status',
    label: { en: 'Runtime status', zh: '运行状态' },
    blurb: {
      en: 'Service readiness, diagnostics, and memory usage',
      zh: '服务就绪情况、诊断与内存占用',
    },
    icon: Activity,
    href: '/settings/status',
    tile: '',
  },
]

const CUSTOMER_SETTINGS_KEYS = new Set([
  'account',
  'customer-voice',
  'general',
  'appearance',
  'progress',
  'learner-profile',
  'guardian',
  'archive',
  'about',
])

export function visibleSettingsPages(access: SettingsAccess): SettingsLeaf[] {
  if (!access.resolved) return []

  return [
    ...extraPages,
    ...SETTINGS_CATEGORIES
      .filter(category => isSettingsCategoryVisible(category, access))
      .flatMap(category => category.children ?? [{ ...category, tile: '' }])
      .filter(
        leaf =>
          isSettingsLeafVisible(leaf, access) &&
          resolveSettingsKey(leaf.key) === leaf.key
      ),
  ].filter(page => CUSTOMER_SETTINGS_KEYS.has(page.key))
}

export function settingsPageLabel(key: string, fallback: Lang): Lang {
  if (key === 'archive') return { en: 'Data controls', zh: 'Data controls' }

  if (key === 'learner-profile') return { en: 'Personalization', zh: 'Personalization' }

  if (key === 'about') return { en: 'Help & About', zh: 'Help & About' }

  if (key === 'llm') return { en: 'Language models', zh: '语言模型' }
  if (key === 'agent-claude-code') return { en: 'Partners & agents', zh: '伙伴与智能体' }
  if (key === 'starters') return { en: 'Conversation', zh: '对话' }
  if (key === 'connections') return { en: 'Providers', zh: '提供方' }
  if (key === 'knowledge') return { en: 'Knowledge & documents', zh: '知识与文档' }
  return fallback
}

/**
 * Icon for a page as the navigation shows it.
 *
 * The counterpart to ``settingsPageLabel``: where a row stands for a whole
 * family it is titled for the family, so it cannot also wear one member's
 * brand mark. "Partners & agents" carried Claude Code's orange glyph — the one
 * saturated mark in a column of neutral line icons, and wrong about the page,
 * which configures every partner. Search results address the leaf itself and
 * keep the vendor glyph, matching the label they show.
 */
export function settingsPageIcon(key: string, fallback: LucideIcon): LucideIcon {
  if (key === 'agent-claude-code') return Bot
  return fallback
}

/** Old links sometimes placed ?profile after the fragment. Preserve it too. */
export function legacySettingsDestination(hash: string, search: string): string {
  const [rawKey, hashQuery = ''] = hash.replace(/^#/, '').split('?')
  let key = 'general'
  try {
    key = resolveSettingsKey(decodeURIComponent(rawKey || 'general'))
  } catch {
    /* malformed old URL */
  }
  const known = new Set([
    ...extraPages.map(page => page.key),
    ...SETTINGS_CATEGORIES.flatMap(
      category => category.children?.map(leaf => leaf.key) ?? [category.key]
    ),
  ])
  if (!known.has(key)) key = 'general'
  const query = new URLSearchParams(search)
  new URLSearchParams(hashQuery).forEach((value, name) => query.set(name, value))
  return `/settings/${key}${query.size ? `?${query}` : ''}`
}
