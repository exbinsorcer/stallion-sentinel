export type ViewMode = 'simple' | 'technical'

export type NavPage =
  | 'overview'
  | 'hostless'
  | 'applications'
  | 'change-requests'
  | 'findings'
  | 'activity'
  | 'documentation'
  | 'settings'

export type Severity = 'critical' | 'high' | 'warning' | 'info'
export type StatusValue = 'healthy' | 'warning' | 'failed' | 'unknown'

export type CoreService = {
  name?: string
  status?: string
  message?: string
  evidence?: Record<string, unknown>
}

export type StatusSummary = {
  overall_status?: string
  summary?: string
  hostless_configured?: boolean
  core_services?: CoreService[]
  applications?: Array<Record<string, unknown>>
  open_change_requests?: number
  active_findings?: number
  last_checked?: string | null
  last_run_id?: string | null
}

export type ChangeRequest = {
  request_id?: string
  title?: string
  severity?: string
  status?: string
  category?: string
  approval_status?: string
  required_permission_level?: string
  simple_explanation?: string
  description?: string
  verified_condition?: string
  verified_root_cause?: string | null
  requested_outcome?: string
  constraints?: string[]
  verification_plan?: string[]
  affected_component?: string
  affected_system?: string
  related_findings?: string[]
  related_run_ids?: string[]
  created_at?: string
  updated_at?: string
  evidence?: Array<Record<string, unknown>> | Record<string, unknown>
}

export type Finding = {
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

export type ActivityItem = {
  time?: string
  type?: string
  status?: string
  message?: string
  details?: Record<string, unknown>
}

export type AppItem = {
  id?: string
  friendly_name?: string
  overall_status?: string
  backend_container?: string
  frontend_container?: string
  backend_state?: string
  frontend_state?: string
  backend_docker_health?: string
  frontend_docker_health?: string
  backend_http_health?: string
  frontend_http_health?: string
  tls_status?: string
  network?: string | null
  last_checked?: string
}

export type PublicSettings = {
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
