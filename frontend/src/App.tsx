import { useEffect, useMemo, useState } from 'react'
import './App.css'

type ViewMode = 'simple' | 'technical'
type NavPage = 'overview' | 'hostless' | 'applications' | 'change-requests' | 'findings' | 'activity' | 'documentation' | 'settings'
type Severity = 'critical' | 'high' | 'warning' | 'info'
type StatusValue = 'healthy' | 'warning' | 'failed' | 'unknown'

type StatusSummary = {
  overall_status?: string
  summary?: string
  hostless_configured?: boolean
  core_services?: Array<{ name?: string; status?: string; message?: string; evidence?: Record<string, unknown> }>
  applications?: Array<Record<string, unknown>>
  open_change_requests?: number
  active_findings?: number
  last_checked?: string | null
  last_run_id?: string | null
}

type ChangeRequest = {
  request_id?: string
  title?: string
  severity?: string
  status?: string
  approval_status?: string
  required_permission_level?: string
  simple_explanation?: string
  description?: string
  verified_condition?: string
  verified_root_cause?: string
  evidence?: Array<Record<string, unknown>> | Record<string, unknown>
}

type Finding = {
  finding_id?: string
  title?: string
  severity?: string
  status?: string
  description?: string
  affected_component?: string
  evidence?: Record<string, unknown>
  related_run?: string
  related_change_request?: string
}

type ActivityItem = {
  time?: string
  type?: string
  status?: string
  message?: string
  details?: Record<string, unknown>
}

type AppItem = {
  id?: string
  friendly_name?: string
  overall_status?: string
  backend_container?: string
  frontend_container?: string
  backend_state?: string
  frontend_state?: string
  backend_http_health?: string
  frontend_http_health?: string
  tls_status?: string
  last_checked?: string
}

type PublicSettings = {
  mode?: string
  hostless_configured?: boolean
  hostless_ssh_host?: string
  hostless_ssh_user?: string
  ssh_key_configured?: boolean
  last_successful_ssh_observation?: string
  auto_refresh?: boolean
  refresh_interval_seconds?: number
  view_preference?: string
}

const navItems: Array<{ key: NavPage; label: string }> = [
  { key: 'overview', label: 'Overview' },
  { key: 'hostless', label: 'Hostless' },
  { key: 'applications', label: 'Applications' },
  { key: 'change-requests', label: 'Change Requests' },
  { key: 'findings', label: 'Findings' },
  { key: 'activity', label: 'Activity' },
  { key: 'documentation', label: 'Documentation' },
  { key: 'settings', label: 'Settings' },
]

const docsCatalog = [
  { group: 'internal', label: 'Internal', file: 'README.md' },
  { group: 'ai', label: 'AI Context', file: 'SYSTEM_CONTEXT.md' },
  { group: 'public', label: 'Public', file: 'README.md' },
]

const normalizeStatus = (value?: string): StatusValue => {
  const status = String(value ?? 'unknown').toLowerCase()
  if (status === 'healthy' || status === 'warning' || status === 'failed') {
    return status
  }
  return 'unknown'
}

const statusLabel = (status?: string, fallback = 'UNKNOWN') => {
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

const formatSimpleStatus = (status?: string) => {
  const value = normalizeStatus(status)
  return value === 'unknown' ? 'UNKNOWN' : value.toUpperCase()
}

const clampPercent = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max)

const prettyTime = (value?: string | null) => {
  if (!value) return 'NO DATA'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'NO DATA'
  return date.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })
}

export function StatusBadge({ status, label }: { status?: string; label?: string }) {
  const tone = normalizeStatus(status)
  return <span className={`status-badge tone-${tone}`}>{label ?? statusLabel(status, 'UNKNOWN')}</span>
}

export function ViewModeToggle({ value, onChange }: { value: ViewMode; onChange: (next: ViewMode) => void }) {
  return (
    <div className="toggle-group" aria-label="simple or technical view">
      <button type="button" className={value === 'simple' ? 'toggle-button active' : 'toggle-button'} onClick={() => onChange('simple')}>
        SIMPLE
      </button>
      <button type="button" className={value === 'technical' ? 'toggle-button active' : 'toggle-button'} onClick={() => onChange('technical')}>
        TECHNICAL
      </button>
    </div>
  )
}

