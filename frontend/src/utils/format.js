export function formatBytes(bytes = 0) {
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB']
  let i = -1
  do { bytes /= 1024; i++ } while (bytes >= 1024 && i < units.length - 1)
  return `${bytes.toFixed(1)} ${units[i]}`
}

// The backend sends naive UTC timestamps; add "Z" so the browser converts to local time.
export const parseDate = (d) => new Date(/[zZ]$|[+-]\d\d:\d\d$/.test(d) ? d : `${d}Z`)
export const formatDate = (d) => parseDate(d).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })

export function timeAgo(d) {
  const s = Math.max(0, (Date.now() - parseDate(d).getTime()) / 1000)
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`
  return `${Math.floor(s / 86400)} d ago`
}
