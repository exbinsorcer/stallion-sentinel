import { Fragment, useEffect, useMemo, useState } from 'react'
import './design/tokens.css'
import './App.css'
import {
  StatusBadge,
  StatusMark,
  ViewModeToggle,
  MachinePanel,
  SectionLabel,
  MetricBlock,
  ResourceMeter,
  DataRow,
  PermissionTag,
  EvidenceBlock,
  EmptyState,
  ErrorState,
  LoadingState,
  HeartbeatWave,
  SystemNode,
  Connector,
  ExplainPanel,
  MachineTable,
  InfoTip,
} from './components/Machine'

export { StatusBadge, ViewModeToggle, ResourceMeter } from './components/Machine'
import type { ActivityItem, AppItem, ChangeRequest, Finding, NavPage, PublicSettings, StatusSummary, ViewMode } from './lib/types'
import {
  categoryCopy,
  DOCS_CATALOG,
  humanize,
  permissionCopy,
  prettyTime,
  sortStatus,
  statusLabel,
} from './lib/format'

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

const SEVERITY_RANK: Record<string, number> = { critical: 0, high: 1, medium: 2, warning: 2, low: 3, info: 3 }
const severityRank = (severity?: string) => SEVERITY_RANK[String(severity ?? '').toLowerCase()] ?? 4

type CheckRecord = { name?: string; status?: string; message?: string; evidence?: Record<string, unknown> }

const findCheck = (checks: CheckRecord[], matcher: RegExp) => checks.find((item) => matcher.test(item.name ?? ''))

const SYSTEM_MATRIX: Array<{ label: string; match: RegExp; simple: string; why: string; glossaryTerm: string }> = [
  {
    label: 'DOCKER',
    match: /^docker engine$/i,
    simple: 'Runs each hosted application inside its own isolated container.',
    why: 'If Docker is unreachable, Sentinel cannot verify any container state.',
    glossaryTerm: 'Docker',
  },
  {
    label: 'CORE BACKEND',
    match: /^hostless core backend$/i,
    simple: 'The Hostless platform backend that powers the operator dashboard and APIs.',
    why: 'If this is down, the Hostless platform itself may be unusable.',
    glossaryTerm: 'Backend',
  },
  {
    label: 'CORE FRONTEND',
    match: /^hostless core frontend$/i,
    simple: 'The interactive Hostless operator dashboard.',
    why: 'A frontend outage can block operational visibility even if other services keep running.',
    glossaryTerm: 'Frontend',
  },
  {
    label: 'MONGODB',
    match: /^mongodb$/i,
    simple: 'Stores platform and application data.',
    why: 'Without it, applications relying on the database cannot read or write data.',
    glossaryTerm: 'MongoDB',
  },
  {
    label: 'CADDY',
    match: /^caddy$/i,
    simple: 'Routes visitors to hosted applications.',
    why: 'Without it, sites cannot receive traffic.',
    glossaryTerm: 'Caddy',
  },
  {
    label: 'PLATFORM TLS',
    match: /^hostless platform tls$/i,
    simple: 'Secures the main Hostless domain for visitors.',
    why: 'An invalid certificate causes browser security warnings for every visitor.',
    glossaryTerm: 'TLS Certificate',
  },
]

export function ChangeRequestCard({
  request,
  mode,
  onView,
}: {
  request: ChangeRequest
  mode: ViewMode
  onView?: (id: string) => void
}) {
  return (
    <div className="sen-card">
      <div className="sen-card-row">
        <span className="sen-tech-value">{request.request_id ?? 'UNKNOWN'}</span>
        <StatusBadge status={request.approval_status ?? 'unknown'} label={humanize(request.approval_status, 'NOT APPROVED')} />
      </div>
      <h3 className="sen-card-title">{request.title ?? 'Change request'}</h3>
      <div className="sen-chip-row">
        <span className="sen-chip">{humanize(request.severity)}</span>
        <span className="sen-chip">{humanize(request.status, 'DRAFT')}</span>
        <PermissionTag level={request.required_permission_level} />
      </div>
      <p className="sen-card-text">{request.description ?? request.simple_explanation ?? 'No description provided.'}</p>
      {mode === 'technical' && (
        <div className="sen-card-tech">
          <DataRow label="Verified condition" value={request.verified_condition ?? 'NOT KNOWN YET'} mono={false} />
          <DataRow label="Verified root cause" value={request.verified_root_cause ?? 'UNKNOWN'} mono={false} />
          <DataRow label="Required permission" value={humanize(request.required_permission_level, 'OBSERVE')} />
          <DataRow label="Approval status" value={humanize(request.approval_status, 'NOT APPROVED')} />
        </div>
      )}
      <button type="button" className="sen-btn secondary" onClick={() => onView?.(request.request_id ?? '')}>
        VIEW REQUEST
      </button>
    </div>
  )
}

