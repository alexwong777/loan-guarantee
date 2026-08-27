import { useEffect, useState } from 'react'
import { extractKyc } from '../api.js'
import UploadZone from './UploadZone.jsx'

const CACHE_KEY = 'lg_kyc_cache'

const FIELD_LABELS = {
  document_type: 'Document Type',
  full_name: 'Full Name',
  id_number: 'ID Number',
  passport_number: 'Passport Number',
  date_of_birth: 'Date of Birth',
  nationality: 'Nationality',
  gender: 'Gender',
  address: 'Address',
  company_name: 'Company Name',
  registration_number: 'Registration Number',
  incorporation_date: 'Incorporation Date',
  issue_date: 'Issue Date',
  expiry_date: 'Expiry Date',
  issuing_authority: 'Issuing Authority',
  place_of_birth: 'Place of Birth',
  phone_number: 'Phone Number',
  email: 'Email',
  bank_name: 'Bank Name',
  account_number: 'Account Number',
}

function formatLabel(key) {
  return FIELD_LABELS[key] || key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

function loadCache() {
  try {
    const raw = localStorage.getItem(CACHE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function saveCache(entry) {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(entry))
  } catch {
    // storage unavailable/full - caching is a convenience only, safe to skip
  }
}

export default function KycPanel() {
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [info, setInfo] = useState(null)
  const [result, setResult] = useState(null)
  const [showRaw, setShowRaw] = useState(false)
  const [cachedName, setCachedName] = useState(null)
  const [stopController, setStopController] = useState(null)

  useEffect(() => {
    const cached = loadCache()
    if (cached) {
      setResult(cached.result)
      setCachedName({ name: cached.fileName, savedAt: cached.savedAt })
    }
  }, [])

  async function handleExtract() {
    const controller = new AbortController()
    setStopController(controller)
    setLoading(true)
    setError(null)
    setInfo(null)
    setResult(null)
    try {
      const data = await extractKyc(file, controller.signal)
      setResult(data)
      setCachedName(null)
      saveCache({ result: data, fileName: file.name, savedAt: Date.now() })
    } catch (err) {
      if (err.isUserStop) setInfo('Stopped.')
      else setError(err.message)
    } finally {
      setLoading(false)
      setStopController(null)
    }
  }

  function handleStop() {
    stopController?.abort()
  }

  function handleClearResult() {
    localStorage.removeItem(CACHE_KEY)
    setResult(null)
    setCachedName(null)
  }

  const fieldEntries = result ? Object.entries(result.fields).filter(([, v]) => v) : []
  const displayName = file?.name ?? cachedName?.name

  return (
    <div className="panel">
      <div className="panel__intro">
        <h2>KYC Extraction</h2>
      </div>

      <div className="upload-grid upload-grid--single">
        <UploadZone label="KYC Document" accentLabel="Document" file={file} onFileSelected={setFile} disabled={loading} />
      </div>

      <div className="panel__actions">
        <button className="btn btn--primary" disabled={!file || loading} onClick={handleExtract}>
          {loading && <span className="spinner" />}
          {loading ? 'Extracting…' : 'Extract Information'}
        </button>
        {loading && (
          <button type="button" className="btn btn--stop" onClick={handleStop}>
            Stop
          </button>
        )}
        {error && <p className="error-text">{error}</p>}
        {info && <p className="info-text">{info}</p>}
      </div>

      {result && (
        <div className="results fade-in">
          {cachedName && (
            <p className="cache-note">
              Showing the last cached result for <strong>{displayName}</strong> from{' '}
              {new Date(cachedName.savedAt).toLocaleString()}.{' '}
              <button type="button" className="link-btn" onClick={handleClearResult}>
                Clear
              </button>
            </p>
          )}

          {result.timing && (
            <p className="timing-note">
              {result.timing.total_pages} page{result.timing.total_pages === 1 ? '' : 's'} processed in{' '}
              {result.timing.elapsed_seconds}s (avg {result.timing.avg_seconds_per_page}s/page)
            </p>
          )}

          {fieldEntries.length === 0 ? (
            <p className="empty-note">No structured fields were detected. Check the raw OCR text below.</p>
          ) : (
            <div className="field-grid">
              {fieldEntries.map(([key, value]) => (
                <div className="field-card" key={key}>
                  <span className="field-card__label">{formatLabel(key)}</span>
                  <span className="field-card__value">{String(value)}</span>
                </div>
              ))}
            </div>
          )}

          <button className="btn btn--ghost" onClick={() => setShowRaw((v) => !v)}>
            {showRaw ? 'Hide raw OCR text' : 'Show raw OCR text'}
          </button>
          {showRaw && <pre className="raw-text">{result.raw_text}</pre>}
        </div>
      )}
    </div>
  )
}
