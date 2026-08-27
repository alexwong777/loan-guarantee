import { useCallback, useRef, useState } from 'react'

export default function UploadZone({ label, accentLabel, file, onFileSelected, disabled }) {
  const inputRef = useRef(null)
  const [isDragging, setIsDragging] = useState(false)

  const handleFiles = useCallback(
    (files) => {
      if (files && files[0]) onFileSelected(files[0])
    },
    [onFileSelected],
  )

  const onDrop = useCallback(
    (e) => {
      e.preventDefault()
      setIsDragging(false)
      if (disabled) return
      handleFiles(e.dataTransfer.files)
    },
    [handleFiles, disabled],
  )

  return (
    <div
      className={`upload-zone ${isDragging ? 'is-dragging' : ''} ${file ? 'has-file' : ''} ${disabled ? 'is-disabled' : ''}`}
      onDragOver={(e) => {
        e.preventDefault()
        if (!disabled) setIsDragging(true)
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={onDrop}
      onClick={() => !disabled && inputRef.current?.click()}
      role="button"
      tabIndex={0}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.png,.jpg,.jpeg,.webp,.tiff,.bmp"
        hidden
        disabled={disabled}
        onChange={(e) => handleFiles(e.target.files)}
      />
      <span className="upload-zone__badge">{accentLabel}</span>

      {file ? (
        <div className="upload-zone__file">
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none">
            <path d="M6 2h9l5 5v15H6V2z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
            <path d="M14 2v6h6" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
          </svg>
          <div>
            <p className="upload-zone__filename">{file.name}</p>
            <p className="upload-zone__filesize">{(file.size / 1024).toFixed(0)} KB &middot; click to replace</p>
          </div>
        </div>
      ) : (
        <div className="upload-zone__empty">
          <svg width="30" height="30" viewBox="0 0 24 24" fill="none">
            <path d="M12 16V4m0 0L7 9m5-5l5 5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M4 16v3a2 2 0 002 2h12a2 2 0 002-2v-3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <p className="upload-zone__title">{label}</p>
          <p className="upload-zone__hint">Drag &amp; drop or click &middot; PDF, PNG, JPG</p>
        </div>
      )}
    </div>
  )
}
