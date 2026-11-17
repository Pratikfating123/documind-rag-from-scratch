import { useCallback, useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { Box, Library, LayoutDashboard, Menu, MessageSquare, Search, Settings as Cog, X } from 'lucide-react'
import { getHealth } from '../services/api.js'
import { usePolling } from '../hooks/usePolling.js'

const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/knowledge-base', label: 'Knowledge Base', icon: Library },
  { to: '/chat', label: 'AI Chat', icon: MessageSquare },
  { to: '/retrieval', label: 'Retrieval Explorer', icon: Search },
  { to: '/settings', label: 'Settings', icon: Cog },
]

export default function MainLayout() {
  const [open, setOpen] = useState(false)
  const [online, setOnline] = useState(null)
  const check = useCallback(() => getHealth().then(() => setOnline(true)).catch(() => setOnline(false)), [])
  useEffect(() => { check() }, [check])
  usePolling(check, 15000)

  const linkCls = ({ isActive }) =>
    `flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold transition ${isActive ? 'bg-brand-tint text-brand' : 'text-navy hover:text-brand'}`

  return (
    <div className="flex min-h-screen flex-col bg-white">
      <header className="sticky top-0 z-40 border-b border-line bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6">
          <NavLink to="/" className="flex items-center gap-2 text-xl font-extrabold text-navy">
            <Box className="h-7 w-7 text-brand" /> DocuMind
          </NavLink>
          <nav className="hidden items-center gap-1 lg:flex">
            {NAV.map((n) => <NavLink key={n.to} to={n.to} end={n.to === '/'} className={linkCls}><n.icon className="h-4 w-4" />{n.label}</NavLink>)}
          </nav>
          <div className="flex items-center gap-3">
            <span className={`hidden items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold sm:inline-flex ${online === false ? 'bg-red-50 text-red-600' : 'bg-brand-tint text-brand'}`}>
              <span className={`h-2 w-2 rounded-full ${online === false ? 'bg-red-500' : online ? 'bg-emerald-500' : 'bg-gray-300'}`} />
              {online === false ? 'Backend offline' : online ? 'Backend online' : 'Connecting…'}
            </span>
            <button className="lg:hidden" onClick={() => setOpen(!open)} aria-label="Menu">
              {open ? <X className="h-6 w-6 text-navy" /> : <Menu className="h-6 w-6 text-navy" />}
            </button>
          </div>
        </div>
        {open && (
          <nav className="flex flex-col gap-1 border-t border-line bg-white p-3 lg:hidden">
            {NAV.map((n) => <NavLink key={n.to} to={n.to} end={n.to === '/'} onClick={() => setOpen(false)} className={linkCls}><n.icon className="h-4 w-4" />{n.label}</NavLink>)}
          </nav>
        )}
      </header>
      <main className="flex-1"><Outlet /></main>
      <footer className="border-t border-line py-4 text-center text-xs text-ink">DocuMind · RAG from Scratch · built with FastAPI, NumPy &amp; Sentence Transformers</footer>
    </div>
  )
}
