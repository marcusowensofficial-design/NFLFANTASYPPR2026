import type { FactorScoreDetail } from '../../types'

export const renderWhyFactorItem = (factorStr: string, isPositive: boolean, key: string | number) => {
  const match = factorStr.match(/^\[(.*?)\]\s*(.*)$/)
  if (match) {
    const category = match[1]
    const content = match[2]
    const catClass = category.toLowerCase().replace(/[^a-z]/g, '')
    return (
      <li key={key} className={`why-factor-item ${isPositive ? 'pos' : 'neg'}`}>
        <span className={`why-pill-badge ${catClass || 'default'}`}>{category}</span>
        <span>{content}</span>
      </li>
    )
  }
  return (
    <li key={key} className={isPositive ? 'pos' : 'neg'}>
      {isPositive ? '+ ' : '- '}
      {factorStr}
    </li>
  )
}

export const renderFactorDetailBox = (
  factorKey: string,
  title: string,
  icon: string,
  detail?: FactorScoreDetail | null
) => {
  if (!detail) return null
  return (
    <div
      key={factorKey}
      style={{
        background: 'rgba(15, 23, 42, 0.75)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: '6px',
        padding: '10px 12px',
        marginBottom: '10px',
      }}
    >
      <div className="inspector-header-row" style={{ marginBottom: '8px' }}>
        <div className="inspector-factor-title">
          <span>{icon}</span>
          <span>{title}</span>
          <span className={`factor-bar-badge ${detail.bucket_color}`}>{detail.bucket}</span>
        </div>
        <strong style={{ fontSize: '13px', color: 'var(--text-primary)' }}>
          {detail.score} <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>/ 100</span>
        </strong>
      </div>

      <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--accent-cyan)', marginBottom: '3px' }}>
        📐 Mathematical Calibration Formula:
      </div>
      <div className="inspector-formula-box" style={{ marginBottom: '8px' }}>
        {detail.formula_description}
      </div>

      <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '3px' }}>
        📊 Raw Inputs Evaluated:
      </div>
      <div className="inspector-inputs-grid" style={{ marginBottom: '8px' }}>
        {Object.entries(detail.raw_inputs || {}).map(([k, v]) => (
          <div key={k} className="inspector-input-row">
            <span className="inspector-input-key">{k.replace(/_/g, ' ')}:</span>
            <span className="inspector-input-val">{String(v)}</span>
          </div>
        ))}
      </div>

      <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '3px' }}>
        ⚖️ Weighted Point Contributions:
      </div>
      <div className="inspector-contributions-box" style={{ marginBottom: '8px' }}>
        {Object.entries(detail.contributions || {}).map(([k, v]) => (
          <div key={k} className="inspector-contrib-row">
            <span className="inspector-contrib-name">{k.replace(/_/g, ' ')}</span>
            <span className="inspector-contrib-pts">+{v} pts</span>
          </div>
        ))}
      </div>

      {detail.reasons && detail.reasons.length > 0 && (
        <>
          <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '3px' }}>
            🎯 Provenance Driver Bullets:
          </div>
          <ul className="inspector-reasons-list">
            {detail.reasons.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
