import { useState } from 'react'
import { ChevronDown, FileText } from 'lucide-react'
import { ScoreBar } from './ui.jsx'

/** One retrieved chunk: document, page, similarity score and expandable text. */
export default function SourceCard({ source, threshold }) {
  const [open, setOpen] = useState(false)
  const where = source.page_number ? `Page ${source.page_number}` : source.section || 'Document'
  return (
    <div className="card p-3">
      <div className="flex items-start gap-2">
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-brand text-xs font-bold text-white">
          {source.label || source.rank}
        </span>
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-1 truncate text-sm font-bold text-navy">
            <FileText className="h-3.5 w-3.5 shrink-0 text-brand" /> {source.document_name}
          </p>
          <p className="text-xs text-ink">{where} · chunk #{source.chunk_index}</p>
        </div>
      </div>
      <div className="mt-2"><ScoreBar score={source.score} threshold={threshold} /></div>
      <button onClick={() => setOpen(!open)} className="mt-2 flex items-center gap-1 text-xs font-semibold text-brand">
        {open ? 'Hide' : 'Show'} retrieved context
        <ChevronDown className={`h-3.5 w-3.5 transition ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && <p className="mt-2 max-h-48 overflow-y-auto whitespace-pre-wrap rounded-lg bg-brand-tint p-2 text-xs leading-relaxed text-navy">{source.content}</p>}
    </div>
  )
}