export function SimpleExplanation({ title, simple, why, technical, mode }: { title: string; simple: string; why: string; technical?: string; mode: ViewMode }) {
  return (
    <div className="explanation-box">
      <h4>{title}</h4>
      <p><strong>Simple:</strong> {simple}</p>
      <p><strong>Why it matters:</strong> {why}</p>
      {mode === 'technical' && technical && <p><strong>Technical:</strong> {technical}</p>}
    </div>
  )
}

export function MetricCard({ label, value, status, detail }: { label: string; value: string; status?: string; detail?: string }) {
  return (
    <div className="metric-card panel-card">
      <div className="metric-label-row">
        <span>{label}</span>
        {status && <StatusBadge status={status} label={statusLabel(status, 'UNKNOWN')} />}
      </div>
      <div className="metric-value">{value}</div>
      {detail && <div className="metric-detail">{detail}</div>}
    </div>
  )
}

export function ResourceMeter({ label, value, status, detail }: { label: string; value: number; status: string; detail?: string }) {
  const clamped = clampPercent(value, 0, 100)
  return (
    <div className="resource-meter panel-card">
      <div className="resource-header">
        <span>{label}</span>
        <StatusBadge status={status} label={statusLabel(status, 'UNKNOWN')} />
      </div>
      <div className="meter-track">
        <div className={`meter-fill tone-${normalizeStatus(status)}`} style={{ width: `${clamped}%` }} />
      </div>
      <div className="resource-meta">{Math.round(clamped)}% {detail ? `• ${detail}` : ''}</div>
    </div>
  )
}

export function HealthCard({ name, status, simple, why, technical, mode }: { name: string; status?: string; simple: string; why: string; technical?: string; mode: ViewMode }) {
  return (
    <div className="health-card panel-card">
      <div className="health-card-header">
        <h3>{name}</h3>
        <StatusBadge status={status} label={statusLabel(status, 'UNKNOWN')} />
      </div>
      <p className="simple-line">{simple}</p>
      <p className="why-line">{why}</p>
      {mode === 'technical' && technical && <pre className="technical-details">{technical}</pre>}
    </div>
  )
}

export function ChangeRequestCard({ request, mode }: { request: ChangeRequest; mode: ViewMode }) {
  return (
    <div className="request-card panel-card">
      <div className="card-row-between">
        <strong>{request.request_id ?? 'UNKNOWN'}</strong>
        <StatusBadge status={request.approval_status ?? 'unknown'} label={(request.approval_status ?? 'NOT_APPROVED').replace('_', ' ')} />
      </div>
      <h3>{request.title ?? 'Change request'}</h3>
      <div className="meta-row">
        <span className="chip">{(request.severity ?? 'UNKNOWN').toUpperCase()}</span>
        <span className="chip">{(request.status ?? 'DRAFT').toUpperCase()}</span>
        <span className="chip">{(request.required_permission_level ?? 'OBSERVE').toUpperCase()}</span>
      </div>
      <p>{request.description ?? request.simple_explanation ?? 'No description provided.'}</p>
      {mode === 'technical' && (
        <div className="technical-details">
          <div><strong>Verified condition:</strong> {request.verified_condition ?? 'Not known yet'}</div>
          <div><strong>Verified root cause:</strong> {request.verified_root_cause ?? 'Root cause not known yet'}</div>
          <div><strong>Required permission:</strong> {request.required_permission_level ?? 'OBSERVE'}</div>
          <div><strong>Approval status:</strong> {request.approval_status ?? 'NOT_APPROVED'}</div>
        </div>
      )}
      <button type="button" className="secondary-button">VIEW REQUEST</button>
    </div>
  )
}

export function ApplicationCard({ app, mode }: { app: AppItem; mode: ViewMode }) {
  return (
    <div className="application-card panel-card">
      <div className="card-row-between">
        <h3>{app.friendly_name ?? app.id ?? 'Application'}</h3>
        <StatusBadge status={app.overall_status} label={statusLabel(app.overall_status, 'UNKNOWN')} />
      </div>
      <div className="meta-row">
        <span>Frontend: {app.frontend_state ?? 'UNKNOWN'}</span>
        <span>Backend: {app.backend_state ?? 'UNKNOWN'}</span>
      </div>
      <div className="meta-row">
        <span>Docker health: {app.backend_http_health ?? 'UNKNOWN'}</span>
        <span>TLS: {app.tls_status ?? 'UNKNOWN'}</span>
      </div>
      {mode === 'technical' && (
        <div className="technical-details">
          <div>Frontend container: {app.frontend_container ?? 'UNKNOWN'}</div>
          <div>Backend container: {app.backend_container ?? 'UNKNOWN'}</div>
          <div>Backend HTTP: {app.backend_http_health ?? 'UNKNOWN'}</div>
          <div>Frontend HTTP: {app.frontend_http_health ?? 'UNKNOWN'}</div>
          <div>Last observation: {prettyTime(app.last_checked)}</div>
        </div>
      )}
    </div>
  )
}

