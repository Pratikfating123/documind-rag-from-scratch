import { useCallback, useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { AlertTriangle, Bot, ChevronDown, Copy, FileText, History, MessageSquarePlus, Send, Sparkles, Trash2, User } from 'lucide-react'
import Markdown from '../components/Markdown.jsx'
import SourceCard from '../components/SourceCard.jsx'
import { EmptyState } from '../components/ui.jsx'
import { useToast } from '../context/ToastContext.jsx'
import { useDocuments } from '../hooks/useDocuments.js'
import { askQuestion, deleteConversation, errorMessage, getConversation, listConversations } from '../services/api.js'
import { timeAgo } from '../utils/format.js'

const SUGGESTED = ['What are the three parts of the CIA triad?', 'What is overfitting and how can it be reduced?', 'What is the difference between narrow AI and general AI?', 'Explain precision and recall.']

export default function Chat() {
  const toast = useToast()
  const location = useLocation()
  const navigate = useNavigate()
  const { documents } = useDocuments()
  const processed = documents.filter((d) => d.processing_status === 'processed')

  const [conversations, setConversations] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [scope, setScope] = useState('all')
  const [selected, setSelected] = useState([])
  const [showSide, setShowSide] = useState(false)
  const [showDocs, setShowDocs] = useState(false)
  const bottomRef = useRef(null)
  const handledNav = useRef(false)

  const loadConversations = useCallback(() => listConversations().then(setConversations).catch(() => {}), [])
  useEffect(() => { loadConversations() }, [loadConversations])
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, loading])

  const send = async (text, idsOverride) => {
    const q = text.trim()
    if (!q || loading) return
    const ids = idsOverride ?? (scope === 'selected' ? selected : [])
    if (scope === 'selected' && idsOverride === undefined && ids.length === 0) {
      toast('Select at least one document, or switch to "All documents".', 'error')
      return
    }
    setMessages((m) => [...m, { role: 'user', content: q }])
    setInput('')
    setLoading(true)
    try {
      const res = await askQuestion({ question: q, conversation_id: activeId, document_ids: ids.length ? ids : null })
      setActiveId(res.conversation_id)
      setMessages((m) => [...m, { role: 'assistant', content: res.answer, sources: res.sources, hasAnswer: res.has_answer }])
      loadConversations()
    } catch (e) {
      const msg = errorMessage(e)
      setMessages((m) => [...m, { role: 'assistant', content: msg, sources: [], error: true }])
      toast(msg, 'error')
    } finally { setLoading(false) }
  }

  // A question sent from the Dashboard search card.
  useEffect(() => {
    const st = location.state
    if (!st?.question || handledNav.current) return
    handledNav.current = true
    if (st.documentIds?.length) { setScope('selected'); setSelected(st.documentIds) }
    navigate('/chat', { replace: true, state: null })
    send(st.question, st.documentIds || [])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const openConversation = async (id) => {
    try {
      const c = await getConversation(id)
      setActiveId(id)
      setMessages(c.messages.map((m) => ({ role: m.role, content: m.content, sources: m.sources, hasAnswer: m.sources.length > 0 })))
      setShowSide(false)
    } catch (e) { toast(errorMessage(e), 'error') }
  }
  const newConversation = () => { setActiveId(null); setMessages([]); setShowSide(false) }
  const removeConversation = async (id) => {
    if (!window.confirm('Delete this conversation?')) return
    try {
      await deleteConversation(id)
      if (id === activeId) newConversation()
      loadConversations()
    } catch (e) { toast(errorMessage(e), 'error') }
  }
  const copy = (text) => navigator.clipboard.writeText(text).then(() => toast('Copied to clipboard.')).catch(() => toast('Could not copy.', 'error'))
  const toggleDoc = (id) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]))

  return (
    <div className="mx-auto grid h-[calc(100vh-7.5rem)] min-h-[520px] max-w-7xl gap-4 px-4 py-4 sm:px-6 lg:grid-cols-[260px_1fr]">
      {/* Conversation history */}
      <aside className={`card flex-col overflow-hidden ${showSide ? 'flex' : 'hidden'} lg:flex`}>
        <div className="p-3"><button className="btn-primary w-full" onClick={newConversation}><MessageSquarePlus className="h-4 w-4" /> New conversation</button></div>
        <p className="px-4 pb-1 text-xs font-bold uppercase tracking-wide text-ink">History</p>
        <div className="flex-1 space-y-1 overflow-y-auto px-2 pb-2">
          {conversations.length === 0 && <p className="px-2 py-4 text-sm text-ink">No conversations yet.</p>}
          {conversations.map((c) => (
            <div key={c.id} className={`group flex items-center gap-1 rounded-lg px-2 py-2 ${c.id === activeId ? 'bg-brand-tint' : 'hover:bg-brand-tint'}`}>
              <button className="min-w-0 flex-1 text-left" onClick={() => openConversation(c.id)}>
                <p className="truncate text-sm font-semibold text-navy">{c.title}</p>
                <p className="text-xs text-ink">{timeAgo(c.updated_at)}</p>
              </button>
              <button onClick={() => removeConversation(c.id)} aria-label="Delete conversation" className="text-gray-400 hover:text-red-500"><Trash2 className="h-4 w-4" /></button>
            </div>
          ))}
        </div>
      </aside>

      {/* Chat area */}
      <section className="card flex min-h-0 flex-col overflow-hidden">
        <div className="flex flex-wrap items-center gap-2 border-b border-line p-3">
          <button className="btn-ghost lg:hidden" onClick={() => setShowSide(!showSide)}><History className="h-4 w-4" /> History</button>
          <div className="flex rounded-lg border border-line p-0.5 text-xs font-semibold">
            <button onClick={() => setScope('all')} className={`rounded-md px-3 py-1.5 ${scope === 'all' ? 'bg-brand text-white' : 'text-navy'}`}>All documents</button>
            <button onClick={() => setScope('selected')} className={`rounded-md px-3 py-1.5 ${scope === 'selected' ? 'bg-brand text-white' : 'text-navy'}`}>Selected</button>
          </div>
          {scope === 'selected' && (
            <div className="relative">
              <button className="btn-ghost" onClick={() => setShowDocs(!showDocs)}>{selected.length} selected <ChevronDown className="h-3.5 w-3.5" /></button>
              {showDocs && (
                <div className="card absolute left-0 top-10 z-20 max-h-64 w-72 overflow-y-auto p-2 shadow-lift">
                  {processed.length === 0 && <p className="p-2 text-xs text-ink">No processed documents yet.</p>}
                  {processed.map((d) => (
                    <label key={d.id} className="flex cursor-pointer items-center gap-2 rounded-md p-2 text-sm hover:bg-brand-tint">
                      <input type="checkbox" checked={selected.includes(d.id)} onChange={() => toggleDoc(d.id)} className="accent-brand" />
                      <span className="truncate text-navy">{d.filename}</span>
                    </label>
                  ))}
                </div>
              )}
            </div>
          )}
          <button className="btn-ghost ml-auto" disabled={messages.length === 0} onClick={() => (activeId ? removeConversation(activeId) : newConversation())}>
            <Trash2 className="h-3.5 w-3.5" /> Clear conversation
          </button>
        </div>

        <div className="flex-1 space-y-6 overflow-y-auto p-4">
          {messages.length === 0 && !loading && (
            <EmptyState icon={Sparkles} title="Ask anything about your documents" text={processed.length ? 'Answers are grounded in your uploaded documents and come with sources.' : 'Upload and process a document in the Knowledge Base first.'}>
              <div className="flex max-w-xl flex-wrap justify-center gap-2">
                {SUGGESTED.map((s) => <button key={s} className="pill" onClick={() => send(s)}>{s}</button>)}
              </div>
            </EmptyState>
          )}

          {messages.map((m, i) => m.role === 'user' ? (
            <div key={i} className="flex justify-end gap-2">
              <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-brand px-4 py-2.5 text-sm text-white">{m.content}</div>
              <span className="mt-1 hidden h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-soft text-brand sm:flex"><User className="h-4 w-4" /></span>
            </div>
          ) : (
            <div key={i} className="flex gap-2">
              <span className="mt-1 hidden h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand to-indigo-500 text-white sm:flex"><Bot className="h-4 w-4" /></span>
              <div className="min-w-0 flex-1">
                <div className={`rounded-2xl rounded-tl-sm border p-4 ${m.error ? 'border-red-200 bg-red-50' : 'border-line bg-brand-tint/50'}`}>
                  {m.error && <p className="mb-1 flex items-center gap-1 text-xs font-bold text-red-600"><AlertTriangle className="h-3.5 w-3.5" /> Something went wrong</p>}
                  {!m.error && m.hasAnswer === false && <p className="mb-2 flex items-center gap-1 rounded-md bg-amber-50 px-2 py-1 text-xs font-semibold text-amber-700"><AlertTriangle className="h-3.5 w-3.5" /> No relevant passages were found in the selected documents.</p>}
                  <Markdown>{m.content}</Markdown>
                  {!m.error && <button onClick={() => copy(m.content)} className="mt-2 flex items-center gap-1 text-xs font-semibold text-brand"><Copy className="h-3.5 w-3.5" /> Copy response</button>}
                </div>
                {m.sources?.length > 0 && (
                  <div className="mt-3">
                    <p className="mb-2 flex items-center gap-1 text-xs font-bold uppercase tracking-wide text-ink"><FileText className="h-3.5 w-3.5" /> Retrieved sources ({m.sources.length})</p>
                    <div className="grid gap-2 sm:grid-cols-2">{m.sources.map((s) => <SourceCard key={s.chunk_id} source={s} />)}</div>
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-brand to-indigo-500 text-white"><Bot className="h-4 w-4" /></span>
              <div className="flex items-center gap-1 rounded-2xl border border-line bg-brand-tint/50 px-4 py-3" aria-label="Thinking">
                {[0, 1, 2].map((n) => <i key={n} className="h-2 w-2 animate-bounce rounded-full bg-brand" style={{ animationDelay: `${n * 0.15}s` }} />)}
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="border-t border-line p-3">
          <div className="flex items-end gap-2">
            <textarea value={input} rows={1} onChange={(e) => setInput(e.target.value)} placeholder="Ask a question about your documents…"
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input) } }}
              className="input max-h-32 resize-none" />
            <button className="btn-primary h-[42px]" disabled={loading || !input.trim()} onClick={() => send(input)} aria-label="Send"><Send className="h-4 w-4" /></button>
          </div>
          <p className="mt-1 text-center text-[11px] text-ink">Answers use only retrieved document content. Press Enter to send, Shift+Enter for a new line.</p>
        </div>
      </section>
    </div>
  )
}
