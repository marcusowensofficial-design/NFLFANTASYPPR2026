import React, { useState } from 'react'

export interface NFLTeamLogoProps {
  team?: string | null
  size?: number
  className?: string
  style?: React.CSSProperties
  title?: string
  alt?: string
  showLabel?: boolean
  labelPosition?: 'right' | 'left' | 'bottom'
}

/**
 * Standardize alternative or legacy team codes to ESPN CDN keys
 */
export const normalizeNflTeamCode = (team?: string | null): string => {
  if (!team) return ''
  const clean = team.trim().toUpperCase()
  const map: Record<string, string> = {
    JAC: 'jax',
    JAX: 'jax',
    WAS: 'wsh',
    WSH: 'wsh',
    LA: 'lar',
    LAR: 'lar',
    SD: 'lac',
    LAC: 'lac',
    OAK: 'lv',
    LV: 'lv',
    STL: 'lar',
    ARZ: 'ari',
    BLT: 'bal',
    CLV: 'cle',
    HST: 'hou',
    SL: 'lar',
  }
  return map[clean] || clean.toLowerCase()
}

/**
 * High-resolution authentic NFL Team Logo loaded from ESPN CDN with smooth SVG/Pill fallback
 */
export const NFLTeamLogo: React.FC<NFLTeamLogoProps> = ({
  team,
  size = 24,
  className = '',
  style = {},
  title,
  alt,
  showLabel = false,
  labelPosition = 'right',
}) => {
  const [hasError, setHasError] = useState(false)
  const cleanTeam = (team || '').trim().toUpperCase()

  if (!cleanTeam || cleanTeam === 'FA' || cleanTeam === 'FREE AGENT' || cleanTeam === 'NONE' || cleanTeam === 'TBD') {
    return null
  }

  const cdnKey = normalizeNflTeamCode(cleanTeam)
  const logoUrl = `https://a.espncdn.com/i/teamlogos/nfl/500/${cdnKey}.png`
  const displayTitle = title || cleanTeam
  const displayAlt = alt || cleanTeam

  const logoElement = hasError ? (
    <span
      className={`nfl-team-fallback-badge ${className}`}
      style={{
        width: `${size}px`,
        height: `${size}px`,
        minWidth: `${size}px`,
        fontSize: size > 24 ? '11px' : size > 18 ? '9.5px' : '8px',
        ...style,
      }}
      title={displayTitle}
    >
      {cleanTeam}
    </span>
  ) : (
    <img
      src={logoUrl}
      alt={displayAlt}
      loading="lazy"
      onError={() => setHasError(true)}
      className={`nfl-team-logo-img ${className}`}
      style={{
        width: `${size}px`,
        height: `${size}px`,
        minWidth: `${size}px`,
        objectFit: 'contain',
        ...style,
      }}
      title={displayTitle}
    />
  )

  if (!showLabel) {
    return logoElement
  }

  const isFlexCol = labelPosition === 'bottom'
  const isLeft = labelPosition === 'left'

  return (
    <span
      className="nfl-team-with-label"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        flexDirection: isFlexCol ? 'column' : 'row',
        gap: size > 24 ? '6px' : '4px',
      }}
    >
      {isLeft && <span className="nfl-team-label-text">{cleanTeam}</span>}
      {logoElement}
      {!isLeft && <span className="nfl-team-label-text">{cleanTeam}</span>}
    </span>
  )
}

export default NFLTeamLogo
