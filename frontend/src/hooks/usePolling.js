import { useEffect, useRef } from 'react'

/** Calls `callback` every `ms` milliseconds while `enabled` is true. */
export function usePolling(callback, ms, enabled = true) {
  const saved = useRef(callback)
  useEffect(() => { saved.current = callback }, [callback])
  useEffect(() => {
    if (!enabled) return undefined
    const id = setInterval(() => saved.current(), ms)
    return () => clearInterval(id)
  }, [ms, enabled])
}
