import { CheckCircle2, FileText, FileType2, Loader2, AlertTriangle, Clock } from 'lucide-react'

export function Spinner({ className = 'h-5 w-5' }) {
  return <Loader2 className={`animate-spin text-brand ${className}`} />
}

export function EmptyState({ icon: Icon, title, text, children }) {
  return (
    <div className="flex flex-col items-center justify-center px-4 py-12 text-center">
      {Icon && <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-tint text-brand"><Icon className="h-7 w-7" /></div>}
      <h3 className="text-base font-bold">{title}</h3>
      {text && <p className="mt-1 max-w-sm text-sm text-ink">{text}</p>}
      {children && <div className="mt-4">{children}</div>}
    </div>
  )
}

const STATUS = {
  processed: { cls: 'bg-emerald-50 text-emerald-600', label: 'Processed', Icon: CheckCircle2 },
  processing: { cls: 'bg-brand-soft text-brand', label: 'Processing', Icon: Loader2, spin: true },
  uploaded: { cls: 'bg-amber-50 text-amber-600', label: 'Queued', Icon: Clock },
  failed: { cls: 'bg-red-50 text-red-600', label: 'Failed', Icon: AlertTriangle },
}

export function StatusBadge({ status }) {
  const s = STATUS[status] || STATUS.uploaded
  return (
    <span className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-semibold ${s.cls}`}>
      <s.Icon className={`h-3.5 w-3.5 ${s.spin ? 'animate-spin' : ''}`} /> {s.label}
    </span>
  )
}

export function FileIcon({ type, className = 'h-6 w-6' }) {
  const palette = { pdf: 'bg-red-50 text-red-500', docx: 'bg-blue-50 text-blue-600', txt: 'bg-brand-tint text-ink' }
  const Icon = type === 'txt' ? FileText : FileType2
  return (
    <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl ${palette[type] || palette.txt}`}>
      <Icon className={className} />
    </div>
  )
}

export function ScoreBar({ score, threshold }) {
  const pct = Math.max(0, Math.min(100, score * 100))
  const color = threshold != null && score < threshold ? 'bg-amber-400' : 'bg-gradient-to-r from-brand to-indigo-500'
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-brand-soft">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-12 text-right text-xs font-bold text-navy">{score.toFixed(3)}</span>
    </div>
  )
}

export function PageHeader({ title, highlight, subtitle, children }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="section-title">{title} {highlight && <span className="text-brand">{highlight}</span>}</h1>
        {subtitle && <p className="mt-1 text-sm text-ink">{subtitle}</p>}
      </div>
      {children}
    </div>
  )
}
