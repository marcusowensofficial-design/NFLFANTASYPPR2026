import React from 'react'
import { getFantasyProsPlayerUrl, isInjuryStatus } from '../../types'

export const InjuryStatusPill: React.FC<{
  status?: string | null
  fullName: string
  position?: string
  injuryNote?: string | null
  className?: string
  style?: React.CSSProperties
}> = ({ status, fullName, position, injuryNote, className = '', style }) => {
  const displayStatus = (status || 'ACTIVE').trim().toUpperCase()
  const isInjured = isInjuryStatus(displayStatus)

  let variantClass = 'active'
  if (['OUT', 'O', 'IR', 'INJURY_RESERVE', 'INJURED_RESERVE', 'DOUBTFUL', 'D', 'PUP', 'SUSPENDED', 'SUSP'].includes(displayStatus)) {
    variantClass = 'danger'
  } else if (displayStatus.includes('QUESTIONABLE') || displayStatus === 'Q' || displayStatus.includes('PROBABLE')) {
    variantClass = 'warn'
  } else if (isInjured) {
    variantClass = 'warn'
  }

  const url = getFantasyProsPlayerUrl(fullName, position)

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    window.open(url, '_blank', 'noopener,noreferrer')
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      e.stopPropagation()
      window.open(url, '_blank', 'noopener,noreferrer')
    }
  }

  const tooltip = isInjured
    ? (injuryNote
        ? `${displayStatus}: ${injuryNote} • Click to open FantasyPros profile & live injury updates ↗`
        : `${displayStatus} • Click to open ${fullName}'s FantasyPros profile & live injury report ↗`)
    : `ACTIVE (Healthy) • Click to open ${fullName}'s FantasyPros profile ↗`

  return (
    <span
      role="button"
      tabIndex={0}
      className={`status-pill clickable ${variantClass} ${className}`.trim()}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      title={tooltip}
      style={style}
    >
      <span>{displayStatus}</span>
      {isInjured && <span className="status-pill-link-icon" aria-hidden="true">↗</span>}
    </span>
  )
}
