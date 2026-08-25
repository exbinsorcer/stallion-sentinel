import type { StatusValue } from './types'

export const normalizeStatus = (value?: string): StatusValue => {
  const status = String(value ?? 'unknown').toLowerCase()
  if (status === 'healthy' || status === 'warning' || status === 'failed') {
    return status
  }
  return 'unknown'
}

export const statusLabel = (status?: string, fallback = 'UNKNOWN') => {
  const value = normalizeStatus(status)
  switch (value) {
    case 'healthy':
      return 'HEALTHY'
    case 'warning':
      return 'WARNING'
    case 'failed':
      return 'FAILED'
    default:
      return fallback
  }
}

export const clampPercent = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max)

export const prettyTime = (value?: string | null) => {
  if (!value) return 'NO DATA'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'NO DATA'
  return date.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })
}

export const sortStatus = (status?: string) => {
  const order: Record<StatusValue, number> = { failed: 0, warning: 1, healthy: 2, unknown: 3 }
  return order[normalizeStatus(status)] ?? 3
}

export const humanize = (value?: string | null, fallback = 'UNKNOWN') => {
  if (!value) return fallback
  return String(value).replace(/_/g, ' ').toUpperCase()
}

export const DOCS_CATALOG: Record<'internal' | 'ai' | 'public', string[]> = {
  internal: ['README.md', 'OPERATIONS_CONSOLE.md', 'CHANGE_REQUESTS.md', 'CHANGELOG.md', 'FINDINGS.md', 'INCIDENTS.md', 'COMPATIBILITY.md'],
  ai: ['SYSTEM_CONTEXT.md', 'ACTIVE_ISSUES.md', 'RESOLVED_ISSUES.md', 'ARCHITECTURE.md', 'CHANGE_EXECUTOR_CONTRACT.md', 'TROUBLESHOOTING_HISTORY.md'],
  public: ['README.md', 'CAPABILITIES.md', 'SUPPORTED_APPS.md', 'KNOWN_ISSUES.md', 'ROADMAP.md'],
}

/**
 * Deterministic, static copy only — no generative text, no invented causes.
 * These maps describe fixed backend enums (PermissionLevel, ChangeRequestCategory)
 * and are identical for every request in a given category/permission bucket.
 */
export const PERMISSION_COPY: Record<string, { label: string; description: string }> = {
  OBSERVE: { label: 'OBSERVE', description: 'Read-only access.' },
  PATCH_PROPOSAL: { label: 'PATCH PROPOSAL', description: 'A tool may suggest a change but cannot apply it.' },
  TEST_BRANCH: {
    label: 'TEST BRANCH',
    description: 'A coding tool may make and test a change in a separate branch but cannot deploy it.',
  },
  PREPARE_RELEASE: {
    label: 'PREPARE RELEASE',
    description: 'A tool may prepare a change for release but cannot put it live.',
  },
  PRODUCTION_CHANGE: {
    label: 'PRODUCTION CHANGE',
    description: 'A live system change would be required and owner approval is necessary.',
  },
}

export const permissionCopy = (level?: string) =>
  PERMISSION_COPY[String(level ?? 'OBSERVE').toUpperCase()] ?? {
    label: String(level ?? 'OBSERVE').toUpperCase(),
    description: 'Permission scope not recognized.',
  }

export const CATEGORY_COPY: Record<string, { simple: string; why: string }> = {
  CODE_CHANGE: {
    simple: 'Something in the running software needs a code-level fix.',
    why: 'Left unresolved, this can cause repeated false alarms or hidden failures.',
  },
  INFRASTRUCTURE_CHANGE: {
    simple: 'Something in the underlying server or network setup needs review.',
    why: 'Infrastructure issues can affect every application hosted on Hostless.',
  },
  CONFIGURATION_CHANGE: {
    simple: 'A setting or configuration value needs to be reviewed.',
    why: 'Misconfiguration can cause features to behave unpredictably.',
  },
  OPERATIONAL_ATTENTION: {
    simple: 'This needs a person to look at it — it is not something Sentinel resolves by observing alone.',
    why: 'Some conditions require a judgment call only the owner can make.',
  },
  SECURITY_CHANGE: {
    simple: 'This affects how visitors are verified as securely connected to the site.',
    why: 'Visitors may see browser security warnings or fail to connect at all.',
  },
  CAPACITY_CHANGE: {
    simple: 'The server may not have enough room (memory, disk, etc.) for current demand.',
    why: 'Running low on capacity can slow down or crash running applications.',
  },
  DOCUMENTATION_CHANGE: {
    simple: "Sentinel's documentation needs to be updated to match reality.",
    why: 'Outdated documentation can mislead future engineering decisions.',
  },
  UNKNOWN: {
    simple: 'This issue has been detected but not yet categorized.',
    why: 'Until it is categorized, its full impact cannot be summarized simply.',
  },
}

export const categoryCopy = (category?: string) =>
  CATEGORY_COPY[String(category ?? 'UNKNOWN').toUpperCase()] ?? CATEGORY_COPY.UNKNOWN

export const GLOSSARY: Record<string, string> = {
  Docker: 'The engine that runs each application inside its own isolated container on the server.',
  Caddy: 'The traffic router that directs visitors from the internet to the correct hosted application.',
  MongoDB: 'The database engine used to store application data.',
  RAM: "The server's short-term working memory. Running low can slow down or crash running applications.",
  Disk: 'Long-term storage space on the server. Running low can prevent new data from being written.',
  'TLS Certificate': 'The credential that lets a browser confirm a site connection is secure and private.',
  Backend: 'The part of an application that processes data and business logic, out of view of visitors.',
  Frontend: 'The part of an application visitors see and interact with in a browser.',
  'Docker Health': "Docker's own automatic self-test for a container, separate from whether the container is running.",
  Network: 'The private communication channel that lets containers for the same application talk to each other.',
  Finding: 'A specific, evidenced observation Sentinel made during a heartbeat check.',
  'Change Request': 'A structured, evidence-backed proposal for a change that Sentinel cannot make itself.',
}
