import React, { useEffect, useState } from 'react'
import type { PlayerGameLogResponse, PlayerGameLogItem } from '../../types'
import { NFLTeamLogo } from '../shared/NFLTeamLogo'

interface PlayerGameLogModalProps {
  isOpen: boolean
  onClose: () => void
  playerIdOrName: number | string | null
  playerName?: string
  position?: string
  proTeam?: string
}

const renderProfessionalStatLine = (log: PlayerGameLogItem, pos?: string) => {
  const p = (pos || '').toUpperCase().trim()
  const hasPass = (log.passing?.attempts || 0) > 0 || (log.passing?.yards || 0) > 0
  const hasRush = (log.rushing?.attempts || 0) > 0 || (log.rushing?.yards || 0) > 0
  const hasRec = (log.receiving?.targets || 0) > 0 || (log.receiving?.receptions || 0) > 0 || (log.receiving?.yards || 0) > 0
  const hasKick = (log.kicking?.fg_made || 0) > 0 || (log.kicking?.xp_made || 0) > 0
  const isDST = p === 'D/ST' || p === 'DST' || log.defense !== undefined

  const pillStyle = (bg: string, border: string, color: string, isHighlight = false): React.CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: '4px',
    background: bg,
    border: `1px solid ${border}`,
    color: color,
    borderRadius: '6px',
    padding: '3px 8px',
    fontSize: '11px',
    fontWeight: isHighlight ? 800 : 600,
    letterSpacing: '-0.01em',
  })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
      {/* Primary Stat Badges Row */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', alignItems: 'center' }}>
        {/* QB / Passing Badges */}
        {hasPass && (
          <>
            <span style={pillStyle('rgba(56, 189, 248, 0.15)', 'rgba(56, 189, 248, 0.35)', '#38bdf8')}>
              🎯 <strong style={{ color: '#f8fafc' }}>{log.passing.yards}</strong> Pass Yards
            </span>
            <span style={pillStyle(
              (log.passing.touchdowns || 0) > 0 ? 'rgba(16, 185, 129, 0.2)' : 'rgba(255, 255, 255, 0.05)',
              (log.passing.touchdowns || 0) > 0 ? 'rgba(16, 185, 129, 0.45)' : 'rgba(255, 255, 255, 0.1)',
              (log.passing.touchdowns || 0) > 0 ? '#34d399' : '#94a3b8',
              (log.passing.touchdowns || 0) > 0
            )}>
              🏈 <strong style={{ color: (log.passing.touchdowns || 0) > 0 ? '#34d399' : '#f8fafc' }}>{log.passing.touchdowns || 0}</strong> Pass TDs
            </span>
            <span style={pillStyle('rgba(255, 255, 255, 0.05)', 'rgba(255, 255, 255, 0.12)', '#cbd5e1')}>
              {log.passing.completions}/{log.passing.attempts} Cmp
            </span>
            {log.passing.interceptions !== undefined && log.passing.interceptions > 0 ? (
              <span style={pillStyle('rgba(239, 68, 68, 0.18)', 'rgba(239, 68, 68, 0.4)', '#f87171', true)}>
                ⚠️ <strong>{log.passing.interceptions}</strong> INT
              </span>
            ) : (
              <span style={pillStyle('rgba(255, 255, 255, 0.04)', 'rgba(255, 255, 255, 0.08)', '#64748b')}>
                0 INT
              </span>
            )}
          </>
        )}

        {/* Rushing Badges */}
        {hasRush && (
          <>
            <span style={pillStyle('rgba(245, 158, 11, 0.15)', 'rgba(245, 158, 11, 0.35)', '#fbbf24')}>
              🏃 <strong style={{ color: '#f8fafc' }}>{log.rushing.yards}</strong> Rush Yards
            </span>
            {(log.rushing.touchdowns || 0) > 0 && (
              <span style={pillStyle('rgba(16, 185, 129, 0.2)', 'rgba(16, 185, 129, 0.45)', '#34d399', true)}>
                🏈 <strong>{log.rushing.touchdowns}</strong> Rush TD
              </span>
            )}
            <span style={pillStyle('rgba(255, 255, 255, 0.05)', 'rgba(255, 255, 255, 0.12)', '#cbd5e1')}>
              {log.rushing.attempts} Car {log.rushing.ypc > 0 ? `(${log.rushing.ypc} YPC)` : ''}
            </span>
          </>
        )}

        {/* Receiving Badges */}
        {hasRec && (
          <>
            <span style={pillStyle('rgba(168, 85, 247, 0.15)', 'rgba(168, 85, 247, 0.35)', '#c084fc')}>
              🙌 <strong style={{ color: '#f8fafc' }}>{log.receiving.yards}</strong> Rec Yards
            </span>
            {(log.receiving.touchdowns || 0) > 0 && (
              <span style={pillStyle('rgba(16, 185, 129, 0.2)', 'rgba(16, 185, 129, 0.45)', '#34d399', true)}>
                🏈 <strong>{log.receiving.touchdowns}</strong> Rec TD
              </span>
            )}
            <span style={pillStyle('rgba(255, 255, 255, 0.05)', 'rgba(255, 255, 255, 0.12)', '#cbd5e1')}>
              {log.receiving.receptions} Rec ({log.receiving.targets} Tgt)
            </span>
            {log.receiving.ypr > 0 && (
              <span style={pillStyle('rgba(255, 255, 255, 0.04)', 'rgba(255, 255, 255, 0.08)', '#94a3b8')}>
                {log.receiving.ypr} YPR
              </span>
            )}
          </>
        )}

        {/* Kicking Badges */}
        {hasKick && log.kicking && (
          <>
            <span style={pillStyle('rgba(16, 185, 129, 0.18)', 'rgba(16, 185, 129, 0.35)', '#34d399', true)}>
              🎯 <strong style={{ color: '#f8fafc' }}>{log.kicking.fg_made}</strong> FG Made
            </span>
            <span style={pillStyle('rgba(56, 189, 248, 0.15)', 'rgba(56, 189, 248, 0.3)', '#38bdf8')}>
              {log.kicking.xp_made} XP Made
            </span>
            {log.kicking.long ? (
              <span style={pillStyle('rgba(255, 255, 255, 0.05)', 'rgba(255, 255, 255, 0.1)', '#94a3b8')}>
                Long: {log.kicking.long} Yds
              </span>
            ) : null}
          </>
        )}

        {/* D/ST Badges */}
        {isDST && (
          <>
            <span style={pillStyle('rgba(56, 189, 248, 0.15)', 'rgba(56, 189, 248, 0.3)', '#38bdf8')}>
              🛡️ {log.defense?.points_allowed ?? 0} Pts Allowed
            </span>
            <span style={pillStyle('rgba(245, 158, 11, 0.15)', 'rgba(245, 158, 11, 0.3)', '#fbbf24')}>
              ⚡ {log.defense?.sacks ?? 0} Sacks
            </span>
            {((log.defense?.interceptions || 0) + (log.defense?.fumbles_recovered || 0)) > 0 && (
              <span style={pillStyle('rgba(16, 185, 129, 0.18)', 'rgba(16, 185, 129, 0.35)', '#34d399', true)}>
                🔒 {(log.defense?.interceptions || 0) + (log.defense?.fumbles_recovered || 0)} Turnovers
              </span>
            )}
          </>
        )}

        {/* Fumbles Lost */}
        {log.fumbles_lost !== undefined && log.fumbles_lost > 0 && (
          <span style={pillStyle('rgba(239, 68, 68, 0.2)', 'rgba(239, 68, 68, 0.45)', '#f87171', true)}>
            ⚠️ {log.fumbles_lost} Fumble Lost
          </span>
        )}

        {/* If no touches recorded */}
        {!hasPass && !hasRush && !hasRec && !hasKick && !isDST && (
          <span style={{ fontSize: '12px', color: '#64748b', fontStyle: 'italic' }}>
            DNP / No recorded stats
          </span>
        )}
      </div>

      {/* Micro-metrics detail line */}
      <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', fontSize: '11px', color: '#64748b' }}>
        {hasPass && log.passing.qbr && (
          <span>QBR: <strong style={{ color: '#94a3b8' }}>{log.passing.qbr}</strong></span>
        )}
        {hasRush && log.rushing.long !== undefined && log.rushing.long > 0 && (
          <span>Long Rush: <strong style={{ color: '#94a3b8' }}>{log.rushing.long} yds</strong></span>
        )}
        {hasRec && log.receiving.long !== undefined && log.receiving.long > 0 && (
          <span>Long Rec: <strong style={{ color: '#94a3b8' }}>{log.receiving.long} yds</strong></span>
        )}
        {hasRec && log.receiving.catch_pct > 0 && (
          <span>Catch Rate: <strong style={{ color: '#94a3b8' }}>{log.receiving.catch_pct}%</strong></span>
        )}
        {/* Scrimmage totals for RBs/WRs with multiple touch types */}
        {(hasRush && hasRec) && (
          <span style={{ color: '#38bdf8', fontWeight: 600 }}>
            Total Scrimmage: {(log.rushing.yards || 0) + (log.receiving.yards || 0)} Yds • {(log.rushing.attempts || 0) + (log.receiving.receptions || 0)} Touches
          </span>
        )}
      </div>
    </div>
  )
}

