import { createContext, useCallback, useContext, useState } from 'react'
import { AlertCircle, CheckCircle2, X } from 'lucide-react'

const ToastContext = createContext(null)
export const useToast = () => useContext(ToastContext)

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const dismiss = (id) => setToasts((t) => t.filter((x) => x.id !== id))
  const toast = useCallback((message, type = 'success') => {
    const id = Date.now() + Math.random()
    setToasts((t) => [...t, { id, message, type }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 5000)
  }, [])

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex w-[calc(100%-2rem)] max-w-sm flex-col gap-2">
        {toasts.map((t) => (
          <div key={t.id} className="card flex items-start gap-3 p-3 shadow-lift">
            {t.type === 'error' ? (
              <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-500" />
            ) : (
              <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-500" />
            )}
            <p className="flex-1 text-sm text-navy">{t.message}</p>
            <button onClick={() => dismiss(t.id)} aria-label="Dismiss"><X className="h-4 w-4 text-gray-400" /></button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
