import React, { useState, useMemo } from 'react'
import type {
  LeagueSummaryResponse,
  MatchupResponseItem,
  OptimizedLineupResult,
  TeamRosterResponse,
  RosterPlayerResponse,
} from '../../types'
import { InjuryStatusPill } from '../shared/InjuryStatusPill'
import { NFLTeamLogo } from '../shared/NFLTeamLogo'

export interface LeagueTabProps {
  league: LeagueSummaryResponse | null
  matchups: MatchupResponseItem[]
  matchupWeek: number
  setMatchupWeek: (week: number) => void
  selectedRosterTeamId: number
  setSelectedRosterTeamId: (teamId: number) => void
  teamRosterData: TeamRosterResponse | null
  isLoadingRoster?: boolean
  onRefreshRoster?: () => void
  lineup: OptimizedLineupResult | null
  onCompareFromRoster: (player: any) => void
}

export const LeagueTab: React.FC<LeagueTabProps> = ({
  league,
  matchups,
  matchupWeek,
  setMatchupWeek,
  selectedRosterTeamId,
  setSelectedRosterTeamId,
  teamRosterData,
  isLoadingRoster = false,
  onRefreshRoster,
  onCompareFromRoster,
}) => {
  const [activeSection, setActiveSection] = useState<'ALL' | 'ROSTER' | 'STANDINGS' | 'SCOREBOARD'>('ALL')
  const [positionFilter, setPositionFilter] = useState<
    'ALL' | 'STARTERS' | 'BENCH' | 'QB' | 'RB' | 'WR' | 'TE' | 'FLEX' | 'K' | 'D/ST' | 'IR'
  >('ALL')
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [sortBy, setSortBy] = useState<'SLOT' | 'PROJ_DESC' | 'NAME'>('SLOT')

  const scrollToRoster = () => {
    const rosterEl = document.getElementById('team-roster-section')
    if (rosterEl) {
      rosterEl.scrollIntoView({ behavior: 'smooth' })
    }
  }

  const handleSelectTeam = (teamId: number, autoScroll = true) => {
    setSelectedRosterTeamId(teamId)
    if (autoScroll) {
      scrollToRoster()
    }
  }

  const selectedTeamSummary = useMemo(() => {
    return league?.teams.find((t) => t.id === selectedRosterTeamId) || null
  }, [league, selectedRosterTeamId])

  // Verify that active roster data strictly matches the currently selected team ID
  const isRosterDataMatching = teamRosterData?.team_id === selectedRosterTeamId
  const activeRosterData = isRosterDataMatching ? teamRosterData : null

  // Process and filter team roster
  const filteredRoster = useMemo(() => {
    if (!activeRosterData?.roster) return []
    let list = [...activeRosterData.roster]

    // Position or Status filter
    if (positionFilter === 'STARTERS') {
      list = list.filter((p) => p.is_starter)
    } else if (positionFilter === 'BENCH') {
      list = list.filter((p) => !p.is_starter && p.slot_name !== 'IR')
    } else if (positionFilter === 'IR') {
      list = list.filter((p) => p.slot_name === 'IR')
    } else if (positionFilter === 'FLEX') {
      list = list.filter((p) => p.slot_name === 'FLEX' || (['RB', 'WR', 'TE'].includes(p.position) && p.is_starter))
    } else if (positionFilter !== 'ALL') {
      list = list.filter((p) => p.position === positionFilter)
    }

    // Search query filter
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim()
      list = list.filter(
        (p) =>
          p.full_name.toLowerCase().includes(q) ||
          p.pro_team.toLowerCase().includes(q) ||
          p.position.toLowerCase().includes(q) ||
          p.slot_name.toLowerCase().includes(q)
      )
    }

    // Sort order
    if (sortBy === 'PROJ_DESC') {
      list.sort((a, b) => b.projected_points - a.projected_points)
    } else if (sortBy === 'NAME') {
      list.sort((a, b) => a.full_name.localeCompare(b.full_name))
    } else {
      // Slot order
      const slotOrderMap: Record<string, number> = {
        QB: 1,
        RB: 2,
        WR: 3,
        TE: 4,
        FLEX: 5,
        K: 6,
        'D/ST': 7,
        DST: 7,
        BE: 8,
        BENCH: 8,
        IR: 9,
      }
      list.sort((a, b) => {
        const orderA = slotOrderMap[a.slot_name?.toUpperCase()] || 99
        const orderB = slotOrderMap[b.slot_name?.toUpperCase()] || 99
        if (orderA !== orderB) return orderA - orderB
        return b.projected_points - a.projected_points
      })
    }

    return list
  }, [activeRosterData, positionFilter, searchQuery, sortBy])

  // Compute position counts for quick badge counters
  const rosterCounts = useMemo(() => {
    if (!activeRosterData?.roster) {
      return { total: 0, starters: 0, bench: 0, ir: 0, qb: 0, rb: 0, wr: 0, te: 0, k: 0, dst: 0 }
    }
    const r = activeRosterData.roster
    return {
      total: r.length,
      starters: r.filter((p) => p.is_starter).length,
      bench: r.filter((p) => !p.is_starter && p.slot_name !== 'IR').length,
      ir: r.filter((p) => p.slot_name === 'IR').length,
      qb: r.filter((p) => p.position === 'QB').length,
      rb: r.filter((p) => p.position === 'RB').length,
      wr: r.filter((p) => p.position === 'WR').length,
      te: r.filter((p) => p.position === 'TE').length,
      k: r.filter((p) => p.position === 'K').length,
      dst: r.filter((p) => p.position === 'D/ST' || p.position === 'DST').length,
    }
  }, [activeRosterData])

  const getSlotBadgeClass = (slotName: string): string => {
    const s = slotName?.toUpperCase() || ''
    if (s === 'QB') return 'qb'
    if (s === 'RB') return 'rb'
    if (s === 'WR') return 'wr'
    if (s === 'TE') return 'te'
    if (s === 'FLEX') return 'flex'
    if (s === 'K') return 'k'
    if (s === 'D/ST' || s === 'DST') return 'dst'
    if (s === 'BE' || s === 'BENCH') return 'be'
    if (s === 'IR') return 'ir'
    return ''
  }

  return (
    <div>
      {/* 0. League Hub Control & Quick Team Switcher */}
      <div
        className="card"
        style={{
          marginBottom: '20px',
          padding: '16px 20px',
          background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.85) 100%)',
          border: '1px solid rgba(148, 163, 184, 0.15)',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '14px',
            marginBottom: '14px',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span style={{ fontSize: '20px' }}>👥</span>
              <h2 style={{ fontSize: '18px', fontWeight: 800, margin: 0, color: 'var(--text-primary)' }}>
                League Member Rosters & Intelligence
              </h2>
              <span className="pill cyan" style={{ fontSize: '11px', fontWeight: 700 }}>
                {league?.teams.length || 8} Teams
              </span>
            </div>
            <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
              Freely browse any league member's active lineup, bench stashes, and scoring projections independently.
            </div>
          </div>

          {/* Quick Sub-Section View Switcher */}
          <div
            style={{
              display: 'flex',
              gap: '6px',
              background: 'rgba(15, 23, 42, 0.6)',
              padding: '4px',
              borderRadius: '8px',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <button
              className={`btn btn-sm ${activeSection === 'ROSTER' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => {
                setActiveSection('ROSTER')
                scrollToRoster()
              }}
              style={{ fontSize: '12px', padding: '5px 12px' }}
            >
              👥 Team Rosters
            </button>
            <button
              className={`btn btn-sm ${activeSection === 'STANDINGS' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setActiveSection('STANDINGS')}
              style={{ fontSize: '12px', padding: '5px 12px' }}
            >
              🏆 Standings
            </button>
            <button
              className={`btn btn-sm ${activeSection === 'SCOREBOARD' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setActiveSection('SCOREBOARD')}
              style={{ fontSize: '12px', padding: '5px 12px' }}
            >
              ⚔️ Scoreboard
            </button>
            <button
              className={`btn btn-sm ${activeSection === 'ALL' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setActiveSection('ALL')}
              style={{ fontSize: '12px', padding: '5px 12px' }}
            >
              👀 View All
            </button>
          </div>
        </div>

        {/* Member Selector Bar */}
        <div>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '10px',
              flexWrap: 'wrap',
              gap: '8px',
            }}
          >
            <span
              style={{
                fontSize: '12px',
                fontWeight: 700,
                color: 'var(--accent-cyan)',
                textTransform: 'uppercase',
                letterSpacing: '0.5px',
              }}
            >
              ⚡ Click Any Member to Inspect Complete Roster:
            </span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Quick Select:</span>
              <select
                className="select-dropdown"
                style={{ minWidth: '220px', padding: '4px 10px', fontSize: '12px' }}
                value={selectedRosterTeamId}
                onChange={(e) => handleSelectTeam(Number(e.target.value), activeSection === 'ALL')}
              >
                {league?.teams.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name} ({t.record}) {t.is_user_team ? '★ (My Team)' : ''}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {league?.teams.map((t) => {
              const isSelected = selectedRosterTeamId === t.id
              return (
                <button
                  key={t.id}
                  className={`roster-team-switcher-btn ${isSelected ? 'active' : ''}`}
                  onClick={() => handleSelectTeam(t.id, activeSection === 'ALL')}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '6px 12px',
                    borderRadius: '6px',
                    fontSize: '12px',
                    fontWeight: isSelected ? 800 : 600,
                  }}
                >
                  <span>{isSelected ? '👁️' : '📋'}</span>
                  <span>{t.name}</span>
                  <span style={{ fontSize: '11px', opacity: 0.75 }}>({t.record})</span>
                  {t.is_user_team && (
                    <span style={{ color: 'var(--accent-cyan)', fontWeight: 900, fontSize: '11px' }}>★</span>
                  )}
                </button>
              )
            })}
          </div>
        </div>
      </div>

      {/* 1. Official League Standings Table */}
      {(activeSection === 'ALL' || activeSection === 'STANDINGS') && (
        <div className="card" style={{ marginBottom: '24px' }}>
          <div className="card-header">
            <div>
              <h3 className="card-title">🏆 League Standings & Rosters</h3>
              <span className="pill purple">
                {league?.name || 'Mile High Fantasy'} • Season {league?.season || 2026}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                Click any team row or "View Roster" button to inspect their complete roster below
              </span>
            </div>
          </div>

        <div className="table-responsive">
          <table className="custom-table">
            <thead>
              <tr>
                <th style={{ width: '60px' }}>Rank</th>
                <th>Team & Manager</th>
                <th>Record (W-L-T)</th>
                <th>Win Pct</th>
                <th>Points For (PF)</th>
                <th>Points Against (PA)</th>
                <th>Current Status</th>
                <th style={{ textAlign: 'right' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {league?.teams.map((t, idx) => {
                const rankNum = t.rank ?? idx + 1
                const isSelected = selectedRosterTeamId === t.id
                return (
                  <tr
                    key={t.id}
                    onClick={() => handleSelectTeam(t.id)}
                    className={isSelected ? 'standings-row-selected' : ''}
                    style={{
                      cursor: 'pointer',
                      transition: 'background 0.15s ease',
                      ...(t.is_user_team && !isSelected ? { background: 'rgba(6, 182, 212, 0.06)' } : {}),
                    }}
                    title={`Click to view ${t.name}'s roster`}
                  >
                    <td>
                      <span className={`standings-rank-badge ${rankNum <= 3 ? `rank-${rankNum}` : ''}`}>
                        {rankNum}
                      </span>
                    </td>
                    <td>
                      <div style={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ color: isSelected ? 'var(--accent-purple)' : 'inherit' }}>{t.name}</span>
                        {t.is_user_team && (
                          <span className="pill cyan" style={{ padding: '1px 6px', fontSize: '10px' }}>
                            My Team
                          </span>
                        )}
                        {isSelected && (
                          <span className="pill purple" style={{ padding: '1px 6px', fontSize: '10px' }}>
                            Active View
                          </span>
                        )}
                      </div>
                      {t.primary_owner && (
                        <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                          Manager: {t.primary_owner} ({t.abbrev})
                        </div>
                      )}
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                      {t.wins ?? 0}-{t.losses ?? 0}
                      {t.ties ? `-${t.ties}` : ''}
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                      {((t.win_pct || 0) * 100).toFixed(1)}%
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--accent-cyan)' }}>
                      {t.points_for.toFixed(1)} pts
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                      {t.points_against.toFixed(1)} pts
                    </td>
                    <td>
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                        {t.starter_count || 9} Starters • {t.bench_count || 7} Bench
                      </span>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <button
                        className={`btn ${isSelected ? 'btn-primary' : 'btn-secondary'} btn-sm`}
                        style={{ padding: '4px 12px', fontSize: '11px', fontWeight: 700 }}
                        onClick={(e) => {
                          e.stopPropagation()
                          handleSelectTeam(t.id)
                        }}
                      >
                        {isSelected ? '👁️ Viewing Roster' : '📋 View Roster'}
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
      )}

      {/* 2. Head-to-Head Weekly Scoreboard */}
      {(activeSection === 'ALL' || activeSection === 'SCOREBOARD') && (
        <div className="card" style={{ marginBottom: '24px' }}>
          <div className="card-header">
            <div className="matchup-controls-header" style={{ width: '100%', marginBottom: 0 }}>
              <div>
                <h3 className="card-title">⚔️ Weekly Head-to-Head Scoreboard</h3>
                <span className="pill cyan">Week {matchupWeek} Matchups</span>
              </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Matchup Week:</span>
              <select
                className="select-dropdown"
                value={matchupWeek}
                onChange={(e) => setMatchupWeek(Number(e.target.value))}
                style={{ padding: '4px 10px', minWidth: '110px' }}
              >
                {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14].map((w) => (
                  <option key={w} value={w}>
                    Week {w} {w === (league?.current_week || 1) ? '(Current)' : ''}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {matchups.length === 0 ? (
          <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '14px' }}>
            No scheduled matchups recorded for Week {matchupWeek}.
          </div>
        ) : (
          <div className="matchup-grid">
            {matchups.map((m) => {
              const isUserMatchup = !!(
                league?.user_team_id &&
                (m.away_team_id === league.user_team_id || m.home_team_id === league.user_team_id)
              )
              const awayWon = m.winner === 'AWAY'
              const homeWon = m.winner === 'HOME'
              const isCompleted = m.winner !== null && m.winner !== 'UNDECIDED' && m.winner !== 'NONE'
              const isAwaySelected = selectedRosterTeamId === m.away_team_id
              const isHomeSelected = selectedRosterTeamId === m.home_team_id

              return (
                <div key={m.matchup_id} className={`matchup-card ${isUserMatchup ? 'user-matchup' : ''}`}>
                  {/* Away Team */}
                  <div
                    className={`matchup-team-row is-clickable ${awayWon ? 'winner' : ''} ${isAwaySelected ? 'is-selected' : ''}`}
                    onClick={() => handleSelectTeam(m.away_team_id)}
                    title={`Click to view ${m.away_team_name}'s roster`}
                  >
                    <div className="matchup-team-info">
                      <span className="matchup-team-name">
                        {m.away_team_name}
                        {league?.user_team_id === m.away_team_id && (
                          <span className="pill cyan" style={{ padding: '0 4px', fontSize: '9px' }}>
                            My Team
                          </span>
                        )}
                        {isAwaySelected && (
                          <span className="pill purple" style={{ padding: '0 4px', fontSize: '9px' }}>
                            Active
                          </span>
                        )}
                      </span>
                      <span className="matchup-team-owner">
                        {m.away_team_abbrev} • <span style={{ textDecoration: 'underline' }}>Click for Roster</span>
                      </span>
                    </div>
                    <div className="matchup-team-scoring">
                      <span className="matchup-score-actual">
                        {isCompleted
                          ? `${m.away_score.toFixed(1)}`
                          : m.away_score > 0
                          ? `${m.away_score.toFixed(1)}`
                          : '—'}
                      </span>
                      <span className="matchup-score-proj">Proj: {m.away_projected.toFixed(1)}</span>
                    </div>
                  </div>

                  {/* Divider / Status */}
                  <div className="matchup-divider">
                    <span className="matchup-vs-pill">{isCompleted ? 'FINAL' : 'VS'}</span>
                  </div>

                  {/* Home Team */}
                  <div
                    className={`matchup-team-row is-clickable ${homeWon ? 'winner' : ''} ${isHomeSelected ? 'is-selected' : ''}`}
                    onClick={() => handleSelectTeam(m.home_team_id)}
                    title={`Click to view ${m.home_team_name}'s roster`}
                  >
                    <div className="matchup-team-info">
                      <span className="matchup-team-name">
                        {m.home_team_name}
                        {league?.user_team_id === m.home_team_id && (
                          <span className="pill cyan" style={{ padding: '0 4px', fontSize: '9px' }}>
                            My Team
                          </span>
                        )}
                        {isHomeSelected && (
                          <span className="pill purple" style={{ padding: '0 4px', fontSize: '9px' }}>
                            Active
                          </span>
                        )}
                      </span>
                      <span className="matchup-team-owner">
                        {m.home_team_abbrev} • <span style={{ textDecoration: 'underline' }}>Click for Roster</span>
                      </span>
                    </div>
                    <div className="matchup-team-scoring">
                      <span className="matchup-score-actual">
                        {isCompleted
                          ? `${m.home_score.toFixed(1)}`
                          : m.home_score > 0
                          ? `${m.home_score.toFixed(1)}`
                          : '—'}
                      </span>
                      <span className="matchup-score-proj">Proj: {m.home_projected.toFixed(1)}</span>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
      )}

      {/* 3. Complete Team Roster Deep Dive */}
      {(activeSection === 'ALL' || activeSection === 'ROSTER') && (
        <div className="card" id="team-roster-section" style={{ scrollMarginTop: '20px' }}>
          <div className="card-header" style={{ flexWrap: 'wrap', gap: '12px' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <h3 className="card-title" style={{ margin: 0 }}>
                  👥 {selectedTeamSummary ? selectedTeamSummary.name : (activeRosterData ? activeRosterData.team_name : 'Member')} Roster Deep Dive
                </h3>
                {selectedTeamSummary?.is_user_team && (
                  <span className="pill cyan" style={{ fontSize: '11px', fontWeight: 700 }}>
                    ★ My Team
                  </span>
                )}
              </div>
              <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px' }}>
                Manager: {selectedTeamSummary?.primary_owner || 'League Member'} • Record: {selectedTeamSummary?.record || '0-0'} • Standings Rank: #{selectedTeamSummary?.rank || 1}
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              {activeRosterData && (
                <span className="pill purple" style={{ fontSize: '12px', fontWeight: 700, padding: '4px 10px' }}>
                  Total Projected: {activeRosterData.total_projected_points.toFixed(1)} pts
                </span>
              )}
              {onRefreshRoster && (
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={onRefreshRoster}
                  disabled={isLoadingRoster}
                  title="Refresh this team's roster"
                >
                  {isLoadingRoster ? '⏳ Refreshing...' : '🔄 Refresh'}
                </button>
              )}
            </div>
          </div>

        {/* Team Switcher Bar */}
        <div style={{ marginBottom: '20px' }}>
          <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '8px' }}>
            SELECT LEAGUE MEMBER ROSTER:
          </div>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {league?.teams.map((t) => {
              const isBtnActive = selectedRosterTeamId === t.id
              return (
                <button
                  key={t.id}
                  className={`roster-team-switcher-btn ${isBtnActive ? 'active' : ''}`}
                  onClick={() => handleSelectTeam(t.id, false)}
                >
                  <span>{isBtnActive ? '👁️' : '📋'}</span>
                  <span>{t.name}</span>
                  <span style={{ fontSize: '10px', opacity: 0.75 }}>
                    ({t.record})
                  </span>
                  {t.is_user_team && (
                    <span style={{ color: 'var(--accent-cyan)', fontWeight: 800, fontSize: '10px' }}>
                      ★
                    </span>
                  )}
                </button>
              )
            })}
          </div>
        </div>

        {/* Loading State: show when loading OR when active roster does not yet match selected team */}
        {(isLoadingRoster || !isRosterDataMatching) && (
          <div
            style={{
              padding: '40px 20px',
              textAlign: 'center',
              background: 'rgba(15, 23, 42, 0.4)',
              borderRadius: '8px',
              border: '1px dashed var(--border-subtle)',
              marginBottom: '20px',
            }}
          >
            <div style={{ fontSize: '24px', marginBottom: '8px' }}>⚡</div>
            <div style={{ fontWeight: 700, fontSize: '15px', color: 'var(--text-primary)' }}>
              Loading {selectedTeamSummary?.name || 'team'}'s roster...
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
              Fetching latest ESPN player statuses and projections
            </div>
          </div>
        )}

        {/* Empty State */}
        {!isLoadingRoster && isRosterDataMatching && !activeRosterData && (
          <div
            style={{
              padding: '40px 20px',
              textAlign: 'center',
              background: 'rgba(15, 23, 42, 0.4)',
              borderRadius: '8px',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <div style={{ fontSize: '24px', marginBottom: '8px' }}>📋</div>
            <div style={{ fontWeight: 700, fontSize: '15px' }}>No roster data loaded for this team</div>
            <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px', marginBottom: '16px' }}>
              Click below to load or synchronize this team's roster entries.
            </div>
            {onRefreshRoster && (
              <button className="btn btn-primary btn-sm" onClick={onRefreshRoster}>
                🔄 Load Roster Now
              </button>
            )}
          </div>
        )}

        {/* Filter & Search Toolbar */}
        {!isLoadingRoster && isRosterDataMatching && activeRosterData && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '12px',
              flexWrap: 'wrap',
              padding: '12px 16px',
              background: 'rgba(15, 23, 42, 0.65)',
              borderRadius: '8px',
              border: '1px solid var(--border-subtle)',
              marginBottom: '16px',
            }}
          >
            {/* Position Filter Chips */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
              <button
                className={`roster-filter-chip ${positionFilter === 'ALL' ? 'active' : ''}`}
                onClick={() => setPositionFilter('ALL')}
              >
                All ({rosterCounts.total})
              </button>
              <button
                className={`roster-filter-chip ${positionFilter === 'STARTERS' ? 'active' : ''}`}
                onClick={() => setPositionFilter('STARTERS')}
              >
                Starters ({rosterCounts.starters})
              </button>
              <button
                className={`roster-filter-chip ${positionFilter === 'BENCH' ? 'active' : ''}`}
                onClick={() => setPositionFilter('BENCH')}
              >
                Bench ({rosterCounts.bench})
              </button>
              {rosterCounts.ir > 0 && (
                <button
                  className={`roster-filter-chip ${positionFilter === 'IR' ? 'active' : ''}`}
                  onClick={() => setPositionFilter('IR')}
                  style={{ color: '#f87171' }}
                >
                  IR ({rosterCounts.ir})
                </button>
              )}
              <span style={{ color: 'var(--border-subtle)', margin: '0 2px' }}>|</span>
              {(['QB', 'RB', 'WR', 'TE', 'FLEX', 'K', 'D/ST'] as const).map((pos) => (
                <button
                  key={pos}
                  className={`roster-filter-chip ${positionFilter === pos ? 'active' : ''}`}
                  onClick={() => setPositionFilter(pos)}
                >
                  {pos}
                </button>
              ))}
            </div>

            {/* Search & Sort Controls */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <input
                type="text"
                className="input-field"
                placeholder="Search player or team..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{ padding: '5px 10px', fontSize: '12px', minWidth: '180px' }}
              />
              <select
                className="select-dropdown"
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as any)}
                style={{ padding: '5px 10px', fontSize: '12px' }}
              >
                <option value="SLOT">Sort: Slot Order</option>
                <option value="PROJ_DESC">Sort: Proj Pts (High-Low)</option>
                <option value="NAME">Sort: Player Name</option>
              </select>
            </div>
          </div>
        )}

        {/* Selected Team Roster View */}
        {!isLoadingRoster && isRosterDataMatching && activeRosterData && (
          <div>
            <div className="table-responsive">
              <table className="custom-table">
                <thead>
                  <tr>
                    <th style={{ width: '80px' }}>Slot</th>
                    <th>Player</th>
                    <th>Pos</th>
                    <th>NFL Team</th>
                    <th>Projected Points</th>
                    <th>Injury & Game Status</th>
                    <th style={{ textAlign: 'right' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRoster.map((p: RosterPlayerResponse) => {
                    const slotClass = getSlotBadgeClass(p.slot_name)
                    return (
                      <tr
                        key={p.entry_id}
                        className={p.is_starter ? '' : 'bench-row'}
                        style={p.slot_name === 'IR' ? { background: 'rgba(239, 68, 68, 0.04)' } : undefined}
                      >
                        <td>
                          <span className={`slot-badge ${slotClass}`}>
                            {p.slot_name}
                          </span>
                        </td>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span style={{ fontWeight: 700, fontSize: '13px' }}>{p.full_name}</span>
                            {p.fp_pos_rank && (
                              <span
                                className="pill purple"
                                style={{ fontSize: '9px', padding: '1px 5px', fontWeight: 700 }}
                                title="FantasyPros Position Rank"
                              >
                                {p.fp_pos_rank}
                              </span>
                            )}
                            {p.fp_tier && (
                              <span
                                className="pill cyan"
                                style={{ fontSize: '9px', padding: '1px 5px', fontWeight: 700 }}
                                title="FantasyPros Tier"
                              >
                                T{p.fp_tier}
                              </span>
                            )}
                            {p.fp_start_sit_grade && (
                              <span
                                className="pill emerald"
                                style={{ fontSize: '9px', padding: '1px 5px', fontWeight: 800 }}
                                title="FantasyPros Start/Sit Grade"
                              >
                                {p.fp_start_sit_grade}
                              </span>
                            )}
                          </div>
                        </td>
                        <td>
                          <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>
                            {p.position}
                          </span>
                        </td>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <NFLTeamLogo team={p.pro_team} size={20} />
                            <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                              {p.pro_team}
                            </span>
                          </div>
                        </td>
                        <td>
                          <div>
                            <span
                              style={{
                                fontFamily: 'var(--font-mono)',
                                fontWeight: 800,
                                fontSize: '13px',
                                color: 'var(--accent-cyan)',
                              }}
                            >
                              {p.projected_points.toFixed(1)} pts
                            </span>
                            {(((p.projected_points_espn ?? 0) > 0) || ((p.projected_points_fp ?? 0) > 0)) && (
                              <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                                ESPN: {p.projected_points_espn !== undefined ? p.projected_points_espn.toFixed(1) : p.projected_points.toFixed(1)}
                                {(p.projected_points_fp ?? 0) > 0 ? ` • FP: ${p.projected_points_fp?.toFixed(1)}` : ''}
                              </div>
                            )}
                          </div>
                        </td>
                        <td>
                          <InjuryStatusPill
                            status={p.injury_status}
                            fullName={p.full_name}
                            position={p.position}
                            injuryNote={p.fp_injury_note}
                          />
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          <button
                            className="btn btn-secondary btn-sm"
                            style={{ padding: '3px 10px', fontSize: '11px' }}
                            onClick={() => onCompareFromRoster(p)}
                            title={`Compare ${p.full_name} against your lineup starters`}
                          >
                            ⚖️ Compare
                          </button>
                        </td>
                      </tr>
                    )
                  })}

                  {/* Empty IR Slot display if eligible */}
                  {positionFilter !== 'STARTERS' &&
                    positionFilter !== 'BENCH' &&
                    activeRosterData.roster.filter((p) => p.slot_name === 'IR').length === 0 && (
                      <tr style={{ background: 'rgba(16, 185, 129, 0.03)' }}>
                        <td>
                          <span
                            className="slot-badge emerald"
                            style={{
                              color: '#34d399',
                              borderColor: 'rgba(16, 185, 129, 0.4)',
                              fontWeight: 800,
                            }}
                          >
                            IR
                          </span>
                        </td>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span style={{ fontWeight: 600, color: '#34d399' }}>Empty IR Slot</span>
                            <span
                              className="pill emerald"
                              style={{ fontSize: '10px', padding: '1px 5px', fontWeight: 800 }}
                            >
                              1 FREE SPOT
                            </span>
                          </div>
                        </td>
                        <td style={{ color: 'var(--text-muted)' }}>Any</td>
                        <td style={{ color: 'var(--text-muted)' }}>—</td>
                        <td style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>0.0 pts</td>
                        <td>
                          <span className="pill emerald" style={{ fontSize: '10px' }}>
                            Open Stash
                          </span>
                        </td>
                        <td style={{ color: 'var(--text-muted)', fontSize: '11px', textAlign: 'right' }}>
                          Free Spot
                        </td>
                      </tr>
                    )}

                  {/* Empty Search / Filter Result */}
                  {filteredRoster.length === 0 && (
                    <tr>
                      <td colSpan={7} style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>
                        No players found matching current filter ({positionFilter})
                        {searchQuery ? ` and query "${searchQuery}"` : ''}.
                        <div style={{ marginTop: '8px' }}>
                          <button
                            className="btn btn-secondary btn-sm"
                            onClick={() => {
                              setPositionFilter('ALL')
                              setSearchQuery('')
                            }}
                          >
                            Reset Filters
                          </button>
                        </div>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Roster Architecture Breakdown Footer */}
            <div
              style={{
                marginTop: '16px',
                padding: '12px 16px',
                background: 'rgba(15, 23, 42, 0.5)',
                borderRadius: '8px',
                border: '1px solid var(--border-subtle)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '12px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  Roster Size: <strong style={{ color: 'var(--text-primary)' }}>{activeRosterData.roster.length}</strong> /{' '}
                  {activeRosterData.starters_count + activeRosterData.bench_slots_count + activeRosterData.ir_slots_count} Max
                </span>
                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  Starters:{' '}
                  <strong style={{ color: 'var(--accent-cyan)' }}>{activeRosterData.starters_count}</strong>
                </span>
                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  Bench:{' '}
                  <strong style={{ color: 'var(--text-primary)' }}>{activeRosterData.bench_count}</strong> /{' '}
                  {activeRosterData.bench_slots_count}
                </span>
                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  IR Slots:{' '}
                  <strong style={{ color: activeRosterData.roster.some((p) => p.slot_name === 'IR') ? '#f87171' : '#34d399' }}>
                    {activeRosterData.roster.filter((p) => p.slot_name === 'IR').length} / {activeRosterData.ir_slots_count}
                  </strong>
                </span>
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                Viewing:{' '}
                <strong style={{ color: 'var(--accent-purple)' }}>{selectedTeamSummary?.name || activeRosterData.team_name}</strong>
              </div>
            </div>
          </div>
        )}
      </div>
      )}
    </div>
  )
}
