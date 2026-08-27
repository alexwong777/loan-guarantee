export default function DiffPane({ title, segments, tone }) {
  return (
    <div className="diff-pane">
      <div className="diff-pane__header">
        <span className={`diff-pane__dot diff-pane__dot--${tone}`} />
        <h3>{title}</h3>
      </div>
      <div className="diff-pane__body">
        {segments.length === 0 ? (
          <span className="diff-pane__empty">No text detected</span>
        ) : (
          segments.map((seg, i) => (
            <span key={i} className={`diff-seg diff-seg--${seg.type}`}>
              {seg.text}
            </span>
          ))
        )}
      </div>
    </div>
  )
}
