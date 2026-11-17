import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Cpu, Info, Search } from 'lucide-react'
import SourceCard from '../components/SourceCard.jsx'
import { EmptyState, PageHeader, ScoreBar, Spinner } from '../components/ui.jsx'
import { useToast } from '../context/ToastContext.jsx'
import { errorMessage, getSettings, retrievalSearch } from '../services/api.js'

export default function RetrievalExplorer() {
  const toast = useToast()
  const [query, setQuery] = useState('')
  const [topK, setTopK] = useState(5)
  const [threshold, setThreshold] = useState(0.25)
  const [showAll, setShowAll] = useState(true)
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState(null)

  useEffect(() => {
    getSettings().then((s) => { setTopK(s.top_k); setThreshold(s.similarity_threshold) }).catch(() => {})
  }, [])

  const run = async () => {
    if (!query.trim()) return
    setLoading(true)
    try { setData(await retrievalSearch({ query: query.trim(), top_k: topK, threshold, include_below_threshold: showAll })) }
    catch (e) { toast(errorMessage(e), 'error') }
    finally { setLoading(false) }
  }

  const chart = data?.results.map((r) => ({ name: `#${r.rank} ${r.document_name.slice(0, 16)}`, score: r.score })) || []

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <PageHeader title="Retrieval" highlight="Explorer" subtitle="See exactly how the question is turned into a vector and which chunks win. No LLM is called here." />

      <div className="card p-4">
        <div className="flex flex-col gap-2 sm:flex-row">
          <input value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && run()} placeholder="Enter a search query, e.g. what is overfitting?" className="input flex-1" />
          <button className="btn-primary" onClick={run} disabled={loading || !query.trim()}>{loading ? <Spinner className="h-4 w-4 !text-white" /> : <Search className="h-4 w-4" />} Search</button>
        </div>
        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          <label className="text-xs font-semibold text-navy">Top K: <b className="text-brand">{topK}</b>
            <input type="range" min="1" max="10" value={topK} onChange={(e) => setTopK(+e.target.value)} className="mt-1 w-full accent-brand" /></label>
          <label className="text-xs font-semibold text-navy">Similarity threshold: <b className="text-brand">{threshold.toFixed(2)}</b>
            <input type="range" min="0" max="1" step="0.01" value={threshold} onChange={(e) => setThreshold(+e.target.value)} className="mt-1 w-full accent-brand" /></label>
          <label className="flex items-center gap-2 self-end text-xs font-semibold text-navy">
            <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} className="accent-brand" /> Also show chunks below the threshold
          </label>
        </div>
      </div>

      {!data && !loading && <div className="card mt-6"><EmptyState icon={Search} title="Run a search to inspect retrieval" text="Try a question related to one of your uploaded documents." /></div>}

      {data && (
        <div className="mt-6 space-y-6">
          <div className="grid gap-4 lg:grid-cols-3">
            <div className="card p-5 lg:col-span-1">
              <h3 className="mb-3 flex items-center gap-2 font-bold"><Cpu className="h-4 w-4 text-brand" /> Query embedding</h3>
              <ul className="space-y-1.5 text-sm">
                <li className="flex justify-between"><span>Model</span><b className="truncate pl-2 text-navy">{data.query_embedding.model.split('/').pop()}</b></li>
                <li className="flex justify-between"><span>Dimensions</span><b className="text-navy">{data.query_embedding.dimension}</b></li>
                <li className="flex justify-between"><span>L2 norm</span><b className="text-navy">{data.query_embedding.l2_norm}</b></li>
                <li className="flex justify-between"><span>Vectors searched</span><b className="text-navy">{data.total_vectors}</b></li>
              </ul>
              <p className="mt-3 text-xs font-semibold text-navy">First 8 values</p>
              <div className="mt-1 flex h-14 items-center gap-1">
                {data.query_embedding.preview.map((v, i) => (
                  <div key={i} className="flex flex-1 flex-col items-center justify-center" title={v}>
                    <div className={`w-full rounded-sm ${v >= 0 ? 'bg-brand' : 'bg-indigo-300'}`} style={{ height: `${Math.max(4, Math.min(100, Math.abs(v) * 400))}%` }} />
                  </div>
                ))}
              </div>
              <p className="mt-3 flex gap-1 text-xs text-ink"><Info className="mt-0.5 h-3.5 w-3.5 shrink-0" /> Vectors are normalised to length 1, so cosine similarity equals the dot product.</p>
            </div>

            <div className="card p-5 lg:col-span-2">
              <h3 className="mb-3 font-bold">Retrieval ranking</h3>
              {chart.length === 0 ? <p className="py-10 text-center text-sm text-ink">No chunk scored above the threshold. Lower it or show chunks below the threshold.</p> : (
                <div style={{ height: Math.max(160, chart.length * 44) }}><ResponsiveContainer>
                  <BarChart data={chart} layout="vertical" margin={{ left: 10, right: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E0E6F7" horizontal={false} />
                    <XAxis type="number" domain={[0, 1]} tick={{ fontSize: 10 }} /><YAxis type="category" dataKey="name" width={130} tick={{ fontSize: 11 }} />
                    <Tooltip /><ReferenceLine x={data.threshold} stroke="#F59E0B" strokeDasharray="4 4" label={{ value: 'threshold', fontSize: 10, fill: '#F59E0B', position: 'top' }} />
                    <Bar dataKey="score" fill="#3C65F5" radius={[0, 6, 6, 0]} />
                  </BarChart></ResponsiveContainer></div>
              )}
            </div>
          </div>

          {data.results.length > 0 && (<>
            <div className="card overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-brand-tint text-xs uppercase text-ink"><tr><th className="p-3">Rank</th><th className="p-3">Document</th><th className="p-3">Page / section</th><th className="p-3">Chunk</th><th className="w-56 p-3">Similarity</th><th className="p-3">Passes</th></tr></thead>
                <tbody className="divide-y divide-line">
                  {data.results.map((r) => (
                    <tr key={r.chunk_id}>
                      <td className="p-3 font-bold text-brand">#{r.rank}</td><td className="p-3 font-semibold text-navy">{r.document_name}</td>
                      <td className="p-3">{r.page_number ? `Page ${r.page_number}` : r.section || '—'}</td><td className="p-3">#{r.chunk_index}</td>
                      <td className="p-3"><ScoreBar score={r.score} threshold={data.threshold} /></td>
                      <td className="p-3">{r.passes_threshold ? <span className="text-emerald-600">Yes</span> : <span className="text-amber-600">No</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              {data.results.map((r) => (
                <div key={r.chunk_id} className="space-y-2">
                  <SourceCard source={r} threshold={data.threshold} />
                  <p className="rounded-lg bg-brand-tint p-2 text-xs text-navy"><b>Why retrieved:</b> {r.explanation}</p>
                  <p className="break-all px-1 text-[11px] text-ink">chunk_id: {r.chunk_id}</p>
                </div>
              ))}
            </div>
          </>)}
        </div>
      )}
    </div>
  )
}
