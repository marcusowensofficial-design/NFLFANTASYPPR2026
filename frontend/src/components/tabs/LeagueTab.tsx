import React from 'react'
import type { LeagueSummaryResponse, MatchupResponseItem, OptimizedLineupResult } from '../../types'
import { InjuryStatusPill } from '../shared/InjuryStatusPill'

export interface LeagueTabProps {
  league: LeagueSummaryResponse | null
  matchups: MatchupResponseItem[]
  matchupWeek: number
  setMatchupWeek: (week: number) => void
  selectedRosterTeamId: number
  setSelectedRosterTeamId: (teamId: number) => void
  teamRosterData: any | null
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
  onCompareFromRoster,
}) => {
  return (
    <div>
      {/* 1. Official League Standings Table */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <div className="card-header">
          <div>
            <h3 className="card-title">🏆 League Standings</h3>
            <span className="pill purple">{league?.name || 'Mile High Fantasy'} • Season {league?.season || 2026}</span>
          </div>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Sorted by Win% then Points For
          </span>
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
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {league?.teams.map((t, idx) => {
                const rankNum = t.rank ?? (idx + 1)
                return (
                  <tr key={t.id} style={t.is_user_team ? { background: 'rgba(6, 182, 212, 0.08)' } : undefined}>
                    <td>
                      <span className={`standings-rank-badge ${rankNum <= 3 ? `rank-${rankNum}` : ''}`}>
                        {rankNum}
                      </span>
                    </td>
                    <td>
                      <div style={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span>{t.name}</span>
                        {t.is_user_team && <span className="pill cyan" style={{ padding: '1px 6px', fontSize: '10px' }}>My Team</span>}
                      </div>
                      {t.primary_owner && (
                        <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                          {t.primary_owner}
                        </div>
                      )}
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                      {t.wins ?? 0}-{t.losses ?? 0}{t.ties ? `-${t.ties}` : ''}
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
                      <button
                        className={`btn ${selectedRosterTeamId === t.id ? 'btn-primary' : 'btn-secondary'} btn-sm`}
                        style={{ padding: '3px 10px', fontSize: '11px' }}
                        onClick={() => {
                          setSelectedRosterTeamId(t.id)
                          const rosterEl = document.getElementById('team-roster-section')
                          if (rosterEl) rosterEl.scrollIntoView({ behavior: 'smooth' })
                        }}
                      >
                        📋 View Roster
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* 2. Head-to-Head Weekly Scoreboard */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <div className="card-header">
          <div className="matchup-controls-header" style={{ width: '100%', marginBottom: 0 }}>
            <div>
              <h3 className="card-title">⚔️ Weekly Head-to-Head Scoreboard</h3>
              <span className="pill cyan">Week {matchupWeek} Matchups</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Week:</span>
              <select
                className="select-dropdown"
                value={matchupWeek}
                onChange={(e) => setMatchupWeek(Number(e.target.value))}
                style={{ padding: '4px 10px', minWidth: '100px' }}
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
              const isUserMatchup = !!(league?.user_team_id && (m.away_team_id === league.user_team_id || m.home_team_id === league.user_team_id))
              const awayWon = m.winner === 'AWAY'
              const homeWon = m.winner === 'HOME'
              const isCompleted = m.winner !== null && m.winner !== 'UNDECIDED' && m.winner !== 'NONE'
              return (
                <div key={m.matchup_id} className={`matchup-card ${isUserMatchup ? 'user-matchup' : ''}`}>
                  {/* Away Team */}
                  <div className={`matchup-team-row ${awayWon ? 'winner' : ''}`}>
                    <div className="matchup-team-info">
                      <span className="matchup-team-name">
                        {m.away_team_name}
                        {league?.user_team_id === m.away_team_id && (
                          <span className="pill cyan" style={{ padding: '0 4px', fontSize: '9px' }}>My Team</span>
                        )}
                      </span>
                      <span className="matchup-team-owner">{m.away_team_abbrev}</span>
                    </div>
                    <div className="matchup-team-scoring">
                      <span className="matchup-score-actual">
                        {isCompleted ? `${m.away_score.toFixed(1)}` : (m.away_score > 0 ? `${m.away_score.toFixed(1)}` : '—')}
                      </span>
                      <span className="matchup-score-proj">Proj: {m.away_projected.toFixed(1)}</span>
                    </div>
                  </div>

                  {/* Divider / Status */}
                  <div className="matchup-divider">
                    <span className="matchup-vs-pill">
                      {isCompleted ? 'FINAL' : 'VS'}
                    </span>
                  </div>

                  {/* Home Team */}
                  <div className={`matchup-team-row ${homeWon ? 'winner' : ''}`}>
                    <div className="matchup-team-info">
                      <span className="matchup-team-name">
                        {m.home_team_name}
                        {league?.user_team_id === m.home_team_id && (
                          <span className="pill cyan" style={{ padding: '0 4px', fontSize: '9px' }}>My Team</span>
                        )}
                      </span>
                      <span className="matchup-team-owner">{m.home_team_abbrev}</span>
                    </div>
                    <div className="matchup-team-scoring">
                      <span className="matchup-score-actual">
                        {isCompleted ? `${m.home_score.toFixed(1)}` : (m.home_score > 0 ? `${m.home_score.toFixed(1)}` : '—')}
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

      {/* 3. Complete Team Roster Deep Dive */}
      <div className="card" id="team-roster-section">
        <div className="card-header">
          <h3 className="card-title">👥 Team Roster Breakdown</h3>
          <span className="pill purple">
            {teamRosterData ? teamRosterData.team_name : 'Roster'}
          </span>
        </div>

        {/* Team Switcher for Rosters */}
        <div style={{ marginBottom: '20px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {league?.teams.map((t) => (
            <button
              key={t.id}
              className={`btn ${selectedRosterTeamId === t.id ? 'btn-primary' : 'btn-secondary'} btn-sm`}
              onClick={() => setSelectedRosterTeamId(t.id)}
            >
              {t.name}{t.primary_owner ? ` (${t.primary_owner})` : ''}
            </button>
          ))}
        </div>

        {/* Selected Team Roster View */}
        {teamRosterData && (
          <div>
            <h4 style={{ marginBottom: '12px', fontSize: '16px', fontWeight: 700 }}>
              {teamRosterData.team_name} — Total Projected: {teamRosterData.total_projected_points} pts
            </h4>
            <div className="table-responsive">
              <table className="custom-table">
                <thead>
                  <tr>
                    <th>Slot</th>
                    <th>Player</th>
                    <th>Pos</th>
                    <th>Team</th>
                    <th>Proj. Points</th>
                    <th>Status</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {teamRosterData.roster.map((p: any) => (
                    <tr key={p.entry_id} className={p.is_starter ? '' : 'bench-row'}>
                      <td><span className="slot-badge">{p.slot_name}</span></td>
                      <td style={{ fontWeight: 600 }}>{p.full_name}</td>
                      <td>{p.position}</td>
                      <td>{p.pro_team}</td>
                      <td>{p.projected_points} pts</td>
                      <td>
                        <InjuryStatusPill
                          status={p.injury_status}
                          fullName={p.full_name}
                          position={p.position}
                          injuryNote={p.fp_injury_note}
                        />
                      </td>
                      <td>
                        <button
                          className="btn btn-secondary btn-sm"
                          style={{ padding: '2px 8px', fontSize: '11px' }}
                          onClick={() => onCompareFromRoster(p)}
                        >
                          ⚖️ Compare
                        </button>
                      </td>
                    </tr>
                  ))}
                  {teamRosterData.roster.filter((p: any) => p.slot_name === 'IR').length === 0 && (
                    <tr style={{ background: 'rgba(16, 185, 129, 0.03)' }}>
                      <td>
                        <span className="slot-badge emerald" style={{ color: '#34d399', borderColor: 'rgba(16, 185, 129, 0.4)', fontWeight: 800 }}>
                          IR
                        </span>
                      </td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span style={{ fontWeight: 600, color: '#34d399' }}>Empty IR Slot</span>
                          <span className="pill emerald" style={{ fontSize: '10px', padding: '1px 5px', fontWeight: 800 }}>1 FREE SPOT</span>
                        </div>
                      </td>
                      <td style={{ color: 'var(--text-muted)' }}>Any</td>
                      <td style={{ color: 'var(--text-muted)' }}>—</td>
                      <td style={{ color: 'var(--text-muted)' }}>0.0 pts</td>
                      <td><span className="pill emerald" style={{ fontSize: '10px' }}>Open Stash</span></td>
                      <td style={{ color: 'var(--text-muted)', fontSize: '11px' }}>Free Spot</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
