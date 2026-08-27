import { useEffect, useState } from 'react'
import { compareLetters } from '../api.js'
import DiffPane from './DiffPane.jsx'
import MatchGauge from './MatchGauge.jsx'
import UploadZone from './UploadZone.jsx'

const CACHE_KEY = 'lg_compare_cache'

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

function formatProgressLine(status) {
  if (!status) return ''
  const parts = Object.values(status.tracks || {}).map((t) => {
    const label = t.label.toLowerCase()
    if (!t.total) return `${label} starting…`
    return t.done ? `${label} ${t.total}/${t.total} done` : `${label} page ${t.current}/${t.total}`
  })
  parts.push(`${status.elapsed_seconds}s elapsed`)
  return parts.join('  ·  ')
}

export default function ComparePanel() {
  const [clientFile, setClientFile] = useState(null)
  const [mizuhoFile, setMizuhoFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [info, setInfo] = useState(null)
  const [result, setResult] = useState(null)
  const [cachedNames, setCachedNames] = useState(null)
  const [stopController, setStopController] = useState(null)
  const [progress, setProgress] = useState(null)

  useEffect(() => {
    const cached = loadCache()
    if (cached) {
      setResult(cached.result)
      setCachedNames({ client: cached.clientName, mizuho: cached.mizuhoName, savedAt: cached.savedAt })
    }
  }, [])

  const canCompare = clientFile && mizuhoFile && !loading

  async function handleCompare() {
    const controller = new AbortController()
    setStopController(controller)
    setLoading(true)
    setError(null)
    setInfo(null)
    setResult(null)
    setProgress(null)
    try {
      const data = await compareLetters(clientFile, mizuhoFile, {
        signal: controller.signal,
        onProgress: setProgress,
      })
      setResult(data)
      setCachedNames(null)
      saveCache({ result: data, clientName: clientFile.name, mizuhoName: mizuhoFile.name, savedAt: Date.now() })
    } catch (err) {
      if (err.isUserStop) setInfo('Stopped.')
      else setError(err.message)
    } finally {
      setLoading(false)
      setStopController(null)
      setProgress(null)
    }
  }

  function handleStop() {
    stopController?.abort()
  }

  function handleClearResult() {
    localStorage.removeItem(CACHE_KEY)
    setResult(null)
    setCachedNames(null)
  }

  const displayClientName = clientFile?.name ?? cachedNames?.client
  const displayMizuhoName = mizuhoFile?.name ?? cachedNames?.mizuho

  return (
    <div className="panel">
      <div className="panel__intro">
        <h2>Guarantee Comparison</h2>
      </div>

      <div className="upload-grid">
        <UploadZone label="Client Letter" accentLabel="Client" file={clientFile} onFileSelected={setClientFile} disabled={loading} />
        <UploadZone label="Mizuho Letter" accentLabel="Mizuho" file={mizuhoFile} onFileSelected={setMizuhoFile} disabled={loading} />
      </div>

      <div className="panel__actions">
        <button className="btn btn--primary" disabled={!canCompare} onClick={handleCompare}>
          {loading && <span className="spinner" />}
          {loading ? 'Comparing…' : 'Compare Letters'}
        </button>
        {loading && (
          <button type="button" className="btn btn--stop" onClick={handleStop}>
            Stop
          </button>
        )}
        {loading && progress && <p className="progress-line">{formatProgressLine(progress)}</p>}
        {error && <p className="error-text">{error}</p>}
        {info && <p className="info-text">{info}</p>}
      </div>

      {result && (
        <div className="results fade-in">
          {cachedNames && (
            <p className="cache-note">
              Showing the last cached result from {new Date(cachedNames.savedAt).toLocaleString()}. Upload new files
              and compare to refresh it.{' '}
              <button type="button" className="link-btn" onClick={handleClearResult}>
                Clear
              </button>
            </p>
          )}

          <div className="results__summary">
            <MatchGauge percentage={result.match_percentage} />
            <div className="results__summary-text">
              <h3>
                {result.discrepancies.length === 0
                  ? 'Letters match exactly'
                  : `${result.discrepancies.length} discrepanc${result.discrepancies.length === 1 ? 'y' : 'ies'} found`}
              </h3>
              <p>
                Word-level comparison across <strong>{displayClientName}</strong> and{' '}
                <strong>{displayMizuhoName}</strong>.
              </p>
              {result.timing && (
                <p className="timing-note">
                  {result.timing.total_pages} page{result.timing.total_pages === 1 ? '' : 's'} processed in{' '}
                  {result.timing.elapsed_seconds}s (avg {result.timing.avg_seconds_per_page}s/page)
                </p>
              )}
              <div className="legend">
                <span>
                  <i className="legend__swatch legend__swatch--removed" /> Only in client letter
                </span>
                <span>
                  <i className="legend__swatch legend__swatch--added" /> Only in Mizuho letter
                </span>
              </div>
            </div>
          </div>

          <div className="diff-grid">
            <DiffPane title="Client Letter" segments={result.left_segments} tone="client" />
            <DiffPane title="Mizuho Letter" segments={result.right_segments} tone="mizuho" />
          </div>

          {result.discrepancies.length > 0 && (
            <div className="discrepancy-list">
              <h3>Discrepancy details</h3>
              {result.discrepancies.map((d, i) => (
                <div key={i} className="discrepancy-item">
                  <span className="discrepancy-item__index">{i + 1}</span>
                  <div className="discrepancy-item__body">
                    <p>
                      <span className="tag tag--client">Client</span>
                      {d.client_text || <em>— missing —</em>}
                    </p>
                    <p>
                      <span className="tag tag--mizuho">Mizuho</span>
                      {d.mizuho_text || <em>— missing —</em>}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
