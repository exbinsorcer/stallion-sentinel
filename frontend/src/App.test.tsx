import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App, { ApplicationCard, ChangeRequestCard, ResourceMeter, StatusBadge, ViewModeToggle } from './App'

const makeJsonResponse = (payload: unknown) => ({ ok: true, json: async () => payload })

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/api/status')) {
        return Promise.resolve(
          makeJsonResponse({
            overall_status: 'warning',
            summary: 'Hostless core services are running, but the server needs attention.',
            last_checked: '2026-08-25T03:33:53+00:00',
            last_run_id: 'SEN-000004',
            core_services: [],
            open_change_requests: 1,
            active_findings: 1,
          }),
        )
      }
      if (url.endsWith('/api/apps')) {
        return Promise.resolve(
          makeJsonResponse([
            {
              id: 'arcticdrive',
              friendly_name: 'ArcticDrive',
              overall_status: 'warning',
              frontend_state: 'RUNNING',
              backend_state: 'RUNNING',
              backend_http_health: 'UNKNOWN',
              frontend_http_health: 'UNKNOWN',
              tls_status: 'EXPIRED',
              last_checked: '2026-08-25T03:33:53+00:00',
            },
          ]),
        )
      }
      if (url.endsWith('/api/change-requests')) {
        return Promise.resolve(
          makeJsonResponse([
            {
              request_id: 'HCR-000001',
              title: 'Generated backend healthcheck depends on an unavailable binary',
              severity: 'HIGH',
              status: 'DRAFT',
              approval_status: 'NOT_APPROVED',
              required_permission_level: 'TEST_BRANCH',
              description: 'Test request.',
            },
          ]),
        )
      }
      if (url.endsWith('/api/findings')) {
        return Promise.resolve(
          makeJsonResponse([
            {
              finding_id: 'F-001',
              title: 'Expired certificate',
              severity: 'HIGH',
              status: 'failed',
              description: 'The public certificate is expired.',
              affected_component: 'TLS',
              evidence: {},
            },
          ]),
        )
      }
      if (url.endsWith('/api/activity')) {
        return Promise.resolve(
          makeJsonResponse([
            {
              time: '2026-08-25T03:33:53+00:00',
              type: 'heartbeat',
              status: 'warning',
              message: 'Heartbeat completed: SEN-000004',
            },
          ]),
        )
      }
      if (url.endsWith('/api/settings/public')) {
        return Promise.resolve(
          makeJsonResponse({
            mode: 'OBSERVATION',
            hostless_configured: true,
            hostless_ssh_host: 'CONFIGURED',
            hostless_ssh_user: 'CONFIGURED',
            ssh_key_configured: true,
            last_successful_ssh_observation: 'AVAILABLE',
            auto_refresh: false,
            refresh_interval_seconds: 30,
            view_preference: 'simple',
          }),
        )
      }
      if (url.includes('/api/docs/')) {
        return Promise.resolve(makeJsonResponse({ content: '# Sentinel\n\nObservation mode is active.' }))
      }
      return Promise.resolve(makeJsonResponse([]))
    }),
  )
})

describe('StatusBadge', () => {
  it('renders health and failed labels', () => {
    const { rerender } = render(<StatusBadge status="healthy" label="HEALTHY" />)
    expect(screen.getByText('HEALTHY')).toBeInTheDocument()

    rerender(<StatusBadge status="failed" label="FAILED" />)
    expect(screen.getByText('FAILED')).toBeInTheDocument()
  })
})

describe('ViewModeToggle', () => {
  it('switches between simple and technical modes', () => {
    const onChange = vi.fn()
    render(<ViewModeToggle value="simple" onChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: 'TECHNICAL' }))
    expect(onChange).toHaveBeenCalledWith('technical')
  })
})

describe('ResourceMeter', () => {
  it('shows failed state at high utilization', () => {
    render(<ResourceMeter label="RAM" value={90.6} status="failed" detail="Memory pressure" />)
    expect(screen.getByText('RAM')).toBeInTheDocument()
    expect(screen.getByText('FAILED')).toBeInTheDocument()
  })
})

describe('ChangeRequestCard', () => {
  it('shows not approved change requests', () => {
    render(
      <ChangeRequestCard
        mode="simple"
        request={{
          request_id: 'HCR-000001',
          title: 'Generated backend healthcheck depends on an unavailable binary',
          severity: 'HIGH',
          status: 'DRAFT',
          approval_status: 'NOT_APPROVED',
          required_permission_level: 'TEST_BRANCH',
          description: 'Change request exists but is not approved yet.',
        }}
      />,
    )
    expect(screen.getByText('HCR-000001')).toBeInTheDocument()
    expect(screen.getByText('NOT APPROVED')).toBeInTheDocument()
  })
})

describe('ApplicationCard', () => {
  it('shows docker health discrepancy clearly', () => {
    render(
      <ApplicationCard
        mode="simple"
        app={{
          id: 'arcticdrive',
          friendly_name: 'ArcticDrive',
          overall_status: 'warning',
          backend_state: 'RUNNING',
          frontend_state: 'RUNNING',
          backend_http_health: 'UNKNOWN',
          frontend_http_health: 'UNKNOWN',
          tls_status: 'EXPIRED',
        }}
      />,
    )
    expect(screen.getByText('ArcticDrive')).toBeInTheDocument()
    expect(screen.getByText(/Docker health/i)).toBeInTheDocument()
  })
})

describe('App smoke', () => {
  it('renders the Stallion Sentinel shell without crashing', async () => {
    render(<App />)
    await waitFor(() => expect(screen.getByRole('heading', { name: 'STALLION SENTINEL' })).toBeInTheDocument())
  })
})
