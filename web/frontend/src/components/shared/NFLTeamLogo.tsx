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
 * Comprehensive dictionary mapping NFL franchise names, nicknames, and abbreviations
 * directly to ESPN CDN lowercase keys.
 */
const NFL_TEAM_TO_CDN: Record<string, string> = {
  // Full Names
  'ARIZONA CARDINALS': 'ari',
  'ATLANTA FALCONS': 'atl',
  'BALTIMORE RAVENS': 'bal',
  'BUFFALO BILLS': 'buf',
  'CAROLINA PANTHERS': 'car',
  'CHICAGO BEARS': 'chi',
  'CINCINNATI BENGALS': 'cin',
  'CLEVELAND BROWNS': 'cle',
  'DALLAS COWBOYS': 'dal',
  'DENVER BRONCOS': 'den',
  'DETROIT LIONS': 'det',
  'GREEN BAY PACKERS': 'gb',
  'HOUSTON TEXANS': 'hou',
  'INDIANAPOLIS COLTS': 'ind',
  'JACKSONVILLE JAGUARS': 'jax',
  'KANSAS CITY CHIEFS': 'kc',
  'LAS VEGAS RAIDERS': 'lv',
  'LOS ANGELES CHARGERS': 'lac',
  'LOS ANGELES RAMS': 'lar',
  'MIAMI DOLPHINS': 'mia',
  'MINNESOTA VIKINGS': 'min',
  'NEW ENGLAND PATRIOTS': 'ne',
  'NEW ORLEANS SAINTS': 'no',
  'NEW YORK GIANTS': 'nyg',
  'NEW YORK JETS': 'nyj',
  'PHILADELPHIA EAGLES': 'phi',
  'PITTSBURGH STEELERS': 'pit',
  'SAN FRANCISCO 49ERS': 'sf',
  'SEATTLE SEAHAWKS': 'sea',
  'TAMPA BAY BUCCANEERS': 'tb',
  'TENNESSEE TITANS': 'ten',
  'WASHINGTON COMMANDERS': 'wsh',

  // Common Nicknames
  'CARDINALS': 'ari',
  'FALCONS': 'atl',
  'RAVENS': 'bal',
  'BILLS': 'buf',
  'PANTHERS': 'car',
  'BEARS': 'chi',
  'BENGALS': 'cin',
  'BROWNS': 'cle',
  'COWBOYS': 'dal',
  'BRONCOS': 'den',
  'LIONS': 'det',
  'PACKERS': 'gb',
  'TEXANS': 'hou',
  'COLTS': 'ind',
  'JAGUARS': 'jax',
  'CHIEFS': 'kc',
  'RAIDERS': 'lv',
  'CHARGERS': 'lac',
  'RAMS': 'lar',
  'DOLPHINS': 'mia',
  'VIKINGS': 'min',
  'PATRIOTS': 'ne',
  'SAINTS': 'no',
  'GIANTS': 'nyg',
  'JETS': 'nyj',
  'EAGLES': 'phi',
  'STEELERS': 'pit',
  '49ERS': 'sf',
  'NINERS': 'sf',
  'SEAHAWKS': 'sea',
  'BUCCANEERS': 'tb',
  'BUCS': 'tb',
  'TITANS': 'ten',
  'COMMANDERS': 'wsh',

  // Canonical & Legacy Abbreviations
  'ARI': 'ari',
  'ARZ': 'ari',
  'ATL': 'atl',
  'BAL': 'bal',
  'BLT': 'bal',
  'BUF': 'buf',
  'CAR': 'car',
  'CHI': 'chi',
  'CIN': 'cin',
  'CLE': 'cle',
  'CLV': 'cle',
  'DAL': 'dal',
  'DEN': 'den',
  'DET': 'det',
  'GB': 'gb',
  'GBP': 'gb',
  'HOU': 'hou',
  'HST': 'hou',
  'IND': 'ind',
  'JAX': 'jax',
  'JAC': 'jax',
  'KC': 'kc',
  'KCC': 'kc',
  'LV': 'lv',
  'LVR': 'lv',
  'OAK': 'lv',
  'LAC': 'lac',
  'SD': 'lac',
  'LAR': 'lar',
  'LA': 'lar',
  'STL': 'lar',
  'SL': 'lar',
  'MIA': 'mia',
  'MIN': 'min',
  'NE': 'ne',
  'NEP': 'ne',
  'NO': 'no',
  'NOS': 'no',
  'NYG': 'nyg',
  'NYJ': 'nyj',
  'PHI': 'phi',
  'PIT': 'pit',
  'SF': 'sf',
  'SFO': 'sf',
  'SEA': 'sea',
  'TB': 'tb',
  'TBB': 'tb',
  'TEN': 'ten',
  'WAS': 'wsh',
  'WSH': 'wsh',
}

/**
 * Standardize alternative or legacy team codes to ESPN CDN keys
 */
export const normalizeNflTeamCode = (team?: string | null): string => {
  if (!team) return ''
  const clean = team.trim().toUpperCase()

  // Direct dictionary hit
  if (NFL_TEAM_TO_CDN[clean]) {
    return NFL_TEAM_TO_CDN[clean]
  }

  // Check if string contains any recognized team keyword (e.g. "Cardinals", "Falcons")
  for (const [key, code] of Object.entries(NFL_TEAM_TO_CDN)) {
    if (key.length > 3 && clean.includes(key)) {
      return code
    }
  }

  return clean.toLowerCase().slice(0, 3)
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
  const fallbackLabel = (cdnKey || cleanTeam.slice(0, 3)).toUpperCase()

  const logoElement = hasError ? (
    <span
      className={`nfl-team-fallback-badge ${className}`}
      style={{
        width: `${size}px`,
        height: `${size}px`,
        minWidth: `${size}px`,
        maxWidth: `${size}px`,
        fontSize: size > 24 ? '11px' : size > 18 ? '9px' : '7.5px',
        overflow: 'hidden',
        whiteSpace: 'nowrap',
        textOverflow: 'clip',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
        ...style,
      }}
      title={displayTitle}
    >
      {fallbackLabel}
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
        maxWidth: `${size}px`,
        objectFit: 'contain',
        flexShrink: 0,
        ...style,
      }}
      title={displayTitle}
    ></img>
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