export function ApplicationCard({ app, mode }: { app: AppItem; mode: ViewMode }) {
  return (
    <div className="sen-card">
      <div className="sen-card-row">
        <h3 className="sen-card-title">{app.friendly_name ?? app.id ?? 'Application'}</h3>
        <StatusMark status={app.overall_status} />
      </div>
      <div className="sen-chip-row">
        <span className="sen-chip">FRONTEND {humanize(app.frontend_state, 'UNKNOWN')}</span>
        <span className="sen-chip">BACKEND {humanize(app.backend_state, 'UNKNOWN')}</span>
      </div>
      <div className="sen-chip-row">
        <span className="sen-chip">DOCKER HEALTH {humanize(app.backend_docker_health, 'UNKNOWN')}</span>
        <span className="sen-chip">TLS {humanize(app.tls_status, 'UNKNOWN')}</span>
      </div>
      {mode === 'technical' && (
        <div className="sen-card-tech">
          <DataRow label="Frontend container" value={app.frontend_container ?? 'UNKNOWN'} />
          <DataRow label="Backend container" value={app.backend_container ?? 'UNKNOWN'} />
          <DataRow label="Backend HTTP" value={humanize(app.backend_http_health, 'UNKNOWN')} />
          <DataRow label="Frontend HTTP" value={humanize(app.frontend_http_health, 'UNKNOWN')} />
          <DataRow label="Network" value={app.network ?? 'UNKNOWN'} />
          <DataRow label="Last observation" value={prettyTime(app.last_checked)} />
        </div>
      )}
    </div>
  )
}

