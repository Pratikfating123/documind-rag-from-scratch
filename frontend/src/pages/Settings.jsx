import { useCallback, useEffect, useState } from 'react'
import { CheckCircle2, Cpu, Database, KeyRound, Save, Server, Wifi, XCircle } from 'lucide-react'
import { PageHeader, Spinner } from '../components/ui.jsx'
import { useToast } from '../context/ToastContext.jsx'
import { errorMessage, getHealth, getSettings, updateSettings } from '../services/api.js'

function Row({ label, ok, text }) {
  return (
    <div className="flex items-center justify-between border-b border-line py-2.5 last:border-0">
      <span className="text-sm">{label}</span>
      <span className={`flex items-center gap-1 text-sm font-bold ${ok === false ? 'text-red-600' : ok ? 'text-emerald-600' : 'text-navy'}`}>
        {ok === true && <CheckCircle2 className="h-4 w-4" />}{ok === false && <XCircle className="h-4 w-4" />}{text}
      </span>
    </div>
  )
}

export default function Settings() {
  const toast = useToast()
  const [cfg, setCfg] = useState(null)
  const [form, setForm] = useState(null)
  const [health, setHealth] = useState(null)
  const [healthErr, setHealthErr] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)

  const loadAll = useCallback(async () => {
    try {
      const [s, h] = await Promise.all([getSettings(), getHealth()])
      setCfg(s); setForm({ chunk_size: s.chunk_size, chunk_overlap: s.chunk_overlap, top_k: s.top_k, similarity_threshold: s.similarity_threshold, llm_model: s.llm_model })
      setHealth(h); setHealthErr(false)
    } catch (e) { setHealthErr(true); toast(errorMessage(e), 'error') }
  }, [toast])
  useEffect(() => { loadAll() }, [loadAll])

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))
  const save = async () => {
    setSaving(true)
    try { const r = await updateSettings(form); setCfg(r); toast(r.note || 'Settings saved.') }
    catch (e) { toast(errorMessage(e), 'error') }
    finally { setSaving(false) }
  }
  const test = async () => {
    setTesting(true)
    try { setHealth(await getHealth(true)) } catch (e) { toast(errorMessage(e), 'error') } finally { setTesting(false) }
  }

  if (healthErr && !cfg) return <div className="mx-auto max-w-3xl p-8"><div className="rounded-lg bg-red-50 p-4 text-sm text-red-600">Cannot reach the backend. Start it with <code>uvicorn app.main:app --reload</code> in the backend folder.</div></div>
  if (!cfg || !form) return <div className="flex justify-center py-20"><Spinner className="h-8 w-8" /></div>

  const field = (label, key, props) => (
    <label className="block text-xs font-semibold text-navy">{label}
      <input className="input mt-1" value={form[key]} onChange={(e) => set(key, props?.type === 'number' ? +e.target.value : e.target.value)} {...props} />
    </label>
  )

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
      <PageHeader title="" highlight="Settings" subtitle="Tune retrieval behaviour and check that every part of the pipeline is connected." />
      <div className="grid gap-4 md:grid-cols-2">
        <div className="card p-5">
          <h3 className="mb-2 flex items-center gap-2 font-bold"><Server className="h-4 w-4 text-brand" /> System status</h3>
          <Row label="Backend" ok={health?.status === 'ok'} text={health?.status === 'ok' ? 'Healthy' : 'Degraded'} />
          <Row label="Database" ok={health?.database === 'ok'} text={health?.database === 'ok' ? 'Connected' : 'Error'} />
          <Row label="Embedding model" ok={health?.embedding_model_loaded} text={health?.embedding_model_loaded ? 'Loaded' : 'Loads on first use'} />
          <Row label="Vectors indexed" text={health?.vectors_indexed ?? 0} />
          <Row label="Groq API key" ok={health?.groq_configured} text={health?.groq_configured ? 'Configured' : 'Missing'} />
          {health?.groq_connection && <Row label="Groq connection" ok={health.groq_connection.ok} text={health.groq_connection.message} />}
          <button className="btn-soft mt-3" onClick={test} disabled={testing}>{testing ? <Spinner className="h-3.5 w-3.5" /> : <Wifi className="h-3.5 w-3.5" />} Test Groq connection</button>
        </div>

        <div className="card p-5">
          <h3 className="mb-2 flex items-center gap-2 font-bold"><Cpu className="h-4 w-4 text-brand" /> Models</h3>
          <Row label="Embedding model" text={cfg.embedding_model.split('/').pop()} />
          <Row label="LLM provider" text={cfg.llm_provider} />
          <div className="mt-3">{field('Groq model name', 'llm_model')}</div>
          <p className="mt-3 flex items-start gap-1 text-xs text-ink"><KeyRound className="mt-0.5 h-3.5 w-3.5 shrink-0" /> The API key lives only in <code>backend/.env</code> and is never sent to the browser. The embedding model is changed there too (requires reprocessing documents).</p>
        </div>

        <div className="card p-5 md:col-span-2">
          <h3 className="mb-3 flex items-center gap-2 font-bold"><Database className="h-4 w-4 text-brand" /> Chunking &amp; retrieval</h3>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {field('Chunk size (words)', 'chunk_size', { type: 'number', min: 50, max: 2000 })}
            {field('Chunk overlap (words)', 'chunk_overlap', { type: 'number', min: 0, max: 1000 })}
            {field('Top K', 'top_k', { type: 'number', min: 1, max: 20 })}
            {field('Similarity threshold', 'similarity_threshold', { type: 'number', min: 0, max: 1, step: 0.01 })}
          </div>
          <p className="mt-3 text-xs text-ink">Chunk size and overlap apply to documents processed after saving. Use “Reprocess” in the Knowledge Base to rebuild existing documents.</p>
          <button className="btn-primary mt-4" onClick={save} disabled={saving}>{saving ? <Spinner className="h-4 w-4 !text-white" /> : <Save className="h-4 w-4" />} Save changes</button>
        </div>
      </div>
    </div>
  )
}
