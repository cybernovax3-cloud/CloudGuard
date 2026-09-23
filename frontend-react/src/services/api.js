const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL
const baseUrl = configuredBaseUrl || (window.location.port === '5173' ? 'http://127.0.0.1:5000' : window.location.origin)

async function request(path, options = {}) {
  const response = await fetch(`${baseUrl}${path}`, { cache: 'no-store', ...options })
  if (!response.ok) throw new Error(`${response.status} ${path}`)
  return response.json()
}

export const api = { baseUrl, get: path => request(path), post: (path, body) => request(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }) }