function App() {
  const [viewMode, setViewMode] = useState<ViewMode>('simple')
  const [activePage, setActivePage] = useState<NavPage>('overview')
  const [status, setStatus] = useState<StatusSummary | null>(null)
  const [latestRun, setLatestRun] = useState<{ checks?: CheckRecord[] } | null>(null)
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
  const [justRefreshed, setJustRefreshed] = useState(false)
  const [selectedAppId, setSelectedAppId] = useState<string | null>(null)
  const [selectedRequestId, setSelectedRequestId] = useState<string | null>(null)
  const [expandedFindingId, setExpandedFindingId] = useState<string | null>(null)

  const loadDashboardData = async () => {
    try {
      setLoading(true)
      const [statusData, runData, appData, requestData, findingData, activityData, settingsData] = await Promise.all([
        fetch('/api/status').then((res) => (res.ok ? res.json() : {})),
        fetch('/api/heartbeat/latest').then((res) => (res.ok ? res.json() : null)),
        fetch('/api/apps').then((res) => (res.ok ? res.json() : [])),
        fetch('/api/change-requests').then((res) => (res.ok ? res.json() : [])),
        fetch('/api/findings').then((res) => (res.ok ? res.json() : [])),
        fetch('/api/activity').then((res) => (res.ok ? res.json() : [])),
        fetch('/api/settings/public').then((res) => (res.ok ? res.json() : {})),
      ])
      setStatus(statusData as StatusSummary)
      setLatestRun(runData as { checks?: CheckRecord[] } | null)
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
      setJustRefreshed(true)
      setTimeout(() => setJustRefreshed(false), 600)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Heartbeat refresh failed.')
    } finally {
      setIsRefreshing(false)
    }
  }

  const overallStatusValue = status?.overall_status ?? 'unknown'
  const overallLabel = statusLabel(overallStatusValue, 'UNKNOWN')
  const coreServices = [...((status?.core_services ?? []) as CheckRecord[])].sort((a, b) => sortStatus(a.status) - sortStatus(b.status))
  const orderedApps = [...apps].sort((a, b) => sortStatus(a.overall_status) - sortStatus(b.overall_status))
  const allChecks = latestRun?.checks ?? []

  const ramCheck = coreServices.find((item) => (item.name ?? '').toLowerCase() === 'ram')
  const diskCheck = coreServices.find((item) => (item.name ?? '').toLowerCase() === 'disk')
  const ramPercent = Number(ramCheck?.evidence?.used_percent ?? NaN)
  const diskPercent = Number(diskCheck?.evidence?.used_percent ?? NaN)

  const summaryText = useMemo(() => status?.summary || 'No heartbeat has been recorded yet.', [status])

  const orderedFindings = [...findings].sort((a, b) => severityRank(a.severity) - severityRank(b.severity))
  const findingTime = latestRun ? prettyTime(status?.last_checked) : 'NO DATA'

  const selectedApp = apps.find((item) => item.id === selectedAppId) ?? null
  const relatedFindingsForApp = (app: AppItem) =>
    findings.filter((finding) => {
      const haystack = `${finding.affected_component ?? ''} ${finding.description ?? ''} ${finding.title ?? ''}`.toLowerCase()
      return Boolean(app.id) && haystack.includes(String(app.id).toLowerCase())
    })
  const relatedRequestsForApp = (app: AppItem) =>
    changeRequests.filter((request) => {
      const haystack = `${request.affected_component ?? ''} ${request.description ?? ''} ${request.title ?? ''}`.toLowerCase()
      return Boolean(app.id) && haystack.includes(String(app.id).toLowerCase())
    })

  const selectedRequest = changeRequests.find((item) => item.request_id === selectedRequestId) ?? null

  const relatedRequestForFinding = (finding: Finding) =>
    changeRequests.find((request) => (request.related_findings ?? []).includes(finding.finding_id ?? ''))

  const openRequest = (id: string) => {
    setSelectedRequestId(id)
    setActivePage('change-requests')
  }

  const renderOverview = () => {
    const openCount = changeRequests.filter((item) => (item.approval_status ?? 'NOT_APPROVED') !== 'APPROVED').length
    return (
      <div className="page-stack">
        <MachinePanel
          title="Hostless heartbeat"
          actions={
            <button type="button" className="sen-btn primary" onClick={refreshHeartbeat} disabled={isRefreshing}>
              {isRefreshing ? 'REFRESHING…' : 'REFRESH HEARTBEAT'}
            </button>
          }
        >
          <div className="heartbeat-grid">
            <div className="heartbeat-facts">
              <StatusMark status={overallStatusValue} label={overallLabel} />
              <DataRow label="Last check" value={prettyTime(status?.last_checked)} />
              <DataRow label="Last run ID" value={status?.last_run_id ?? 'NO DATA'} />
              <DataRow label="Core services" value={String(coreServices.length)} />
              <DataRow label="Apps monitored" value={String(apps.length)} />
              <DataRow label="Active findings" value={String(status?.active_findings ?? findings.length)} />
              <DataRow label="Open change requests" value={String(status?.open_change_requests ?? openCount)} />
            </div>
            <HeartbeatWave status={overallStatusValue} active={justRefreshed} />
          </div>
        </MachinePanel>

        <MachinePanel title="Owner summary" dense>
          <div className="sen-summary-text">{summaryText}</div>
        </MachinePanel>

        <MachinePanel title="System matrix">
          <div className="matrix-grid">
            {SYSTEM_MATRIX.map((item) => {
              const service = findCheck(coreServices, item.match)
              return (
                <ExplainPanel
                  key={item.label}
                  term={item.label}
                  status={service?.status}
                  simple={item.simple}
                  why={item.why}
                  technical={service?.evidence ?? 'No technical details available.'}
                  mode={viewMode}
                  glossaryTerm={item.glossaryTerm}
                />
              )
            })}
          </div>
        </MachinePanel>

        <MachinePanel title="Resource matrix">
          <div className="resource-grid">
            <ResourceMeter label="CPU" value={0} status="unknown" unavailable detail="No CPU collector configured yet." />
            <ResourceMeter
              label="RAM"
              value={Number.isFinite(ramPercent) ? ramPercent : 0}
              status={ramCheck?.status ?? 'unknown'}
              unavailable={!Number.isFinite(ramPercent)}
              detail={ramCheck ? `Threshold: warn ${ramCheck.evidence?.warning_threshold_pct}% / fail ${ramCheck.evidence?.failed_threshold_pct}%` : undefined}
              glossaryTerm="RAM"
            />
            <ResourceMeter
              label="DISK"
              value={Number.isFinite(diskPercent) ? diskPercent : 0}
              status={diskCheck?.status ?? 'unknown'}
              unavailable={!Number.isFinite(diskPercent)}
              detail={diskCheck ? `Filesystem: ${diskCheck.evidence?.filesystem ?? 'UNKNOWN'}` : undefined}
              glossaryTerm="Disk"
            />
            <ResourceMeter label="UPTIME" value={0} status="unknown" unavailable detail="No uptime collector configured yet." />
          </div>
        </MachinePanel>

        <div className="two-col">
          <MachinePanel title="Active issues">
            {orderedFindings.length ? (
              <div className="issue-list">
                {orderedFindings.slice(0, 6).map((finding) => (
                  <div key={finding.finding_id ?? finding.title} className="issue-row">
                    <StatusMark status={finding.status} label={humanize(finding.severity, 'INFO')} />
                    <div className="issue-body">
                      <div className="issue-title">{finding.title ?? 'Finding'}</div>
                      <div className="issue-meta">{finding.affected_component ?? 'Unknown component'}</div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState message="No findings are available." />
            )}
          </MachinePanel>

          <MachinePanel title="Change requests summary">
            {changeRequests.length ? (
              <div className="card-stack">
                {changeRequests.slice(0, 3).map((request) => (
                  <ChangeRequestCard key={request.request_id} request={request} mode={viewMode} onView={openRequest} />
                ))}
              </div>
            ) : (
              <EmptyState message="No change requests are available." />
            )}
          </MachinePanel>
        </div>
      </div>
    )
  }

  const renderHostless = () => {
    const publicUrlCheck = findCheck(allChecks, /^public hostless url$/i)
    const networkCheck = findCheck(allChecks, /^core docker network$/i)
    const backendCheck = findCheck(allChecks, /^application backend$/i)
    const frontendCheck = findCheck(allChecks, /^application frontend$/i)
    const mongoCheck = findCheck(coreServices, /^mongodb$/i)
    const caddyCheck = findCheck(coreServices, /^caddy$/i)
    const coreBackend = findCheck(coreServices, /^hostless core backend$/i)
    const coreFrontend = findCheck(coreServices, /^hostless core frontend$/i)
    const hostlessWorst = [coreBackend, coreFrontend, mongoCheck]
      .map((item) => item?.status)
      .sort((a, b) => sortStatus(a) - sortStatus(b))[0]

    return (
      <div className="page-stack">
        <MachinePanel title="Known architecture relationships">
          <div className="topology">
            <SystemNode label="INTERNET" status={publicUrlCheck?.status} sub={publicUrlCheck ? undefined : 'NOT MONITORED'} />
            <Connector />
            <SystemNode label="CADDY" status={caddyCheck?.status} />
            <Connector />
            <SystemNode label="HOSTLESS CORE" status={hostlessWorst} sub="BACKEND · FRONTEND · MONGODB" />
            <Connector />
            <SystemNode label="APPLICATION NETWORK" status={networkCheck?.status} sub={networkCheck ? `${(networkCheck.evidence?.networks as unknown[] | undefined)?.length ?? 0} NETWORK(S)` : undefined} />
            <Connector />
            <div className="sen-node-branch">
              <SystemNode label="FRONTEND" status={frontendCheck?.status} />
              <SystemNode label="BACKEND" status={backendCheck?.status} />
            </div>
            <Connector />
            <SystemNode label="DATABASE" status={mongoCheck?.status} sub="MONGODB" />
          </div>
          <p className="sen-note">Only relationships confirmed by the latest Sentinel run are shown. Unmapped links display UNKNOWN.</p>
        </MachinePanel>

        <MachinePanel title="System matrix">
          <div className="matrix-grid">
            {SYSTEM_MATRIX.map((item) => {
              const service = findCheck(coreServices, item.match)
              return (
                <ExplainPanel
                  key={item.label}
                  term={item.label}
                  status={service?.status}
                  simple={item.simple}
                  why={item.why}
                  technical={service?.evidence ?? 'No technical details available.'}
                  mode={viewMode}
                  glossaryTerm={item.glossaryTerm}
                />
              )
            })}
          </div>
        </MachinePanel>

        <MachinePanel title="System resources">
          <div className="resource-grid">
            <ResourceMeter label="CPU" value={0} status="unknown" unavailable detail="No CPU collector configured yet." />
            <ResourceMeter
              label="RAM"
              value={Number.isFinite(ramPercent) ? ramPercent : 0}
              status={ramCheck?.status ?? 'unknown'}
              unavailable={!Number.isFinite(ramPercent)}
              detail={ramCheck ? `${ramCheck.evidence?.used_mb ?? '?'} / ${ramCheck.evidence?.total_mb ?? '?'} MB` : undefined}
              glossaryTerm="RAM"
            />
            <ResourceMeter
              label="DISK"
              value={Number.isFinite(diskPercent) ? diskPercent : 0}
              status={diskCheck?.status ?? 'unknown'}
              unavailable={!Number.isFinite(diskPercent)}
              detail={diskCheck ? `${diskCheck.evidence?.used_mb ?? '?'} / ${diskCheck.evidence?.total_mb ?? '?'} MB` : undefined}
              glossaryTerm="Disk"
            />
            <ResourceMeter label="UPTIME" value={0} status="unknown" unavailable detail="No uptime collector configured yet." />
          </div>
        </MachinePanel>
      </div>
    )
  }

  const renderApplications = () => (
    <div className="page-stack">
      <MachinePanel title="Applications">
        {orderedApps.length ? (
          <MachineTable columns={['NAME', 'APP ID', 'OVERALL', 'FRONTEND', 'BACKEND PROCESS', 'DOCKER HEALTH', 'HTTP HEALTH', 'TLS', 'NETWORK', 'LAST OBSERVATION']}>
            {orderedApps.map((app, index) => (
              <tr
                key={`${app.id ?? 'app'}-${index}`}
                className={`clickable${selectedAppId === app.id ? ' selected' : ''}`}
                onClick={() => setSelectedAppId(app.id ?? null)}
              >
                <td>{app.friendly_name ?? app.id ?? 'Application'}</td>
                <td className="mono">{app.id ?? 'UNKNOWN'}</td>
                <td>
                  <StatusMark status={app.overall_status} />
                </td>
                <td className="mono">{humanize(app.frontend_state, 'UNKNOWN')}</td>
                <td className="mono">{humanize(app.backend_state, 'UNKNOWN')}</td>
                <td className="mono">
                  <div>BE {humanize(app.backend_docker_health, 'UNKNOWN')}</div>
                  <div>FE {humanize(app.frontend_docker_health, 'UNKNOWN')}</div>
                </td>
                <td className="mono">
                  <div>BE {humanize(app.backend_http_health, 'UNKNOWN')}</div>
                  <div>FE {humanize(app.frontend_http_health, 'UNKNOWN')}</div>
                </td>
                <td className="mono">{humanize(app.tls_status, 'UNKNOWN')}</td>
                <td className="mono">{app.network ?? 'UNKNOWN'}</td>
                <td className="mono">{prettyTime(app.last_checked)}</td>
              </tr>
            ))}
          </MachineTable>
        ) : (
          <EmptyState message="No mapped applications are available." />
        )}
      </MachinePanel>

      {selectedApp && (
        <MachinePanel
          title={`Application detail — ${selectedApp.friendly_name ?? selectedApp.id}`}
          actions={
            <button type="button" className="sen-btn secondary" onClick={() => setSelectedAppId(null)}>
              CLOSE
            </button>
          }
        >
          <div className="detail-grid">
            <ApplicationCard app={selectedApp} mode={viewMode} />
            <div className="detail-sections">
              <div className="detail-section">
                <SectionLabel>System</SectionLabel>
                <DataRow label="App ID" value={selectedApp.id ?? 'UNKNOWN'} />
                <DataRow label="Network" value={selectedApp.network ?? 'UNKNOWN'} />
                <DataRow label="Last observation" value={prettyTime(selectedApp.last_checked)} />
              </div>
              <div className="detail-section">
                <SectionLabel>Frontend</SectionLabel>
                <DataRow label="Container" value={selectedApp.frontend_container ?? 'UNKNOWN'} />
                <DataRow label="Process state" value={humanize(selectedApp.frontend_state, 'UNKNOWN')} />
                <DataRow label="Docker health" value={humanize(selectedApp.frontend_docker_health, 'UNKNOWN')} />
              </div>
              <div className="detail-section">
                <SectionLabel>Backend</SectionLabel>
                <DataRow label="Container" value={selectedApp.backend_container ?? 'UNKNOWN'} />
                <DataRow label="Process state" value={humanize(selectedApp.backend_state, 'UNKNOWN')} />
                <DataRow label="Docker health" value={humanize(selectedApp.backend_docker_health, 'UNKNOWN')} />
              </div>
              <div className="detail-section">
                <SectionLabel>Web health</SectionLabel>
                <DataRow label="Backend HTTP" value={humanize(selectedApp.backend_http_health, 'UNKNOWN')} />
                <DataRow label="Frontend HTTP" value={humanize(selectedApp.frontend_http_health, 'UNKNOWN')} />
              </div>
              <div className="detail-section">
                <SectionLabel>TLS / Security</SectionLabel>
                <DataRow label="TLS status" value={humanize(selectedApp.tls_status, 'UNKNOWN')} />
              </div>
              <div className="detail-section">
                <SectionLabel>Findings</SectionLabel>
                {relatedFindingsForApp(selectedApp).length ? (
                  relatedFindingsForApp(selectedApp).map((finding) => (
                    <DataRow key={finding.finding_id} label={finding.title ?? 'Finding'} value={humanize(finding.severity)} mono={false} />
                  ))
                ) : (
                  <span className="sen-row-value muted">NONE</span>
                )}
              </div>
              <div className="detail-section">
                <SectionLabel>Change requests</SectionLabel>
                {relatedRequestsForApp(selectedApp).length ? (
                  relatedRequestsForApp(selectedApp).map((request) => (
                    <DataRow key={request.request_id} label={request.request_id ?? ''} value={humanize(request.approval_status, 'NOT APPROVED')} mono={false} />
                  ))
                ) : (
                  <span className="sen-row-value muted">NONE</span>
                )}
              </div>
              {viewMode === 'technical' && (
                <div className="detail-section wide">
                  <SectionLabel>Evidence</SectionLabel>
                  <EvidenceBlock data={selectedApp} />
                </div>
              )}
            </div>
          </div>
        </MachinePanel>
      )}
    </div>
  )

  const renderChangeRequests = () => {
    const openCount = changeRequests.filter((item) => (item.approval_status ?? 'NOT_APPROVED') !== 'APPROVED').length
    const highCount = changeRequests.filter((item) => (item.severity ?? '').toLowerCase() === 'high').length
    const warningCount = changeRequests.filter((item) => (item.severity ?? '').toLowerCase() === 'warning').length
    const awaitingCount = changeRequests.filter((item) => (item.approval_status ?? 'NOT_APPROVED') === 'NOT_APPROVED').length
    const approvedCount = changeRequests.filter((item) => item.approval_status === 'APPROVED').length

    return (
      <div className="page-stack">
        <MachinePanel
          title={
            <span className="panel-title-with-tip">
              Owner review queue
              <InfoTip term="Change Request" />
            </span>
          }
        >
          <div className="stats-row">
            <MetricBlock label="Open" value={String(openCount)} status="warning" />
            <MetricBlock label="High" value={String(highCount)} status="failed" />
            <MetricBlock label="Warning" value={String(warningCount)} status="warning" />
            <MetricBlock label="Awaiting review" value={String(awaitingCount)} status="unknown" />
            <MetricBlock label="Approved" value={String(approvedCount)} status="healthy" />
          </div>

          {changeRequests.length ? (
            <MachineTable columns={['HCR ID', 'TITLE', 'CATEGORY', 'SEVERITY', 'STATUS', 'PERMISSION', 'APPROVAL']}>
              {changeRequests.map((request, index) => (
                <tr
                  key={`${request.request_id ?? 'request'}-${index}`}
                  className={`clickable${selectedRequestId === request.request_id ? ' selected' : ''}`}
                  onClick={() => setSelectedRequestId(request.request_id ?? null)}
                >
                  <td className="mono">{request.request_id}</td>
                  <td>{request.title}</td>
                  <td className="mono">{humanize(request.category, 'UNKNOWN')}</td>
                  <td className="mono">{humanize(request.severity)}</td>
                  <td className="mono">{humanize(request.status, 'DRAFT')}</td>
                  <td>
                    <PermissionTag level={request.required_permission_level} />
                  </td>
                  <td>
                    <StatusBadge status={request.approval_status} label={humanize(request.approval_status, 'NOT APPROVED')} />
                  </td>
                </tr>
              ))}
            </MachineTable>
          ) : (
            <EmptyState message="No change requests are available." />
          )}
        </MachinePanel>

        {selectedRequest && (
          <MachinePanel
            title={`Change request detail — ${selectedRequest.request_id}`}
            actions={
              <button type="button" className="sen-btn secondary" onClick={() => setSelectedRequestId(null)}>
                CLOSE
              </button>
            }
          >
            <div className="cr-detail">
              <div className="cr-banner">NO ACTION AUTHORIZED</div>
              <div className="detail-section">
                <SectionLabel>Problem</SectionLabel>
                <p className="sen-explain-line">{selectedRequest.description || 'No problem description recorded.'}</p>
              </div>
              <div className="detail-section">
                <SectionLabel>Simple explanation</SectionLabel>
                <p className="sen-explain-line">{categoryCopy(selectedRequest.category).simple}</p>
              </div>
              <div className="detail-section">
                <SectionLabel>Why it matters</SectionLabel>
                <p className="sen-explain-line">{categoryCopy(selectedRequest.category).why}</p>
              </div>
              <div className="detail-section">
                <SectionLabel>Verified condition</SectionLabel>
                <p className="sen-explain-line">{selectedRequest.verified_condition || 'UNKNOWN'}</p>
              </div>
              <div className="detail-section">
                <SectionLabel>Verified root cause</SectionLabel>
                <p className="sen-explain-line">{selectedRequest.verified_root_cause || 'UNKNOWN'}</p>
              </div>
              {viewMode === 'technical' && (
                <div className="detail-section wide">
                  <SectionLabel>Evidence</SectionLabel>
                  <EvidenceBlock data={selectedRequest.evidence ?? 'No structured evidence provided.'} />
                </div>
              )}
              <div className="detail-section">
                <SectionLabel>Requested outcome</SectionLabel>
                <p className="sen-explain-line">{selectedRequest.requested_outcome || 'Not specified.'}</p>
              </div>
              <div className="detail-section">
                <SectionLabel>Constraints</SectionLabel>
                {(selectedRequest.constraints ?? []).length ? (
                  <ul className="sen-list">
                    {(selectedRequest.constraints ?? []).map((constraint) => (
                      <li key={constraint}>{constraint}</li>
                    ))}
                  </ul>
                ) : (
                  <span className="sen-row-value muted">NONE RECORDED</span>
                )}
              </div>
              <div className="detail-section">
                <SectionLabel>Verification plan</SectionLabel>
                {(selectedRequest.verification_plan ?? []).length ? (
                  <ul className="sen-list">
                    {(selectedRequest.verification_plan ?? []).map((step) => (
                      <li key={step}>{step}</li>
                    ))}
                  </ul>
                ) : (
                  <span className="sen-row-value muted">NOT SPECIFIED</span>
                )}
              </div>
              <div className="detail-section">
                <SectionLabel>Required permission</SectionLabel>
                <PermissionTag level={selectedRequest.required_permission_level} />
                <p className="sen-explain-line">{permissionCopy(selectedRequest.required_permission_level).description}</p>
              </div>
              <div className="detail-section">
                <SectionLabel>Approval status</SectionLabel>
                <StatusBadge status={selectedRequest.approval_status} label={humanize(selectedRequest.approval_status, 'NOT APPROVED')} />
              </div>
            </div>
          </MachinePanel>
        )}
      </div>
    )
  }

  const renderFindings = () => (
    <div className="page-stack">
      <MachinePanel
        title={
          <span className="panel-title-with-tip">
            Findings
            <InfoTip term="Finding" />
          </span>
        }
      >
        {orderedFindings.length ? (
          <MachineTable columns={['TIME', 'SEVERITY', 'SYSTEM', 'FINDING', 'RELATED REQUEST']}>
            {orderedFindings.map((finding) => {
              const relatedRequest = relatedRequestForFinding(finding)
              const isExpanded = expandedFindingId === (finding.finding_id ?? finding.title)
              const rowKey = finding.finding_id ?? finding.title ?? 'finding'
              return (
                <Fragment key={rowKey}>
                  <tr
                    className="clickable"
                    onClick={() => setExpandedFindingId(isExpanded ? null : rowKey)}
                  >
                    <td className="mono">{findingTime}</td>
                    <td>
                      <StatusMark status={finding.status} label={humanize(finding.severity, 'INFO')} />
                    </td>
                    <td>{finding.affected_component ?? 'Unknown component'}</td>
                    <td>{finding.title ?? 'Finding'}</td>
                    <td className="mono">{relatedRequest?.request_id ?? 'NONE'}</td>
                  </tr>
                  {isExpanded && (
                    <tr>
                      <td colSpan={5}>
                        <p className="sen-explain-line">{finding.description ?? 'No detailed description provided.'}</p>
                        {viewMode === 'technical' && <EvidenceBlock data={finding.evidence ?? 'No evidence recorded.'} />}
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
          </MachineTable>
        ) : (
          <EmptyState message="No findings are available." />
        )}
      </MachinePanel>
    </div>
  )

  const renderActivity = () => (
    <div className="page-stack">
      <MachinePanel title="Activity stream">
        {activity.length ? (
          <div className="activity-list">
            {activity.map((item, index) => (
              <div key={`${item.type ?? 'event'}-${item.time ?? 'unknown'}-${index}`} className="activity-row">
                <span className="sen-tech-value">{prettyTime(item.time)}</span>
                <StatusMark status={item.status} label={humanize(item.status, 'UNKNOWN')} />
                <span className="activity-type">{humanize(item.type, 'EVENT')}</span>
                <span className="activity-message">{item.message ?? 'No message recorded.'}</span>
                {viewMode === 'technical' && item.details && <EvidenceBlock data={item.details} />}
              </div>
            ))}
          </div>
        ) : (
          <EmptyState message="No activity has been recorded yet." />
        )}
      </MachinePanel>
    </div>
  )

  const renderDocumentation = () => (
    <div className="page-stack">
      <MachinePanel title="Documentation" dense>
        <div className="doc-layout">
          <div className="doc-tree">
            {(Object.keys(DOCS_CATALOG) as Array<keyof typeof DOCS_CATALOG>).map((stream) => (
              <div key={stream} className="doc-stream">
                <SectionLabel>{stream === 'ai' ? 'AI CONTEXT' : stream}</SectionLabel>
                {DOCS_CATALOG[stream].map((file) => {
                  const id = `${stream}/${file}`
                  return (
                    <button
                      key={id}
                      type="button"
                      className={selectedDoc === id ? 'doc-link active' : 'doc-link'}
                      onClick={() => setSelectedDoc(id)}
                    >
                      {file}
                    </button>
                  )
                })}
              </div>
            ))}
            <p className="sen-note">Public ROADMAP is owner controlled. No editing.</p>
          </div>
          <pre className="doc-viewer">{documentation || 'Document content is loading.'}</pre>
        </div>
      </MachinePanel>
    </div>
  )

  const renderSettings = () => (
    <div className="page-stack">
      <MachinePanel title="Settings">
        <DataRow label="Sentinel mode" value="OBSERVATION" />
        <DataRow label="Hostless connection" value={settings?.hostless_configured ? 'CONFIGURED' : 'NOT CONFIGURED'} />
        <DataRow label="SSH key" value={settings?.ssh_key_configured ? 'CONFIGURED' : 'NOT CONFIGURED'} />
        <DataRow label="Auto-refresh" value={settings?.auto_refresh ? 'ON' : 'OFF'} />
        <DataRow label="Refresh interval" value={`${settings?.refresh_interval_seconds ?? 30}s`} />
        <div className="sen-row">
          <span className="sen-row-label">View mode</span>
          <ViewModeToggle value={viewMode} onChange={setViewMode} />
        </div>
      </MachinePanel>
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
    return (
      <div className="app-shell">
        <div className="sen-atmosphere" />
        <LoadingState message="LOADING SENTINEL RUNTIME DATA…" />
      </div>
    )
  }

  return (
    <div className="app-shell">
      <div className="sen-atmosphere" />
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
            <button
              key={item.key}
              type="button"
              className={activePage === item.key ? 'nav-link active' : 'nav-link'}
              onClick={() => setActivePage(item.key)}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <SectionLabel>Observation mode</SectionLabel>
          <p className="sen-note">NO AUTOMATIC REPAIRS</p>
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div className="topbar-brand">
            <p className="eyebrow">OBSERVATION MODE · NO AUTOMATIC REPAIRS</p>
            <h1>STALLION SENTINEL</h1>
          </div>
          <div className="topbar-right">
            <DataRow label="Last heartbeat" value={prettyTime(status?.last_checked)} />
            <StatusMark status={overallStatusValue} label={overallLabel} />
            <ViewModeToggle value={viewMode} onChange={setViewMode} />
            <button type="button" className="sen-btn primary" onClick={refreshHeartbeat} disabled={isRefreshing}>
              {isRefreshing ? 'REFRESHING…' : 'REFRESH HEARTBEAT'}
            </button>
          </div>
        </header>

        {error && <ErrorState message={error} />}
        <div className="page-header-row">
          <SectionLabel>{navItems.find((item) => item.key === activePage)?.label}</SectionLabel>
        </div>
        {pages[activePage]}
      </main>
    </div>
  )
}

export default App
