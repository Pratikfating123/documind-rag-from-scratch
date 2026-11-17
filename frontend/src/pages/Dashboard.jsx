import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Activity, Boxes, CheckCircle2, Database, FileText, HardDrive, MessageSquare, Search, Upload, Zap } from 'lucide-react'
import StatCard from '../components/StatCard.jsx'
import { EmptyState, Spinner, StatusBadge } from '../components/ui.jsx'
import { useDocuments } from '../hooks/useDocuments.js'
import { usePolling } from '../hooks/usePolling.js'
import { errorMessage, getActivity, getStats } from '../services/api.js'
import { formatBytes, timeAgo } from '../utils/format.js'

const PIE_COLORS = { processed: '#10B981', processing: '#3C65F5', uploaded: '#F59E0B', failed: '#EF4444' }
const SUGGESTIONS = ['What is the CIA triad?', 'Explain overfitting', 'What is narrow AI?', 'How does RAG reduce hallucination?']
const PIPELINE_TEXT = {
  ready: ['Ready', 'text-emerald-600 bg-emerald-50'],
  needs_api_key: ['Add GROQ_API_KEY', 'text-amber-600 bg-amber-50'],
  no_documents: ['Upload a document', 'text-brand bg-brand-soft'],
}

export default function Dashboard() {
  const navigate = useNavigate()
  const { documents } = useDocuments()
  const [stats, setStats] = useState(null)
  const [activity, setActivity] = useState(null)
  const [error, setError] = useState(null)
  const [question, setQuestion] = useState('')
  const [docId, setDocId] = useState('all')

  const load = useCallback(async () => {
    try {
      const [s, a] = await Promise.all([getStats(), getActivity()])
      setStats(s); setActivity(a); setError(null)
    } catch (e) { setError(errorMessage(e)) }
  }, [])
  useEffect(() => { load() }, [load])
  usePolling(load, 10000)

  const ask = (q = question) => {
    if (!q.trim()) return
    navigate('/chat', { state: { question: q.trim(), documentIds: docId === 'all' ? [] : [docId] } })
  }
  const processedDocs = documents.filter((d) => d.processing_status === 'processed')
  const [pLabel, pCls] = PIPELINE_TEXT[stats?.pipeline.state] || ['Checking…', 'text-ink bg-brand-tint']
  const uploadsTotal = activity?.uploads_per_day.reduce((a, b) => a + b.count, 0) || 0
  const pieData = activity?.processing_stats.filter((s) => s.count > 0) || []
  const short = (d) => d.date.slice(5)

  return (
    <div>
      {/* Hero */}
      <section className="relative overflow-hidden bg-gradient-to-b from-brand-tint to-white">
        <div className="pointer-events-none absolute -right-24 -top-24 h-96 w-96 rounded-full bg-brand-soft/70 blur-2xl" />
        <div className="relative mx-auto max-w-7xl px-4 pb-14 pt-12 sm:px-6">
          <h1 className="max-w-2xl text-4xl font-extrabold leading-tight sm:text-5xl">
            The <span className="rounded bg-brand-soft px-1 text-brand">Easiest Way</span><br />to Ask Your Documents
          </h1>
          <p className="mt-4 max-w-xl text-sm text-ink sm:text-base">
            Upload PDFs, Word files and text. DocuMind finds the most relevant passages and answers with sources, so you always know where an answer came from.
          </p>
          <div className="card mt-8 flex max-w-3xl flex-col gap-2 p-2 sm:flex-row sm:items-center">
            <select value={docId} onChange={(e) => setDocId(e.target.value)} className="input sm:w-48" aria-label="Document scope">
              <option value="all">All documents</option>
              {processedDocs.map((d) => <option key={d.id} value={d.id}>{d.filename}</option>)}
            </select>
            <input value={question} onChange={(e) => setQuestion(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && ask()}
              placeholder="Ask a question about your documents…" className="input flex-1" />
            <button className="btn-primary" onClick={() => ask()} disabled={!question.trim()}><Search className="h-4 w-4" /> Ask</button>
          </div>
          <p className="mt-3 text-xs font-semibold text-navy">
            Popular questions:{' '}
            {SUGGESTIONS.map((s) => <button key={s} onClick={() => ask(s)} className="mr-2 font-medium text-ink underline decoration-dotted hover:text-brand">{s}</button>)}
          </p>
        </div>
      </section>

      <div className="mx-auto max-w-7xl space-y-8 px-4 pb-12 sm:px-6">
        {error && <div className="rounded-lg bg-red-50 p-3 text-sm text-red-600">{error}</div>}
        {!stats && !error && <div className="flex justify-center py-10"><Spinner className="h-8 w-8" /></div>}

        {stats && (<>
          <section>
            <h2 className="mb-4 text-xl font-extrabold">Your knowledge at a glance</h2>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard icon={FileText} label="Documents uploaded" value={stats.total_documents} />
              <StatCard icon={CheckCircle2} label="Documents processed" value={stats.processed_documents} />
              <StatCard icon={Boxes} label="Chunks created" value={stats.total_chunks} />
              <StatCard icon={MessageSquare} label="Questions asked" value={stats.total_questions} />
            </div>
          </section>

          <section className="grid gap-4 lg:grid-cols-3">
            <div className="card p-5">
              <h3 className="mb-3 flex items-center gap-2 font-bold"><Zap className="h-4 w-4 text-brand" /> RAG pipeline status</h3>
              <span className={`inline-block rounded-md px-2 py-1 text-xs font-bold ${pCls}`}>{pLabel}</span>
              <ul className="mt-4 space-y-2 text-sm">
                <li className="flex justify-between"><span>Embedding model</span><b className="text-navy">{stats.pipeline.embedding_model_loaded ? 'Loaded' : 'Loads on first use'}</b></li>
                <li className="flex justify-between"><span>Vectors indexed</span><b className="text-navy">{stats.pipeline.vectors_indexed}</b></li>
                <li className="flex justify-between"><span>Groq API key</span><b className="text-navy">{stats.pipeline.llm_configured ? 'Configured' : 'Missing'}</b></li>
              </ul>
            </div>
            <div className="card p-5">
              <h3 className="mb-3 flex items-center gap-2 font-bold"><HardDrive className="h-4 w-4 text-brand" /> Storage usage</h3>
              <p className="text-3xl font-extrabold text-brand">{formatBytes(stats.storage.total_bytes)}</p>
              <ul className="mt-4 space-y-2 text-sm">
                <li className="flex justify-between"><span>Uploaded files</span><b className="text-navy">{formatBytes(stats.storage.uploads_bytes)}</b></li>
                <li className="flex justify-between"><span>Vector store</span><b className="text-navy">{formatBytes(stats.storage.vectors_bytes)}</b></li>
              </ul>
            </div>
            <div className="card flex flex-col justify-between bg-gradient-to-br from-brand to-indigo-600 p-5 text-white">
              <div>
                <h3 className="text-lg font-extrabold !text-white">Let’s Learn<br />from your documents</h3>
                <p className="mt-1 text-xs text-white/80">Quick actions</p>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <button onClick={() => navigate('/knowledge-base')} className="inline-flex items-center gap-1.5 rounded-lg bg-white px-3 py-2 text-xs font-bold text-brand"><Upload className="h-3.5 w-3.5" /> Upload</button>
                <button onClick={() => navigate('/chat')} className="inline-flex items-center gap-1.5 rounded-lg bg-white/20 px-3 py-2 text-xs font-bold text-white hover:bg-white/30"><MessageSquare className="h-3.5 w-3.5" /> Chat</button>
                <button onClick={() => navigate('/retrieval')} className="inline-flex items-center gap-1.5 rounded-lg bg-white/20 px-3 py-2 text-xs font-bold text-white hover:bg-white/30"><Search className="h-3.5 w-3.5" /> Explorer</button>
              </div>
            </div>
          </section>

          {activity && (
            <section className="grid gap-4 lg:grid-cols-3">
              <div className="card p-5">
                <h3 className="mb-3 font-bold">Document uploads (14 days)</h3>
                <div className="h-52"><ResponsiveContainer>
                  <BarChart data={activity.uploads_per_day.map((d) => ({ ...d, label: short(d) }))}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E0E6F7" vertical={false} />
                    <XAxis dataKey="label" tick={{ fontSize: 10 }} interval={2} /><YAxis allowDecimals={false} tick={{ fontSize: 10 }} width={24} />
                    <Tooltip /><Bar dataKey="count" name="Uploads" fill="#3C65F5" radius={[4, 4, 0, 0]} />
                  </BarChart></ResponsiveContainer></div>
                {uploadsTotal === 0 && <p className="mt-1 text-center text-xs text-ink">No uploads in this period yet.</p>}
              </div>
              <div className="card p-5">
                <h3 className="mb-3 font-bold">Questions asked (14 days)</h3>
                <div className="h-52"><ResponsiveContainer>
                  <LineChart data={activity.questions_per_day.map((d) => ({ ...d, label: short(d) }))}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E0E6F7" vertical={false} />
                    <XAxis dataKey="label" tick={{ fontSize: 10 }} interval={2} /><YAxis allowDecimals={false} tick={{ fontSize: 10 }} width={24} />
                    <Tooltip /><Line type="monotone" dataKey="count" name="Questions" stroke="#6366F1" strokeWidth={3} dot={{ r: 3 }} />
                  </LineChart></ResponsiveContainer></div>
              </div>
              <div className="card p-5">
                <h3 className="mb-3 font-bold">Processing statistics</h3>
                {pieData.length === 0 ? <EmptyState icon={Database} title="No documents yet" /> : (
                  <div className="h-52"><ResponsiveContainer>
                    <PieChart><Pie data={pieData} dataKey="count" nameKey="status" innerRadius={45} outerRadius={75} paddingAngle={3}>
                      {pieData.map((s) => <Cell key={s.status} fill={PIE_COLORS[s.status]} />)}</Pie><Tooltip />
                    </PieChart></ResponsiveContainer></div>
                )}
                <div className="mt-1 flex flex-wrap justify-center gap-3 text-xs">
                  {pieData.map((s) => <span key={s.status} className="flex items-center gap-1"><i className="h-2 w-2 rounded-full" style={{ background: PIE_COLORS[s.status] }} />{s.status} ({s.count})</span>)}
                </div>
              </div>
            </section>
          )}

          <section className="card p-5">
            <h3 className="mb-3 flex items-center gap-2 font-bold"><Activity className="h-4 w-4 text-brand" /> Recent activity</h3>
            {!activity?.recent_activity.length ? <EmptyState icon={Activity} title="Nothing yet" text="Upload a document or ask a question to see activity here." /> : (
              <ul className="divide-y divide-line">
                {activity.recent_activity.map((r, i) => (
                  <li key={i} className="flex items-center gap-3 py-2.5">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-tint text-brand">
                      {r.type === 'upload' ? <Upload className="h-4 w-4" /> : <MessageSquare className="h-4 w-4" />}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold text-navy">{r.title}</p>
                      <p className="text-xs text-ink">{r.type === 'upload' ? 'Document uploaded' : 'Question asked'} · {timeAgo(r.time)}</p>
                    </div>
                    {r.status && <StatusBadge status={r.status} />}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>)}
      </div>
    </div>
  )
}
