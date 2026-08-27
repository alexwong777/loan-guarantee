const API_BASE = import.meta.env.VITE_API_BASE || '/api'
const POLL_INTERVAL_MS = 1000
const JOB_TIMEOUT_MS = 15 * 60 * 1000 // OCR on CPU can take minutes per page

async function postForm(path, formData) {
  let res
  try {
    res = await fetch(`${API_BASE}${path}`, { method: 'POST', body: formData })
  } catch (err) {
    throw new Error(`Could not reach the backend (${err.message}). Is docker compose still running?`)
  }
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

async function fetchJobStatus(jobId) {
  let res
  try {
    res = await fetch(`${API_BASE}/jobs/${jobId}`)
  } catch (err) {
    throw new Error(`Could not reach the backend (${err.message}). Is docker compose still running?`)
  }
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

function stopJob(jobId) {
  fetch(`${API_BASE}/jobs/${jobId}/stop`, { method: 'POST' }).catch(() => {
    // best-effort - the poll loop stops client-side regardless
  })
}

function userStopError() {
  const err = new Error('Stopped.')
  err.isUserStop = true
  return err
}

async function runJob(startPath, formData, { signal, onProgress } = {}) {
  const { job_id: jobId } = await postForm(startPath, formData)
  const startedAt = Date.now()

  // eslint-disable-next-line no-constant-condition
  while (true) {
    if (signal?.aborted) {
      stopJob(jobId)
      throw userStopError()
    }
    if (Date.now() - startedAt > JOB_TIMEOUT_MS) {
      stopJob(jobId)
      throw new Error(`No response after ${JOB_TIMEOUT_MS / 60000} minutes. Check backend/logs/backend.log.`)
    }

    const status = await fetchJobStatus(jobId)
    onProgress?.(status)

    if (status.status === 'done') return status.result
    if (status.status === 'error') throw new Error(status.error || 'OCR failed.')
    if (status.status === 'cancelled') throw userStopError()

    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS))
  }
}

export async function compareLetters(clientFile, mizuhoFile, opts) {
  const formData = new FormData()
  formData.append('client_file', clientFile)
  formData.append('mizuho_file', mizuhoFile)
  return runJob('/compare/start', formData, opts)
}

export async function extractKyc(file, opts) {
  const formData = new FormData()
  formData.append('file', file)
  return runJob('/extract-kyc/start', formData, opts)
}
