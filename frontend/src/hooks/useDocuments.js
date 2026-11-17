import { useCallback, useEffect, useState } from 'react'
import { errorMessage, listDocuments } from '../services/api.js'
import { usePolling } from './usePolling.js'

/** Loads documents; auto-refreshes every 2 s while any document is still being processed. */
export function useDocuments(params = {}) {
  const key = JSON.stringify(params)
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const refresh = useCallback(async () => {
    try {
      setDocuments(await listDocuments(JSON.parse(key)))
      setError(null)
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setLoading(false)
    }
  }, [key])

  useEffect(() => { refresh() }, [refresh])
  const busy = documents.some((d) => d.processing_status === 'uploaded' || d.processing_status === 'processing')
  usePolling(refresh, 2000, busy)
  return { documents, loading, error, refresh }
}
