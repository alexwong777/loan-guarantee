const API_BASE = import.meta.env.VITE_API_BASE || '/api'

async function handleResponse(res) {
  if (!res.ok) {
    let message = `Request failed (${res.status})`
    try {
      const data = await res.json()
      message = data.detail || message
    } catch {
      // response body wasn't JSON - keep the generic message
    }
    throw new Error(message)
  }
  return res.json()
}

export async function compareLetters(clientFile, mizuhoFile) {
  const formData = new FormData()
  formData.append('client_file', clientFile)
  formData.append('mizuho_file', mizuhoFile)
  const res = await fetch(`${API_BASE}/compare`, { method: 'POST', body: formData })
  return handleResponse(res)
}

export async function extractKyc(file) {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`${API_BASE}/extract-kyc`, { method: 'POST', body: formData })
  return handleResponse(res)
}
