const API_BASE = import.meta.env.VITE_API_BASE || '/api'
const REQUEST_TIMEOUT_MS = 15 * 60 * 1000 // OCR on CPU can take minutes per page

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

async function postForm(path, formData) {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)

  let res
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    })
  } catch (err) {
    if (err.name === 'AbortError') {
      throw new Error(
        `No response after ${REQUEST_TIMEOUT_MS / 60000} minutes. Check backend/logs/backend.log for what's happening.`,
      )
    }
    throw new Error(`Could not reach the backend (${err.message}). Is docker compose still running?`)
  } finally {
    clearTimeout(timeoutId)
  }

  return handleResponse(res)
}

export async function compareLetters(clientFile, mizuhoFile) {
  const formData = new FormData()
  formData.append('client_file', clientFile)
  formData.append('mizuho_file', mizuhoFile)
  return postForm('/compare', formData)
}

export async function extractKyc(file) {
  const formData = new FormData()
  formData.append('file', file)
  return postForm('/extract-kyc', formData)
}