export const PlayerGameLogModal: React.FC<PlayerGameLogModalProps> = ({
  isOpen,
  onClose,
  playerIdOrName,
  playerName,
  position,
  proTeam,
}) => {
  const [data, setData] = useState<PlayerGameLogResponse | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [retryCount, setRetryCount] = useState<number>(0)

  useEffect(() => {
    if (!isOpen || !playerIdOrName) {
      setData(null)
      setError(null)
      return
    }

    let isMounted = true
    setIsLoading(true)
    setError(null)

    const fetchGameLog = async () => {
      try {
        const queryParam = encodeURIComponent(String(playerIdOrName).trim())
        // Attempt query parameter endpoint first (bulletproof against slashes), fallback to path endpoint
        let res: Response
        try {
          res = await fetch(`/api/analysis/player-gamelog?player_id=${queryParam}&season=2026`)
          if (!res.ok) {
            res = await fetch(`/api/analysis/player/${queryParam}/gamelog?season=2026`)
          }
        } catch {
          res = await fetch(`/api/analysis/player/${queryParam}/gamelog?season=2026`)
        }

        if (!res.ok) {
          throw new Error(`Failed to load game log (${res.status})`)
        }
        const json = await res.json()
        if (isMounted) {
          setData(json)
        }
      } catch (err: any) {
        if (isMounted) {
          const rawMsg = String(err?.message || '')
          if (rawMsg.toLowerCase().includes('failed to fetch')) {
            setError(
              'Backend server connection failed. FastAPI on port 8000 is unreachable or cloud deployment is still starting up. If running locally, please ensure run_backend.bat is running.'
            )
          } else {
            setError(rawMsg || 'Could not retrieve player game log')
          }
        }
      } finally {
        if (isMounted) {
          setIsLoading(false)
        }
      }
    }

    fetchGameLog()

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => {
      isMounted = false
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [isOpen, playerIdOrName, retryCount])

  if (!isOpen) return null

  // Resolve displayName: prioritize human-readable name over raw numeric IDs
  const isNumericString = (val?: string | number | null) =>
    val != null && (!isNaN(Number(val)) || String(val).startsWith('Player #') || String(val).startsWith('D/ST -'))

  const rawDataName = data?.player_name
  const rawPropName = playerName

  const displayName: string =
    (!isNumericString(rawDataName) && rawDataName
      ? rawDataName
      : !isNumericString(rawPropName) && rawPropName
      ? rawPropName
      : rawDataName || rawPropName || (playerIdOrName != null ? String(playerIdOrName) : 'Player'))

  const displayPos = data?.position && data.position !== 'UNK' ? data.position : (position || '')
  const displayTeam = data?.pro_team && data.pro_team !== 'UNK' ? data.pro_team : (proTeam || '')

  const getEspnUrl = (): string => {
    const rawId = data?.player_id ?? playerIdOrName
    const numId = typeof rawId === 'number' ? rawId : parseInt(String(rawId), 10)

    const isDst =
      displayPos === 'D/ST' ||
      displayPos === 'DST' ||
      (typeof numId === 'number' && !isNaN(numId) && numId < 0)

    if (isDst && displayTeam && displayTeam !== 'UNK') {
      return `https://www.espn.com/nfl/team/schedule/_/name/${displayTeam.toLowerCase().trim()}`
    }

    if (!isNaN(numId) && numId > 0) {
      return `https://www.espn.com/nfl/player/gamelog/_/id/${numId}`
    }

    if (displayTeam && displayTeam !== 'UNK') {
      return `https://www.espn.com/nfl/team/schedule/_/name/${displayTeam.toLowerCase().trim()}`
    }

    return `https://www.espn.com/search/_/q/${encodeURIComponent(displayName)}`
  }

  return (
    <div
      className="modal-backdrop"
      onClick={onClose}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(5, 10, 20, 0.85)',
        backdropFilter: 'blur(8px)',
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
      }}
    >
      <div
        className="gamelog-modal-card"
        onClick={(e) => e.stopPropagation()}
        style={{
          background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.96) 0%, rgba(30, 41, 59, 0.94) 100%)',
          border: '1px solid rgba(56, 189, 248, 0.3)',
          borderRadius: '16px',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.6), 0 0 35px rgba(56, 189, 248, 0.15)',
          width: '100%',
          maxWidth: '960px',
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          animation: 'fadeInModal 0.2s ease-out',
        }}
      >
        {/* Modal Header */}
        <div
          style={{
            padding: '16px 24px',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'rgba(255, 255, 255, 0.02)',
            gap: '12px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px', minWidth: 0 }}>
            {displayTeam && <NFLTeamLogo team={displayTeam} size={38} />}
            <div style={{ minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                <h2 style={{ fontSize: '20px', fontWeight: 800, margin: 0, color: '#f8fafc', letterSpacing: '-0.02em' }}>
                  {displayName}
                </h2>
                {displayPos && (
                  <span
                    style={{
                      background: 'rgba(56, 189, 248, 0.2)',
                      color: '#38bdf8',
                      border: '1px solid rgba(56, 189, 248, 0.4)',
                      padding: '2px 8px',
                      borderRadius: '6px',
                      fontSize: '11px',
                      fontWeight: 700,
                    }}
                  >
                    {displayPos}
                  </span>
                )}
                {displayTeam && (
                  <span style={{ fontSize: '13px', color: '#94a3b8', fontWeight: 600 }}>
                    {displayTeam}
                  </span>
                )}
              </div>
              <div style={{ fontSize: '12px', color: '#64748b', marginTop: '3px', display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                <span>2026 Regular Season Game Logs & Box Scores</span>
                <span>•</span>
                <a
                  href={getEspnUrl()}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    color: '#38bdf8',
                    textDecoration: 'none',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    fontWeight: 600,
                    fontSize: '11.5px',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.textDecoration = 'underline')}
                  onMouseLeave={(e) => (e.currentTarget.style.textDecoration = 'none')}
                  title={`Open ESPN game logs for ${displayName}`}
                >
                  <span>View on ESPN.com</span>
                  <span style={{ fontSize: '10px' }}>↗</span>
                </a>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexShrink: 0 }}>
            {/* ESPN Hotlink Button */}
            <a
              href={getEspnUrl()}
              target="_blank"
              rel="noopener noreferrer"
              className="espn-gamelog-hotlink"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                background: 'linear-gradient(135deg, rgba(235, 33, 46, 0.16) 0%, rgba(185, 28, 28, 0.28) 100%)',
                border: '1px solid rgba(239, 68, 68, 0.45)',
                color: '#fee2e2',
                borderRadius: '8px',
                padding: '7px 14px',
                fontSize: '11px',
                fontWeight: 800,
                letterSpacing: '0.03em',
                textDecoration: 'none',
                boxShadow: '0 2px 10px rgba(239, 68, 68, 0.18)',
                transition: 'all 0.18s ease',
                cursor: 'pointer',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'linear-gradient(135deg, rgba(235, 33, 46, 0.3) 0%, rgba(185, 28, 28, 0.48) 100%)'
                e.currentTarget.style.borderColor = 'rgba(239, 68, 68, 0.7)'
                e.currentTarget.style.transform = 'translateY(-1px)'
                e.currentTarget.style.boxShadow = '0 4px 14px rgba(239, 68, 68, 0.35)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'linear-gradient(135deg, rgba(235, 33, 46, 0.16) 0%, rgba(185, 28, 28, 0.28) 100%)'
                e.currentTarget.style.borderColor = 'rgba(239, 68, 68, 0.45)'
                e.currentTarget.style.transform = 'translateY(0)'
                e.currentTarget.style.boxShadow = '0 2px 10px rgba(239, 68, 68, 0.18)'
              }}
              title={`Open official ESPN game logs for ${displayName} in a new tab`}
            >
              <span
                style={{
                  background: '#cc0000',
                  color: '#ffffff',
                  padding: '1.5px 5px',
                  borderRadius: '4px',
                  fontSize: '9.5px',
                  fontWeight: 900,
                  letterSpacing: '0.05em',
                  lineHeight: 1,
                }}
              >
                ESPN
              </span>
              <span>VIEW GAMELOGS DIRECTLY ON ESPN</span>
              <span style={{ fontSize: '11px', color: '#fca5a5' }}>↗</span>
            </a>

            <button
              onClick={onClose}
              style={{
                background: 'rgba(255, 255, 255, 0.06)',
                border: '1px solid rgba(255, 255, 255, 0.12)',
                color: '#94a3b8',
                borderRadius: '8px',
                width: '34px',
                height: '34px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                fontSize: '16px',
                transition: 'all 0.15s ease',
              }}
              title="Close (Esc)"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div style={{ padding: '20px 24px', overflowY: 'auto', flex: 1 }}>
          {isLoading && (
            <div style={{ textAlign: 'center', padding: '40px 0', color: '#38bdf8' }}>
              <div style={{ fontSize: '28px', marginBottom: '10px', animation: 'spin 1s linear infinite' }}>⏳</div>
              <div style={{ fontSize: '14px', fontWeight: 600 }}>Loading 2026 official game logs...</div>
            </div>
          )}

          {error && !isLoading && (
            <div
              style={{
                background: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                borderRadius: '10px',
                padding: '16px',
                color: '#fca5a5',
                fontSize: '13px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
                alignItems: 'flex-start',
              }}
            >
              <div>⚠️ {error}</div>
              <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
                <button
                  onClick={() => setRetryCount((c) => c + 1)}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    background: 'rgba(56, 189, 248, 0.2)',
                    border: '1px solid rgba(56, 189, 248, 0.5)',
                    color: '#38bdf8',
                    borderRadius: '6px',
                    padding: '6px 14px',
                    fontSize: '11.5px',
                    fontWeight: 700,
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                >
                  <span>🔄</span>
                  <span>RETRY CONNECTION</span>
                </button>
                <a
                  href={getEspnUrl()}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    background: 'rgba(235, 33, 46, 0.2)',
                    border: '1px solid rgba(235, 33, 46, 0.5)',
                    color: '#ffffff',
                    borderRadius: '6px',
                    padding: '6px 14px',
                    fontSize: '11.5px',
                    fontWeight: 700,
                    textDecoration: 'none',
                  }}
                >
                  <span>🏈 VIEW GAMELOGS DIRECTLY ON ESPN</span>
                  <span>↗</span>
                </a>
              </div>
            </div>
          )}

          {!isLoading && !error && data && (
            <>
              {/* Season Totals Chips */}
              {data.season_totals && data.games_played > 0 && (
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                    gap: '12px',
                    marginBottom: '20px',
                  }}
                >
                  <div style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '10px', padding: '10px 14px' }}>
                    <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Avg Fantasy Pts</div>
                    <div style={{ fontSize: '18px', fontWeight: 800, color: '#38bdf8', marginTop: '2px' }}>
                      {data.season_totals.avg_fantasy_points_ppr?.toFixed(1) || '0.0'} <span style={{ fontSize: '11px', color: '#64748b' }}>PPR</span>
                    </div>
                  </div>

                  <div style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '10px', padding: '10px 14px' }}>
                    <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Games Played</div>
                    <div style={{ fontSize: '18px', fontWeight: 800, color: '#f8fafc', marginTop: '2px' }}>
                      {data.games_played}
                    </div>
                  </div>

                  {data.season_totals.total_touches !== undefined && data.season_totals.total_touches > 0 && (
                    <div style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '10px', padding: '10px 14px' }}>
                      <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Total Touches</div>
                      <div style={{ fontSize: '18px', fontWeight: 800, color: '#f59e0b', marginTop: '2px' }}>
                        {data.season_totals.total_touches}
                      </div>
                    </div>
                  )}

                  {data.season_totals.total_passing_yards !== undefined && data.season_totals.total_passing_yards > 0 && (
                    <div style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(56, 189, 248, 0.2)', borderRadius: '10px', padding: '10px 14px' }}>
                      <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Pass Yards / Pass TDs</div>
                      <div style={{ fontSize: '18px', fontWeight: 800, color: '#38bdf8', marginTop: '2px' }}>
                        {data.season_totals.total_passing_yards} <span style={{ fontSize: '12px', color: '#34d399', fontWeight: 700 }}>({data.season_totals.total_passing_tds} Pass TD)</span>
                      </div>
                    </div>
                  )}

                  {data.season_totals.total_rushing_yards !== undefined && data.season_totals.total_rushing_yards > 0 && (
                    <div style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(245, 158, 11, 0.2)', borderRadius: '10px', padding: '10px 14px' }}>
                      <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Rush Yards / Rush TDs</div>
                      <div style={{ fontSize: '18px', fontWeight: 800, color: '#fbbf24', marginTop: '2px' }}>
                        {data.season_totals.total_rushing_yards} <span style={{ fontSize: '12px', color: '#34d399', fontWeight: 700 }}>({data.season_totals.total_rushing_tds} Rush TD)</span>
                      </div>
                    </div>
                  )}

                  {data.season_totals.total_receiving_yards !== undefined && data.season_totals.total_receiving_yards > 0 && (
                    <div style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(168, 85, 247, 0.2)', borderRadius: '10px', padding: '10px 14px' }}>
                      <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Rec Yards / Receptions</div>
                      <div style={{ fontSize: '18px', fontWeight: 800, color: '#c084fc', marginTop: '2px' }}>
                        {data.season_totals.total_receiving_yards} <span style={{ fontSize: '12px', color: '#94a3b8' }}>({data.season_totals.total_receptions} Rec)</span>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Game Log Table */}
              {data.logs.length === 0 ? (
                <div
                  style={{
                    background: 'rgba(255, 255, 255, 0.02)',
                    border: '1px dashed rgba(255, 255, 255, 0.15)',
                    borderRadius: '12px',
                    padding: '34px 20px',
                    textAlign: 'center',
                    color: '#94a3b8',
                  }}
                >
                  <div style={{ fontSize: '28px', marginBottom: '8px' }}>📋</div>
                  <div style={{ fontWeight: 700, color: '#f8fafc', fontSize: '15px', marginBottom: '4px' }}>
                    No 2026 Game Logs Recorded Yet
                  </div>
                  <div style={{ fontSize: '12.5px', color: '#64748b', marginBottom: '18px', maxWidth: '420px', margin: '0 auto 18px auto' }}>
                    Asset may have had a Week 1 Bye, injury inactive, or practice squad designation. Check ESPN for full historical career logs.
                  </div>
                  <a
                    href={getEspnUrl()}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '8px',
                      background: 'linear-gradient(135deg, rgba(235, 33, 46, 0.2) 0%, rgba(185, 28, 28, 0.35) 100%)',
                      border: '1px solid rgba(239, 68, 68, 0.5)',
                      color: '#fee2e2',
                      borderRadius: '8px',
                      padding: '8px 18px',
                      fontSize: '12px',
                      fontWeight: 800,
                      letterSpacing: '0.02em',
                      textDecoration: 'none',
                    }}
                  >
                    <span
                      style={{
                        background: '#cc0000',
                        color: '#ffffff',
                        padding: '1.5px 5px',
                        borderRadius: '4px',
                        fontSize: '9.5px',
                        fontWeight: 900,
                        lineHeight: 1,
                      }}
                    >
                      ESPN
                    </span>
                    <span>VIEW GAMELOGS DIRECTLY ON ESPN</span>
                    <span>↗</span>
                  </a>
                </div>
              ) : (
                <div style={{ overflowX: 'auto' }}>
                  <table
                    style={{
                      width: '100%',
                      borderCollapse: 'collapse',
                      fontSize: '13px',
                      color: '#cbd5e1',
                    }}
                  >
                    <thead>
                      <tr
                        style={{
                          borderBottom: '1px solid rgba(255, 255, 255, 0.12)',
                          textAlign: 'left',
                          color: '#94a3b8',
                          fontSize: '11px',
                          textTransform: 'uppercase',
                          letterSpacing: '0.05em',
                        }}
                      >
                        <th style={{ padding: '10px 14px', whiteSpace: 'nowrap', width: '85px' }}>Week</th>
                        <th style={{ padding: '10px 14px', whiteSpace: 'nowrap', width: '135px' }}>Opponent</th>
                        <th style={{ padding: '10px 14px', whiteSpace: 'nowrap', width: '130px' }}>Result / Score</th>
                        <th style={{ padding: '10px 14px', whiteSpace: 'nowrap', width: '110px' }}>PPR Pts</th>
                        <th style={{ padding: '10px 14px', minWidth: '320px' }}>Stat Line Breakdown</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.logs.map((log: PlayerGameLogItem, idx: number) => {
                        const isWin = log.result.startsWith('W')
                        const isLoss = log.result.startsWith('L')

                        return (
                          <tr
                            key={log.week + idx}
                            style={{
                              borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
                              background: idx % 2 === 0 ? 'rgba(255, 255, 255, 0.01)' : 'transparent',
                            }}
                          >
                            <td style={{ padding: '12px', fontWeight: 700, color: '#f8fafc' }}>
                              Wk {log.week}
                              <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 400 }}>{log.date}</div>
                            </td>

                            <td style={{ padding: '12px' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <NFLTeamLogo team={log.opponent} size={20} />
                                <span style={{ fontWeight: 600 }}>
                                  {log.at_vs} {log.opponent}
                                </span>
                              </div>
                            </td>

                            <td style={{ padding: '12px 14px', whiteSpace: 'nowrap' }}>
                              <span
                                style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  justifyContent: 'center',
                                  gap: '4px',
                                  padding: '5px 12px',
                                  minWidth: '88px',
                                  whiteSpace: 'nowrap',
                                  borderRadius: '7px',
                                  fontSize: '12px',
                                  fontWeight: 800,
                                  letterSpacing: '0.02em',
                                  background: isWin
                                    ? 'rgba(16, 185, 129, 0.18)'
                                    : isLoss
                                    ? 'rgba(239, 68, 68, 0.18)'
                                    : 'rgba(255, 255, 255, 0.08)',
                                  color: isWin ? '#34d399' : isLoss ? '#f87171' : '#cbd5e1',
                                  border: `1px solid ${
                                    isWin
                                      ? 'rgba(16, 185, 129, 0.45)'
                                      : isLoss
                                      ? 'rgba(239, 68, 68, 0.45)'
                                      : 'rgba(255, 255, 255, 0.15)'
                                  }`,
                                  boxShadow: isWin
                                    ? '0 2px 8px rgba(16, 185, 129, 0.15)'
                                    : isLoss
                                    ? '0 2px 8px rgba(239, 68, 68, 0.15)'
                                    : 'none',
                                }}
                              >
                                {log.result || 'Final'}
                              </span>
                            </td>

                            <td style={{ padding: '12px' }}>
                              <div
                                style={{
                                  display: 'inline-block',
                                  padding: '4px 10px',
                                  borderRadius: '6px',
                                  fontWeight: 800,
                                  fontSize: '14px',
                                  background:
                                    log.fantasy_points_ppr >= 20
                                      ? 'rgba(16, 185, 129, 0.2)'
                                      : log.fantasy_points_ppr >= 12
                                      ? 'rgba(56, 189, 248, 0.2)'
                                      : log.fantasy_points_ppr >= 6
                                      ? 'rgba(245, 158, 11, 0.2)'
                                      : 'rgba(148, 163, 184, 0.15)',
                                  color:
                                    log.fantasy_points_ppr >= 20
                                      ? '#34d399'
                                      : log.fantasy_points_ppr >= 12
                                      ? '#38bdf8'
                                      : log.fantasy_points_ppr >= 6
                                      ? '#fbbf24'
                                      : '#94a3b8',
                                  border: `1px solid ${
                                    log.fantasy_points_ppr >= 20
                                      ? 'rgba(16, 185, 129, 0.4)'
                                      : log.fantasy_points_ppr >= 12
                                      ? 'rgba(56, 189, 248, 0.4)'
                                      : log.fantasy_points_ppr >= 6
                                      ? 'rgba(245, 158, 11, 0.4)'
                                      : 'rgba(148, 163, 184, 0.2)'
                                  }`,
                                }}
                              >
                                {log.fantasy_points_ppr.toFixed(1)}
                              </div>
                              <div style={{ fontSize: '10px', color: '#64748b', marginTop: '2px' }}>
                                Std: {log.fantasy_points_std?.toFixed(1) || '0.0'}
                              </div>
                            </td>

                            <td style={{ padding: '12px' }}>
                              {renderProfessionalStatLine(log, displayPos)}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>

        {/* Modal Footer */}
        <div
          style={{
            padding: '14px 24px',
            borderTop: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'rgba(255, 255, 255, 0.02)',
            flexWrap: 'wrap',
            gap: '10px',
          }}
        >
          <a
            href={getEspnUrl()}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              color: '#38bdf8',
              fontSize: '12px',
              fontWeight: 600,
              textDecoration: 'none',
              transition: 'all 0.15s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = '#7dd3fc'
              e.currentTarget.style.textDecoration = 'underline'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = '#38bdf8'
              e.currentTarget.style.textDecoration = 'none'
            }}
            title="Open official ESPN player game log page in a new tab"
          >
            <span>🔗 VIEW GAMELOGS DIRECTLY ON ESPN</span>
            <span style={{ fontSize: '11px' }}>↗</span>
          </a>

          <button
            className="btn btn-secondary btn-sm"
            onClick={onClose}
            style={{ padding: '6px 18px', fontSize: '12px', fontWeight: 600 }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
