import { useState } from 'react'
import { extractKyc } from '../api.js'
import UploadZone from './UploadZone.jsx'

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
}

function formatLabel(key) {
  return FIELD_LABELS[key] || key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

export default function KycPanel() {
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const [showRaw, setShowRaw] = useState(false)

  async function handleExtract() {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await extractKyc(file)
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const fieldEntries = result ? Object.entries(result.fields).filter(([, v]) => v) : []

  return (
    <div className="panel">
      <div className="panel__intro">
        <h2>KYC Document Extraction</h2>
        <p>
          Upload a passport, ID card, or company registration document. GLM-OCR reads the
          page and pulls out key identity and financial details into a structured summary.
        </p>
      </div>

      <div className="upload-grid upload-grid--single">
        <UploadZone label="KYC Document" accentLabel="Document" file={file} onFileSelected={setFile} disabled={loading} />
      </div>

      <div className="panel__actions">
        <button className="btn btn--primary" disabled={!file || loading} onClick={handleExtract}>
          {loading && <span className="spinner" />}
          {loading ? 'Extracting…' : 'Extract Information'}
        </button>
        {error && <p className="error-text">{error}</p>}
      </div>

      {result && (
        <div className="results fade-in">
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
