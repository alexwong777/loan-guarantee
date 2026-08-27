import { useState } from 'react'
import ComparePanel from './components/ComparePanel.jsx'
import KycPanel from './components/KycPanel.jsx'

const TABS = [
  { id: 'compare', label: 'Guarantee Comparison' },
  { id: 'kyc', label: 'KYC Extraction' },
]

export default function App() {
  const [activeTab, setActiveTab] = useState('compare')

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header__brand">
          <div className="app-header__logo">LG</div>
          <div>
            <h1>Letter of Guarantee Studio</h1>
            <p>Powered by GLM-OCR</p>
          </div>
        </div>
        <nav className="tabs">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              className={`tabs__item ${activeTab === tab.id ? 'is-active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="app-main">{activeTab === 'compare' ? <ComparePanel /> : <KycPanel />}</main>

      <footer className="app-footer">
        <p>Documents are processed through your own local GLM-OCR endpoint. Nothing leaves your machine.</p>
      </footer>
    </div>
  )
}
