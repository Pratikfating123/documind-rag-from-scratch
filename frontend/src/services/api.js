import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8001'
export const api = axios.create({ baseURL: BASE_URL, timeout: 120000 })

// Turn any failure into a readable message (backend errors look like {error:{message}}).
api.interceptors.response.use(
  (r) => r,
  (err) => {
    err.userMessage =
      err.response?.data?.error?.message ||
      (err.code === 'ECONNABORTED' ? 'The request timed out. Please try again.' : null) ||
      (!err.response ? 'Cannot reach the backend. Is it running on http://localhost:8001?' : 'Something went wrong.')
    return Promise.reject(err)
  },
)
export const errorMessage = (e) => e?.userMessage || e?.message || 'Something went wrong.'

// Documents
export const listDocuments = (params = {}) => api.get('/api/documents', { params }).then((r) => r.data)
export const uploadDocument = (file, onProgress) => {
  const form = new FormData()
  form.append('file', file)
  return api
    .post('/api/documents/upload', form, {
      onUploadProgress: (e) => e.total && onProgress?.(Math.round((e.loaded * 100) / e.total)),
    })
    .then((r) => r.data)
}
export const deleteDocument = (id) => api.delete(`/api/documents/${id}`)
export const reprocessDocument = (id) => api.post(`/api/documents/${id}/process`).then((r) => r.data)

// Chat
export const askQuestion = (payload) => api.post('/api/chat/ask', payload).then((r) => r.data)
export const listConversations = () => api.get('/api/chat/conversations').then((r) => r.data)
export const getConversation = (id) => api.get(`/api/chat/conversations/${id}`).then((r) => r.data)
export const deleteConversation = (id) => api.delete(`/api/chat/conversations/${id}`)

// Retrieval, dashboard, settings, health
export const retrievalSearch = (payload) => api.post('/api/retrieval/search', payload).then((r) => r.data)
export const getStats = () => api.get('/api/dashboard/stats').then((r) => r.data)
export const getActivity = () => api.get('/api/dashboard/activity').then((r) => r.data)
export const getSettings = () => api.get('/api/settings').then((r) => r.data)
export const updateSettings = (payload) => api.put('/api/settings', payload).then((r) => r.data)
export const getHealth = (testLlm = false) =>
  api.get('/api/health', { params: { test_llm: testLlm } }).then((r) => r.data)