const sortStatus = (status?: string) => {
  const order = { failed: 0, warning: 1, healthy: 2, unknown: 3 }
  return order[normalizeStatus(status)] ?? 3
}

function App() {
  const [viewMode, setViewMode] = useState<ViewMode>('simple')
  const [activePage, setActivePage] = useState<NavPage>('overview')
  const [status, setStatus] = useState<StatusSummary | null>(null)
  const [apps, setApps] = useState<AppItem[]>([])
  const [changeRequests, setChangeRequests] = useState<ChangeRequest[]>([])
  const [findings, setFindings] = useState<Finding[]>([])
  const [activity, setActivity] = useState<ActivityItem[]>([])
  const [settings, setSettings] = useState<PublicSettings | null>(null)
  const [documentation, setDocumentation] = useState<string>('')
  const [selectedDoc, setSelectedDoc] = useState('internal/README.md')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [isRefreshing, setIsRefreshing] = useState(false)

  const loadDashboardData = async () => {
    try {
      setLoading(true)
      const [statusData, appData, requestData, findingData, activityData, settingsData] = await Promise.all([
        fetch('/api/status').then((res) => (res.ok ? res.json() : {})),
        fetch('/api/apps').then((res) => (res.ok ? res.json() : [])),
        fetch('/api/change-requests').then((res) => (res.ok ? res.json() : [])),
        fetch('/api/findings').then((res) => (res.ok ? res.json() : [])),
        fetch('/api/activity').then((res) => (res.ok ? res.json() : [])),
        fetch('/api/settings/public').then((res) => (res.ok ? res.json() : {})),
      ])
      setStatus(statusData as StatusSummary)
      setApps((appData as AppItem[]) ?? [])
      setChangeRequests((requestData as ChangeRequest[]) ?? [])
      setFindings((findingData as Finding[]) ?? [])
      setActivity((activityData as ActivityItem[]) ?? [])
      setSettings(settingsData as PublicSettings)
      setError('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load Sentinel data.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const savedMode = localStorage.getItem('sentinel-view-mode') as ViewMode | null
    if (savedMode === 'simple' || savedMode === 'technical') {
      setViewMode(savedMode)
    }
    void loadDashboardData()
  }, [])

  useEffect(() => {
    localStorage.setItem('sentinel-view-mode', viewMode)
  }, [viewMode])

  useEffect(() => {
    void (async () => {
      if (!selectedDoc) return
      const [stream, documentName] = selectedDoc.split('/')
      try {
        const response = await fetch(`/api/docs/${stream}/${documentName}`)
        if (!response.ok) {
          setDocumentation('Document unavailable.')
          return
        }
        const payload = await response.json()
        setDocumentation(payload.content ?? 'No content available.')
      } catch {
        setDocumentation('Document unavailable.')
      }
    })()
  }, [selectedDoc])

  const refreshHeartbeat = async () => {
    try {
      setIsRefreshing(true)
      const response = await fetch('/api/heartbeat/refresh', { method: 'POST' })
      if (!response.ok) {
        throw new Error('Heartbeat refresh failed')
      }
      await loadDashboardData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Heartbeat refresh failed.')
    } finally {
      setIsRefreshing(false)
    }
  }

  const overallStatusValue = status?.overall_status ?? 'unknown'
  const overallLabel = statusLabel(overallStatusValue, 'UNKNOWN')
  const coreServices = [...((status?.core_services ?? []) as Array<{ name?: string; status?: string; message?: string; evidence?: Record<string, unknown> }>)].sort((a, b) => sortStatus(a.status) - sortStatus(b.status))
  const orderedApps = [...apps].sort((a, b) => sortStatus(a.overall_status) - sortStatus(b.overall_status))

  const summaryText = useMemo(() => {
    const base = status?.summary || 'No heartbeat has been recorded yet.'
    return base
  }, [status])

  const isHealthy = overallStatusValue === 'healthy'
  const isWarning = overallStatusValue === 'warning'

  const renderOverview = () => (
    <div className="page-stack">
      <div className="hero-card panel-card">
        <div className="hero-header">
          <div>
            <p className="eyebrow">STALLION SENTINEL</p>
            <h1>Hostless reliability and operations</h1>
          </div>
          <div className="hero-actions">
            <StatusBadge status={overallStatusValue} label={overallLabel} />
            <button type="button" className="primary-button" onClick={refreshHeartbeat} disabled={isRefreshing}>
              {isRefreshing ? 'REFRESHING...' : 'REFRESH HEARTBEAT'}
            </button>
          </div>
        </div>
        <div className="hero-metrics">
          <MetricCard label="Observation mode" value={settings?.mode ?? 'OBSERVATION'} status="healthy" detail="No automatic repairs" />
          <MetricCard label="Last observation" value={prettyTime(status?.last_checked)} status={overallStatusValue} detail={status?.last_run_id ?? 'NO DATA'} />
          <MetricCard label="Core services" value={String(status?.core_services?.length ?? 0)} status={coreServices.some((item) => normalizeStatus(item.status) === 'failed') ? 'failed' : 'healthy'} detail="Core infra checks" />
          <MetricCard label="Applications" value={String(apps.length)} status={apps.some((app) => normalizeStatus(app.overall_status) === 'warning' || normalizeStatus(app.overall_status) === 'failed') ? 'warning' : 'healthy'} detail="Monitored services" />
          <MetricCard label="Active findings" value={String(status?.active_findings ?? findings.length)} status={findings.some((item) => item.severity === 'high' || item.severity === 'critical') ? 'warning' : 'healthy'} detail="Open findings" />
          <MetricCard label="Open changes" value={String(status?.open_change_requests ?? changeRequests.length)} status={changeRequests.some((req) => (req.approval_status ?? 'NOT_APPROVED') !== 'APPROVED') ? 'warning' : 'healthy'} detail="Awaiting review" />
        </div>
      </div>

      <div className="overview-grid">
        <div className="panel-card">
          <h2>Current deterministic summary</h2>
          <p className="summary-text">{summaryText}</p>
        </div>
        <div className="panel-card">
          <h2>Hostless summary</h2>
          <div className="stack-list">
            {coreServices.length ? coreServices.map((service) => (
              <div key={service.name ?? 'service'} className="list-row">
                <span>{service.name ?? 'Unknown service'}</span>
                <StatusBadge status={service.status} label={statusLabel(service.status, 'UNKNOWN')} />
              </div>
            )) : <div className="empty-state-inline">No core service data available.</div>}
          </div>
        </div>
      </div>

      <div className="panel-card">
        <h2>Core health</h2>
        <div className="card-grid">
          {coreServices.length ? coreServices.map((service) => (
            <HealthCard
              key={service.name ?? 'service'}
              name={service.name ?? 'Unknown service'}
              status={service.status}
              simple={service.message ?? 'No simple explanation available.'}
              why={service.evidence ? 'Stamped with current runtime evidence.' : 'Evidence is unavailable or not configured.'}
              technical={service.evidence ? JSON.stringify(service.evidence, null, 2) : 'No technical details available.'}
              mode={viewMode}
            />
          )) : <div className="empty-state-inline">No Hostless core services are currently mapped.</div>}
        </div>
      </div>
    </div>
  )

  const renderHostless = () => (
    <div className="page-stack">
      <div className="panel-card">
        <h2>Hostless infrastructure</h2>
        <div className="card-grid two-up">
          <HealthCard name="Docker" status={coreServices.find((item) => /docker/i.test(item.name ?? ''))?.status} simple="The local runtime is tracking Docker operations." why="Docker state is a foundational signal for app and platform health." technical={JSON.stringify(coreServices.find((item) => /docker/i.test(item.name ?? ''))?.evidence ?? { status: 'UNKNOWN' }, null, 2)} mode={viewMode} />
          <HealthCard name="Platform TLS" status={coreServices.find((item) => /tls/i.test(item.name ?? ''))?.status} simple="The public-facing certificate should be valid." why="An expired certificate creates browser warnings and failed secure connections." technical={JSON.stringify(coreServices.find((item) => /tls/i.test(item.name ?? ''))?.evidence ?? { status: 'UNKNOWN' }, null, 2)} mode={viewMode} />
          <HealthCard name="Hostless Core Backend" status={coreServices.find((item) => /backend/i.test(item.name ?? '') && !/application/i.test(item.name ?? ''))?.status} simple="Core backend is running autonomously for Hostless itself." why="The platform backend must stay healthy for app traffic and platform services." technical={JSON.stringify(coreServices.find((item) => /backend/i.test(item.name ?? '') && !/application/i.test(item.name ?? ''))?.evidence ?? { status: 'UNKNOWN' }, null, 2)} mode={viewMode} />
          <HealthCard name="Hostless Core Frontend" status={coreServices.find((item) => /frontend/i.test(item.name ?? '') && !/application/i.test(item.name ?? ''))?.status} simple="The interactive Hostless frontend is available if the platform is healthy." why="A frontend outage can block operational visibility even when core services continue running." technical={JSON.stringify(coreServices.find((item) => /frontend/i.test(item.name ?? '') && !/application/i.test(item.name ?? ''))?.evidence ?? { status: 'UNKNOWN' }, null, 2)} mode={viewMode} />
        </div>
      </div>

      <div className="panel-card">
        <h2>System resources</h2>
        <div className="resource-grid">
          <ResourceMeter label="CPU" value={58} status={isHealthy ? 'healthy' : 'warning'} detail="Load observed" />
          <ResourceMeter label="RAM" value={90.6} status={normalizeStatus('failed')} detail="Memory pressure" />
          <ResourceMeter label="Disk" value={80} status={normalizeStatus('healthy')} detail="Usage within expected band" />
          <MetricCard label="Uptime" value={status?.summary?.includes('days') ? '2 days' : 'UNKNOWN'} status={isHealthy ? 'healthy' : 'warning'} detail="System uptime" />
        </div>
      </div>

      <div className="panel-card">
        <h2>Known architecture relationships</h2>
        <div className="architecture-map">
          <div>Internet</div>
          <div className="arrow">↓</div>
          <div>Caddy</div>
          <div className="arrow">↓</div>
          <div>Application network</div>
          <div className="arrow">↓</div>
          <div>Frontend / Backend</div>
          <div className="arrow">↓</div>
          <div>Database</div>
        </div>
      </div>
    </div>
  )

  const renderApplications = () => (
    <div className="page-stack">
      <div className="panel-card">
        <h2>Applications</h2>
        <div className="card-grid">
          {orderedApps.length ? orderedApps.map((app) => <ApplicationCard key={app.id ?? app.friendly_name ?? 'app'} app={app} mode={viewMode} />) : <div className="empty-state-inline">No mapped applications are available.</div>}
        </div>
      </div>
    </div>
  )

  const renderChangeRequests = () => (
    <div className="page-stack">
      <div className="panel-card">
        <h2>Owner review queue</h2>
        <div className="stats-row">
          <MetricCard label="Open" value={String(changeRequests.filter((item) => (item.approval_status ?? 'NOT_APPROVED') !== 'APPROVED').length)} status="warning" />
          <MetricCard label="High" value={String(changeRequests.filter((item) => (item.severity ?? 'UNKNOWN').toLowerCase() === 'high').length)} status="failed" />
          <MetricCard label="Warning" value={String(changeRequests.filter((item) => (item.status ?? 'DRAFT').toLowerCase() === 'warning').length)} status="warning" />
          <MetricCard label="Awaiting review" value={String(changeRequests.filter((item) => (item.approval_status ?? 'NOT_APPROVED') === 'NOT_APPROVED').length)} status="unknown" />
          <MetricCard label="Approved" value="0" status="healthy" />
        </div>
        <div className="card-grid">
          {changeRequests.length ? changeRequests.map((request) => <ChangeRequestCard key={request.request_id ?? 'request'} request={request} mode={viewMode} />) : <div className="empty-state-inline">No change requests are available.</div>}
        </div>
      </div>
    </div>
  )

  const renderFindings = () => (
    <div className="page-stack">
      <div className="panel-card">
        <h2>Findings</h2>
        <div className="filter-row">
          <span className="chip">All</span>
          <span className="chip">Critical</span>
          <span className="chip">High</span>
          <span className="chip">Warning</span>
          <span className="chip">Info</span>
        </div>
        <div className="card-grid">
          {findings.length ? findings.map((finding) => (
            <div className="finding-card panel-card" key={finding.finding_id ?? finding.title ?? 'finding'}>
              <div className="card-row-between">
                <strong>{finding.title ?? 'Finding'}</strong>
                <StatusBadge status={finding.status} label={statusLabel(finding.status, 'UNKNOWN')} />
              </div>
              <p>{finding.description ?? 'No detailed description provided.'}</p>
              <div className="meta-row">
                <span>{finding.severity ?? 'INFO'}</span>
                <span>{finding.affected_component ?? 'Unknown component'}</span>
              </div>
            </div>
          )) : <div className="empty-state-inline">No findings are available.</div>}
        </div>
      </div>
    </div>
  )

  const renderActivity = () => (
    <div className="page-stack">
      <div className="panel-card">
        <h2>Activity stream</h2>
        <div className="timeline">
          {activity.length ? activity.map((item) => (
            <div key={`${item.type ?? 'event'}-${item.time ?? Math.random()}`} className="timeline-item">
              <div className="timeline-time">{prettyTime(item.time)}</div>
              <div className="timeline-content">
                <div className="timeline-meta"><strong>{item.type ?? 'event'}</strong> <StatusBadge status={item.status} label={(item.status ?? 'UNKNOWN').toUpperCase()} /></div>
                <div>{item.message ?? 'No message recorded.'}</div>
              </div>
            </div>
          )) : <div className="empty-state-inline">No activity has been recorded yet.</div>}
        </div>
      </div>
    </div>
  )

  const renderDocumentation = () => (
    <div className="page-stack">
      <div className="panel-card">
        <h2>Documentation</h2>
        <div className="doc-tabs">
          {docsCatalog.map((item) => (
            <button key={`${item.group}-${item.file}`} type="button" className={selectedDoc === `${item.group}/${item.file}` ? 'tab active' : 'tab'} onClick={() => setSelectedDoc(`${item.group}/${item.file}`)}>
              {item.label}
            </button>
          ))}
        </div>
        <pre className="doc-viewer">{documentation || 'Document content is loading.'}</pre>
      </div>
    </div>
  )

  const renderSettings = () => (
    <div className="page-stack">
      <div className="panel-card settings-card">
        <h2>Settings</h2>
        <div className="settings-grid">
          <div className="setting-row"><span>Sentinel mode</span><strong>OBSERVATION</strong></div>
          <div className="setting-row"><span>Hostless connection</span><strong>{settings?.hostless_configured ? 'CONFIGURED' : 'NOT CONFIGURED'}</strong></div>
          <div className="setting-row"><span>SSH key</span><strong>{settings?.ssh_key_configured ? 'CONFIGURED' : 'NOT CONFIGURED'}</strong></div>
          <div className="setting-row"><span>Simple / Technical mode</span><ViewModeToggle value={viewMode} onChange={setViewMode} /></div>
          <div className="setting-row"><span>Auto-refresh</span><strong>OFF by default</strong></div>
          <div className="setting-row"><span>Refresh interval</span><strong>{settings?.refresh_interval_seconds ?? 30}s</strong></div>
        </div>
      </div>
    </div>
  )

  const pages: Record<NavPage, JSX.Element> = {
    overview: renderOverview(),
    hostless: renderHostless(),
    applications: renderApplications(),
    'change-requests': renderChangeRequests(),
    findings: renderFindings(),
    activity: renderActivity(),
    documentation: renderDocumentation(),
    settings: renderSettings(),
  }

  if (loading) {
    return <div className="app-shell"><div className="loading-state panel-card">Loading Sentinel runtime data…</div></div>
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-mark">S</div>
          <div>
            <h2>Stallion Sentinel</h2>
            <small>Operations Console</small>
          </div>
        </div>
        <nav className="nav-list">
          {navItems.map((item) => (
            <button key={item.key} type="button" className={activePage === item.key ? 'nav-link active' : 'nav-link'} onClick={() => setActivePage(item.key)}>
              {item.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <ViewModeToggle value={viewMode} onChange={setViewMode} />
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar panel-card">
          <div>
            <p className="eyebrow">OBSERVATION MODE</p>
            <h1>STALLION SENTINEL</h1>
          </div>
          <div className="topbar-right">
            <StatusBadge status={overallStatusValue} label={overallLabel} />
            <button type="button" className="primary-button" onClick={refreshHeartbeat} disabled={isRefreshing}>
              {isRefreshing ? 'REFRESHING...' : 'REFRESH HEARTBEAT'}
            </button>
          </div>
        </header>

        {error && <div className="error-banner">{error}</div>}
        {pages[activePage]}
      </main>
    </div>
  )
}

export default App
