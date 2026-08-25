import type { ReactNode } from 'react'
import type { StatusValue, ViewMode } from '../lib/types'
import { normalizeStatus, statusLabel, clampPercent, GLOSSARY, permissionCopy } from '../lib/format'
import './Machine.css'

export function SectionLabel({ children }: { children: ReactNode }) {
  return <span className="sen-section-label">{children}</span>
}

export function MachinePanel({
  title,
  actions,
  dense,
  children,
  className,
}: {
  title?: ReactNode
  actions?: ReactNode
  dense?: boolean
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`sen-panel${className ? ` ${className}` : ''}`}>
      {title && (
        <div className="sen-panel-head">
          <h2>{title}</h2>
          {actions && <div className="sen-panel-actions">{actions}</div>}
        </div>
      )}
      <div className={`sen-panel-body${dense ? ' dense' : ''}`}>{children}</div>
    </section>
  )
}

export function StatusMark({ status, label }: { status?: string; label?: string }) {
  const tone = normalizeStatus(status)
  return (
    <span className={`sen-status tone-${tone}`}>
      <span className="sen-status-dot" />
      {label ?? statusLabel(status)}
    </span>
  )
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

export function MetricBlock({ label, value, status, detail }: { label: string; value: string; status?: string; detail?: string }) {
  return (
    <div className="sen-metric">
      <div className="sen-metric-top">
        <SectionLabel>{label}</SectionLabel>
        {status && <StatusMark status={status} />}
      </div>
      <div className="sen-metric-value">{value}</div>
      {detail && <div className="sen-metric-detail">{detail}</div>}
    </div>
  )
}

export function TechnicalValue({ children }: { children: ReactNode }) {
  return <span className="sen-tech-value">{children}</span>
}

const SEGMENT_COUNT = 24

export function ResourceSignal({
  label,
  value,
  status,
  detail,
  unavailable,
  glossaryTerm,
}: {
  label: string
  value: number
  status: string
  detail?: string
  unavailable?: boolean
  glossaryTerm?: string
}) {
  const clamped = clampPercent(value, 0, 100)
  const filledCount = unavailable ? 0 : Math.round((clamped / 100) * SEGMENT_COUNT)
  const tone = normalizeStatus(status)
  return (
    <div className={`sen-resource${unavailable ? ' unavailable' : ''}`}>
      <div className="sen-resource-head">
        <span className="sen-resource-label">
          {label}
          {glossaryTerm && <InfoTip term={glossaryTerm} />}
        </span>
        <StatusMark status={status} />
      </div>
      <div className="sen-resource-value">{unavailable ? 'NO DATA' : `${clamped.toFixed(1)}%`}</div>
      <div className="sen-segments">
        {Array.from({ length: SEGMENT_COUNT }, (_, index) => (
          <div key={index} className={`sen-segment${index < filledCount ? ` filled tone-${tone}` : ''}`} />
        ))}
      </div>
      <div className="sen-resource-meta">{detail ?? (unavailable ? 'Not collected by Sentinel yet.' : ' ')}</div>
    </div>
  )
}

export function DataRow({ label, value, mono = true }: { label: string; value: ReactNode; mono?: boolean }) {
  return (
    <div className="sen-row">
      <span className="sen-row-label">{label}</span>
      <span className={mono ? 'sen-row-value' : 'sen-row-value'} style={mono ? undefined : { fontFamily: 'var(--sen-font-sans)' }}>
        {value}
      </span>
    </div>
  )
}

export function PermissionTag({ level }: { level?: string }) {
  const copy = permissionCopy(level)
  return (
    <span className="sen-permission" title={copy.description}>
      {copy.label}
    </span>
  )
}

export function EvidenceBlock({ data }: { data: unknown }) {
  const text = typeof data === 'string' ? data : JSON.stringify(data, null, 2)
  return <pre className="sen-evidence">{text || 'No evidence recorded.'}</pre>
}

export function EmptyState({ message }: { message: string }) {
  return <div className="sen-empty">{message}</div>
}

export function ErrorState({ message }: { message: string }) {
  return <div className="sen-error">{message}</div>
}

export function LoadingState({ message = 'PROCESSING…' }: { message?: string }) {
  return <div className="sen-loading">{message}</div>
}

export function InfoTip({ term }: { term: keyof typeof GLOSSARY | string }) {
  const definition = GLOSSARY[term]
  if (!definition) return null
  return (
    <details className="sen-infotip">
      <summary aria-label={`What is ${term}?`}>?</summary>
      <div className="sen-infotip-body">{definition}</div>
    </details>
  )
}

export function HeartbeatWave({ status, active }: { status?: string; active?: boolean }) {
  const tone = normalizeStatus(status)
  const path = 'M0,32 L30,32 L40,10 L50,54 L60,20 L70,44 L80,32 L110,32 L120,14 L130,50 L140,32 L400,32'
  return (
    <div className={`sen-heartbeat tone-${tone}${active ? ' flash' : ''}`} aria-hidden="true">
      <svg viewBox="0 0 400 64" preserveAspectRatio="none">
        <path className="sen-heartbeat-line sen-heartbeat-sweep" d={path} strokeDasharray="340 60" />
      </svg>
    </div>
  )
}

export function SystemNode({ label, status, sub }: { label: string; status?: string; sub?: string }) {
  const tone = normalizeStatus(status)
  return (
    <div className={`sen-node tone-${tone}`}>
      <span className="sen-node-label">{label}</span>
      <span className="sen-node-sub">{sub ?? statusLabel(status)}</span>
    </div>
  )
}

export function Connector() {
  return <div className="sen-connector" />
}

export function ExplainPanel({
  term,
  status,
  simple,
  why,
  technical,
  mode,
  glossaryTerm,
}: {
  term: string
  status?: string
  simple: string
  why: string
  technical?: unknown
  mode: ViewMode
  glossaryTerm?: string
}) {
  return (
    <div className="sen-explain">
      <div className="sen-explain-head">
        <span className="sen-explain-term">
          {term}
          {glossaryTerm && <InfoTip term={glossaryTerm} />}
        </span>
        <StatusMark status={status} />
      </div>
      <div className="sen-explain-body">
        <p className="sen-explain-line">
          <strong>Simple</strong>
          {simple}
        </p>
        <p className="sen-explain-line">
          <strong>Why it matters</strong>
          {why}
        </p>
        {mode === 'technical' && technical !== undefined && (
          <div className="sen-explain-line">
            <strong>Technical</strong>
            <EvidenceBlock data={technical} />
          </div>
        )}
      </div>
    </div>
  )
}

export function MachineTable({
  columns,
  children,
}: {
  columns: string[]
  children: ReactNode
}) {
  return (
    <div className="sen-table-wrap">
      <table className="sen-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  )
}

export const ResourceMeter = ResourceSignal

export type { StatusValue }
