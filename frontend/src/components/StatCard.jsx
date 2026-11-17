export default function StatCard({ icon: Icon, label, value, hint }) {
  return (
    <div className="card flex items-center gap-4 p-4 transition hover:shadow-lift">
      <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-brand-tint text-brand">
        <Icon className="h-6 w-6" />
      </div>
      <div className="min-w-0">
        <p className="truncate text-sm font-bold text-navy">{label}</p>
        <p className="text-2xl font-extrabold text-brand">{value}</p>
        {hint && <p className="truncate text-xs text-ink">{hint}</p>}
      </div>
    </div>
  )
}
