export default function MatchGauge({ percentage }) {
  const radius = 54
  const circumference = 2 * Math.PI * radius
  const clamped = Math.max(0, Math.min(100, percentage))
  const offset = circumference - (clamped / 100) * circumference

  let tone = 'good'
  if (clamped < 90) tone = 'bad'
  else if (clamped < 99) tone = 'warn'

  return (
    <div className={`gauge gauge--${tone}`}>
      <svg width="140" height="140" viewBox="0 0 140 140">
        <circle cx="70" cy="70" r={radius} className="gauge__track" strokeWidth="10" fill="none" />
        <circle
          cx="70"
          cy="70"
          r={radius}
          className="gauge__value"
          strokeWidth="10"
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform="rotate(-90 70 70)"
        />
      </svg>
      <div className="gauge__label">
        <span className="gauge__number">{clamped.toFixed(1)}%</span>
        <span className="gauge__caption">match</span>
      </div>
    </div>
  )
}
