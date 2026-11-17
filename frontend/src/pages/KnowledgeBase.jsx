import { useRef, useState } from 'react'
import { AlertCircle, Calendar, FileUp, Layers, RefreshCw, Search, Trash2, UploadCloud } from 'lucide-react'
import { EmptyState, FileIcon, PageHeader, Spinner, StatusBadge } from '../components/ui.jsx'
import { useToast } from '../context/ToastContext.jsx'
import { useDocuments } from '../hooks/useDocuments.js'
import { deleteDocument, errorMessage, reprocessDocument, uploadDocument } from '../services/api.js'
import { formatBytes, formatDate } from '../utils/format.js'

const STATUS_TABS = [['', 'All'], ['processed', 'Processed'], ['processing', 'Processing'], ['uploaded', 'Queued'], ['failed', 'Failed']]
const ALLOWED = ['pdf', 'docx', 'txt']

export default function KnowledgeBase() {
  const toast = useToast()
  const inputRef = useRef(null)
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [fileType, setFileType] = useState('')
  const [dragging, setDragging] = useState(false)
  const [uploads, setUploads] = useState([]) // [{id, name, progress, error}]
  const [busyId, setBusyId] = useState(null)
  const { documents, loading, error, refresh } = useDocuments({ q: search || undefined, status: status || undefined, file_type: fileType || undefined })

  const patchUpload = (id, patch) => setUploads((u) => u.map((x) => (x.id === id ? { ...x, ...patch } : x)))

  const handleFiles = async (fileList) => {
    for (const file of Array.from(fileList)) {
      const id = `${Date.now()}-${Math.random()}`
      const ext = file.name.split('.').pop().toLowerCase()
      if (!ALLOWED.includes(ext)) {
        toast(`"${file.name}" is not supported. Please upload PDF, DOCX or TXT files.`, 'error')
        continue
      }
      setUploads((u) => [...u, { id, name: file.name, progress: 0 }])
      try {
        await uploadDocument(file, (p) => patchUpload(id, { progress: p }))
        toast(`"${file.name}" uploaded. Processing started.`)
        setUploads((u) => u.filter((x) => x.id !== id))
        refresh()
      } catch (e) {
        patchUpload(id, { error: errorMessage(e) })
        toast(errorMessage(e), 'error')
        setTimeout(() => setUploads((u) => u.filter((x) => x.id !== id)), 6000)
      }
    }
  }

  const onDrop = (e) => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files) }

  const onDelete = async (doc) => {
    if (!window.confirm(`Delete "${doc.filename}"? Its chunks and embeddings will be removed too.`)) return
    setBusyId(doc.id)
    try { await deleteDocument(doc.id); toast('Document deleted.'); refresh() } catch (e) { toast(errorMessage(e), 'error') } finally { setBusyId(null) }
  }
  const onReprocess = async (doc) => {
    setBusyId(doc.id)
    try { await reprocessDocument(doc.id); toast('Reprocessing started.'); refresh() } catch (e) { toast(errorMessage(e), 'error') } finally { setBusyId(null) }
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <PageHeader title="Knowledge" highlight="Base" subtitle="Upload documents, then ask questions about them in AI Chat." />

      <div onDragOver={(e) => { e.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={`card cursor-pointer border-2 border-dashed p-8 text-center transition ${dragging ? 'border-brand bg-brand-tint' : 'hover:border-brand'}`}>
        <input ref={inputRef} type="file" multiple accept=".pdf,.docx,.txt" className="hidden" onChange={(e) => { handleFiles(e.target.files); e.target.value = '' }} />
        <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-tint text-brand"><UploadCloud className="h-7 w-7" /></div>
        <p className="font-bold text-navy">Drag &amp; drop files here, or <span className="text-brand">browse</span></p>
        <p className="mt-1 text-xs text-ink">PDF, DOCX or TXT · up to 20 MB each</p>
      </div>

      {uploads.length > 0 && (
        <div className="mt-4 space-y-2">
          {uploads.map((u) => (
            <div key={u.id} className="card p-3">
              <div className="flex items-center justify-between text-sm">
                <span className="flex items-center gap-2 truncate font-semibold text-navy"><FileUp className="h-4 w-4 text-brand" />{u.name}</span>
                <span className={u.error ? 'text-red-600' : 'text-ink'}>{u.error ? 'Failed' : `${u.progress}%`}</span>
              </div>
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-brand-soft">
                <div className={`h-full rounded-full transition-all ${u.error ? 'bg-red-500' : 'bg-brand'}`} style={{ width: `${u.error ? 100 : u.progress}%` }} />
              </div>
              {u.error && <p className="mt-1 flex items-center gap-1 text-xs text-red-600"><AlertCircle className="h-3.5 w-3.5" />{u.error}</p>}
            </div>
          ))}
        </div>
      )}

      <div className="mt-8 flex flex-wrap items-center gap-2">
        {STATUS_TABS.map(([v, label]) => (
          <button key={label} onClick={() => setStatus(v)} className={`pill ${status === v ? 'pill-active' : ''}`}>{label}</button>
        ))}
        <select value={fileType} onChange={(e) => setFileType(e.target.value)} className="input !w-auto" aria-label="File type">
          <option value="">All types</option><option value="pdf">PDF</option><option value="docx">DOCX</option><option value="txt">TXT</option>
        </select>
        <div className="relative ml-auto w-full sm:w-64">
          <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-gray-400" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search documents…" className="input !pl-9" />
        </div>
      </div>

      <div className="mt-5">
        {loading ? <div className="flex justify-center py-12"><Spinner className="h-8 w-8" /></div>
          : error ? <div className="rounded-lg bg-red-50 p-3 text-sm text-red-600">{error}</div>
          : documents.length === 0 ? (
            <div className="card"><EmptyState icon={FileUp} title={search || status || fileType ? 'No documents match your filters' : 'No documents yet'} text="Upload a PDF, DOCX or TXT file to start building your knowledge base." /></div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {documents.map((d) => (
                <div key={d.id} className="card flex flex-col p-4 transition hover:shadow-lift">
                  <div className="flex items-start gap-3">
                    <FileIcon type={d.file_type} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-bold text-navy" title={d.filename}>{d.filename}</p>
                      <p className="text-xs uppercase text-ink">{d.file_type} · {formatBytes(d.file_size)}</p>
                    </div>
                  </div>
                  <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink">
                    <span className="flex items-center gap-1"><Calendar className="h-3.5 w-3.5" />{formatDate(d.upload_date)}</span>
                    <span className="flex items-center gap-1"><Layers className="h-3.5 w-3.5" />{d.total_chunks} chunks</span>
                  </div>
                  <div className="mt-3"><StatusBadge status={d.processing_status} /></div>
                  {d.error_message && d.processing_status === 'failed' && <p className="mt-2 rounded-lg bg-red-50 p-2 text-xs text-red-600">{d.error_message}</p>}
                  <div className="mt-4 flex gap-2 border-t border-line pt-3">
                    <button className="btn-soft flex-1" disabled={busyId === d.id || d.processing_status === 'processing'} onClick={() => onReprocess(d)}>
                      <RefreshCw className={`h-3.5 w-3.5 ${d.processing_status === 'processing' ? 'animate-spin' : ''}`} /> Reprocess
                    </button>
                    <button className="btn-danger" disabled={busyId === d.id || d.processing_status === 'processing'} onClick={() => onDelete(d)} aria-label="Delete"><Trash2 className="h-3.5 w-3.5" /> Delete</button>
                  </div>
                </div>
              ))}
            </div>
          )}
      </div>
    </div>
  )
}
