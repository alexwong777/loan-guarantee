import { useState } from 'react'
import { compareLetters } from '../api.js'
import DiffPane from './DiffPane.jsx'
import MatchGauge from './MatchGauge.jsx'
import UploadZone from './UploadZone.jsx'

export default function ComparePanel() {
  const [clientFile, setClientFile] = useState(null)
  const [mizuhoFile, setMizuhoFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  const canCompare = clientFile && mizuhoFile && !loading

  async function handleCompare() {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await compareLetters(clientFile, mizuhoFile)
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

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
        {error && <p className="error-text">{error}</p>}
      </div>

      {result && (
        <div className="results fade-in">
          <div className="results__summary">
            <MatchGauge percentage={result.match_percentage} />
            <div className="results__summary-text">
              <h3>
                {result.discrepancies.length === 0
                  ? 'Letters match exactly'
                  : `${result.discrepancies.length} discrepanc${result.discrepancies.length === 1 ? 'y' : 'ies'} found`}
              </h3>
              <p>
                Word-level comparison across <strong>{clientFile?.name}</strong> and{' '}
                <strong>{mizuhoFile?.name}</strong>.
              </p>
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
