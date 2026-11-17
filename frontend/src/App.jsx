import { Navigate, Route, Routes } from 'react-router-dom'
import MainLayout from './layouts/MainLayout.jsx'
import Dashboard from './pages/Dashboard.jsx'
import KnowledgeBase from './pages/KnowledgeBase.jsx'
import Chat from './pages/Chat.jsx'
import RetrievalExplorer from './pages/RetrievalExplorer.jsx'
import Settings from './pages/Settings.jsx'

export default function App() {
  return (
    <Routes>
      <Route element={<MainLayout />}>
        <Route index element={<Dashboard />} />
        <Route path="knowledge-base" element={<KnowledgeBase />} />
        <Route path="chat" element={<Chat />} />
        <Route path="retrieval" element={<RetrievalExplorer />} />
        <Route path="settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
