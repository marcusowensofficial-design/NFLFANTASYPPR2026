import { useState, useEffect } from 'react'
import type { StreamerRecommendation } from '../../types'
import { MatchupStarRating } from '../shared/MatchupStarRating'
import { NFLTeamLogo } from '../shared/NFLTeamLogo'

interface FantasyProsTabProps {
  currentWeek?: number
  onSyncSuccess?: () => void
}

export const FantasyProsTab: React.FC<FantasyProsTabProps> = ({
  currentWeek = 1,
  onSyncSuccess,
}) => {
  const [selectedFpWeek, setSelectedFpWeek] = useState<number>(currentWeek)
  const [fpViewMode, setFpViewMode] = useState<'rankings' | 'projections'>('rankings')
  const [fpRankings, setFpRankings] = useState<any[]>([])
  const [fpPosFilter, setFpPosFilter] = useState<string>('TOP 100')
  const [fpAllRankings, setFpAllRankings] = useState<Record<string, any[]> | null>(null)
  const [fpProjections, setFpProjections] = useState<any[]>([])
  const [fpAllProjections, setFpAllProjections] = useState<Record<string, any[]> | null>(null)
  const [isLoadingFpProj, setIsLoadingFpProj] = useState<boolean>(false)
  const [fpStreamers, setFpStreamers] = useState<StreamerRecommendation[]>([])
  const [fpStreamerPos, setFpStreamerPos] = useState<'DST' | 'K'>('DST')
  const [isLoadingFp, setIsLoadingFp] = useState<boolean>(false)
  const [isFpSyncing, setIsFpSyncing] = useState<boolean>(false)
  const [fpSyncResult, setFpSyncResult] = useState<string | null>(null)

  // Update selected week when currentWeek changes
  useEffect(() => {
    if (currentWeek) {
      setSelectedFpWeek(currentWeek)
    }
  }, [currentWeek])

  const loadFantasyProsRankings = async (pos: string = fpPosFilter, week: number = selectedFpWeek) => {
    setIsLoadingFp(true)
    const cleanPos = pos === 'TOP 100' ? 'TOP100' : pos
    try {
      const res = await fetch(`/api/fantasypros/rankings?position=${cleanPos}&week=${week}&scoring=PPR`)
      if (res.ok) {
        const data = await res.json()
        if (cleanPos === 'ALL') {
          setFpAllRankings(data.rankings)
          setFpRankings([])
        } else {
          setFpRankings(data.players || [])
        }
      }
    } catch (err) {
      console.error('Failed to load FantasyPros rankings:', err)
    } finally {
      setIsLoadingFp(false)
    }
  }

  const loadFantasyProsProjections = async (pos: string = 'RB', week: number = selectedFpWeek) => {
    setIsLoadingFpProj(true)
    const cleanPos = pos === 'TOP 100' ? 'RB' : pos
    try {
      const res = await fetch(`/api/fantasypros/projections?position=${cleanPos}&week=${week}&scoring=PPR`)
      if (res.ok) {
        const data = await res.json()
        if (cleanPos === 'ALL') {
          setFpAllProjections(data.projections)
          setFpProjections([])
        } else {
          setFpProjections(data.players || [])
        }
      }
    } catch (err) {
      console.error('Failed to load FantasyPros projections:', err)
    } finally {
      setIsLoadingFpProj(false)
    }
  }

  const loadFantasyProsStreamers = async (pos: 'DST' | 'K' = 'DST', week: number = selectedFpWeek) => {
    try {
      const res = await fetch(`/api/fantasypros/streamers?position=${pos}&week=${week}`)
      if (res.ok) {
        const data: StreamerRecommendation[] = await res.json()
        setFpStreamers(data)
      }
    } catch (err) {
      console.error('Failed to load streamers:', err)
    }
  }

  const handleFpSync = async () => {
    setIsFpSyncing(true)
    setFpSyncResult(null)
    try {
      const res = await fetch(`/api/fantasypros/sync?week=${selectedFpWeek}`, { method: 'POST' })
      if (res.ok) {
        const data = await res.json()
        setFpSyncResult(data.message)
        if (onSyncSuccess) {
          onSyncSuccess()
        }
        if (fpViewMode === 'rankings') {
          loadFantasyProsRankings(fpPosFilter, selectedFpWeek)
        } else {
          loadFantasyProsProjections(fpPosFilter === 'TOP 100' ? 'RB' : fpPosFilter, selectedFpWeek)
        }
      }
    } catch (err) {
      setFpSyncResult(`Sync failed: ${err}`)
    } finally {
      setIsFpSyncing(false)
    }
  }

  useEffect(() => {
    if (fpViewMode === 'rankings') {
      loadFantasyProsRankings(fpPosFilter, selectedFpWeek)
    } else {
      loadFantasyProsProjections(fpPosFilter === 'TOP 100' ? 'RB' : fpPosFilter, selectedFpWeek)
    }
    loadFantasyProsStreamers(fpStreamerPos, selectedFpWeek)
  }, [selectedFpWeek, fpViewMode])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header Card */}
      <div className="card" style={{ background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.9) 0%, rgba(30, 41, 59, 0.7) 100%)', border: '1px solid rgba(56, 189, 248, 0.3)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <h2 style={{ fontSize: '20px', fontWeight: 800, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
              <span>⭐ FantasyPros Expert Consensus & Projections</span>
              <span className="pill emerald" style={{ fontSize: '11px', padding: '2px 8px', fontWeight: 800 }}>
                🏈 Pure PPR Scoring (1.0 Pt/Rec)
              </span>
              <span className="pill cyan" style={{ fontSize: '11px', padding: '2px 8px' }}>
                Week {selectedFpWeek} Active
              </span>
              <span className="pill zinc" style={{ fontSize: '11px', padding: '2px 8px' }}>
                8-Team Calibrated
              </span>
            </h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginTop: '6px', maxWidth: '750px' }}>
              Aggregated weekly rankings, standard deviations, start/sit letter grades, and projections from over 110+ verified fantasy analysts. Filtered strictly for <strong>Full PPR</strong> scoring (not Half-PPR) for the selected NFL week.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
            {/* Week Selector Dropdown */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'rgba(15, 23, 42, 0.7)', padding: '6px 12px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.12)' }}>
              <span style={{ fontSize: '13px', color: '#38bdf8', fontWeight: 700 }}>📅 Target Week:</span>
              <select
                className="select-dropdown"
                value={selectedFpWeek}
                onChange={(e) => {
                  const w = Number(e.target.value)
                  setSelectedFpWeek(w)
                  if (fpViewMode === 'rankings') {
                    loadFantasyProsRankings(fpPosFilter, w)
                  } else {
                    loadFantasyProsProjections(fpPosFilter === 'TOP 100' ? 'RB' : fpPosFilter, w)
                  }
                  loadFantasyProsStreamers(fpStreamerPos, w)
                }}
                style={{ padding: '4px 10px', minWidth: '130px', fontWeight: 700 }}
              >
                {Array.from({ length: 18 }, (_, i) => i + 1).map((w) => (
                  <option key={w} value={w}>
                    Week {w} {w === currentWeek ? '(Current)' : ''}
                  </option>
                ))}
              </select>
            </div>

            <button
              className="btn btn-primary btn-sm"
              style={{ background: 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)', borderColor: '#38bdf8' }}
              onClick={handleFpSync}
              disabled={isFpSyncing}
            >
              {isFpSyncing ? '⏳ Syncing Week ' + selectedFpWeek + '...' : `⚡ Sync Week ${selectedFpWeek} Intelligence`}
            </button>
          </div>
        </div>

        {fpSyncResult && (
          <div className="diag-box success" style={{ marginTop: '16px', marginBottom: 0 }}>
            {fpSyncResult}
          </div>
        )}

        {/* Sub-view Navigation: Rankings vs Projections */}
        <div style={{ display: 'flex', gap: '8px', marginTop: '18px', paddingTop: '14px', borderTop: '1px solid rgba(255,255,255,0.08)' }}>
          <button
            className={`btn btn-sm ${fpViewMode === 'rankings' ? 'btn-primary' : 'btn-secondary'}`}
            style={fpViewMode === 'rankings' ? { background: '#0284c7', borderColor: '#38bdf8' } : {}}
            onClick={() => {
              setFpViewMode('rankings')
              loadFantasyProsRankings(fpPosFilter, selectedFpWeek)
            }}
          >
            📋 Consensus Rankings (PPR)
          </button>
          <button
            className={`btn btn-sm ${fpViewMode === 'projections' ? 'btn-primary' : 'btn-secondary'}`}
            style={fpViewMode === 'projections' ? { background: '#0284c7', borderColor: '#38bdf8' } : {}}
            onClick={() => {
              setFpViewMode('projections')
              loadFantasyProsProjections(fpPosFilter === 'TOP 100' ? 'RB' : fpPosFilter, selectedFpWeek)
            }}
          >
            📊 Weekly Stat Projections (PPR)
          </button>
        </div>
      </div>

      {/* VIEW 1: POSITIONAL CONSENSUS RANKINGS EXPLORER */}
      {fpViewMode === 'rankings' && (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px', marginBottom: '16px' }}>
            <div>
              <h3 style={{ fontSize: '17px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span>📋 Expert Consensus Rankings (ECR)</span>
                <span className="pill emerald" style={{ fontSize: '11px', padding: '1px 6px' }}>PPR Scoring</span>
              </h3>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                Week {selectedFpWeek} rankings across 110+ analysts by position (Strictly PPR)
              </div>
            </div>

            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              {['TOP 100', 'ALL', 'QB', 'RB', 'WR', 'TE', 'FLX', 'DST', 'K'].map((pos) => (
                <button
                  key={pos}
                  className={`btn btn-sm ${fpPosFilter === pos ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => {
                    setFpPosFilter(pos)
                    loadFantasyProsRankings(pos, selectedFpWeek)
                  }}
                >
                  {pos === 'TOP 100' ? '🏆 TOP 100' : pos}
                </button>
              ))}
            </div>
          </div>

          {isLoadingFp ? (
            <div style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>
              Loading FantasyPros Week {selectedFpWeek} PPR consensus rankings...
            </div>
          ) : fpPosFilter === 'ALL' && fpAllRankings ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {Object.entries(fpAllRankings).map(([posKey, posPlayers]) => (
                <div key={posKey}>
                  <h4 style={{ fontSize: '14px', fontWeight: 800, color: 'var(--accent-cyan)', marginBottom: '8px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '4px' }}>
                    {posKey === 'TOP100' ? '🏆 Overall Top 100 (PPR)' : `${posKey} Expert Consensus (PPR)`} ({posPlayers.length} Players)
                  </h4>
                  <div className="table-responsive">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Rank</th>
                          <th>Player</th>
                          <th>PPR Pos Rank</th>
                          <th>Team</th>
                          <th>Opponent & Matchup (DvP)</th>
                          <th>Tier</th>
                          <th>Grade</th>
                          <th>Expert Avg</th>
                          <th>Std Dev (Spread)</th>
                          <th>Min - Max</th>
                          <th>Proj PPR Pts</th>
                        </tr>
                      </thead>
                      <tbody>
                        {posPlayers.map((p: any, idx: number) => {
                          const std = p.rank_std ? Number(p.rank_std) : null
                          const grade = p.start_sit_grade
                          return (
                            <tr key={idx}>
                              <td>
                                <span style={{ fontWeight: 800, color: '#38bdf8' }}>
                                  #{p.rank_ecr}
                                </span>
                              </td>
                              <td style={{ fontWeight: 700 }}>
                                {p.player_name || p.name}
                              </td>
                              <td>
                                <span className="pill cyan" style={{ fontSize: '11px', padding: '1px 6px', fontWeight: 700 }} title="FantasyPros PPR Positional Rank">
                                  {p.pos_rank || p.player_position_id || p.position || '—'}
                                </span>
                              </td>
                              <td>{p.player_team_id || p.team_id || 'FA'}</td>
                              <td>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', minWidth: '105px' }}>
                                  <div style={{ fontWeight: 700, fontSize: '13px', color: '#f8fafc' }}>
                                    {p.player_opponent || p.opponent || '—'}
                                  </div>
                                  {p.opp_dvp_rank !== undefined && p.opp_dvp_rank !== null && (
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px', flexWrap: 'wrap' }}>
                                      <MatchupStarRating
                                        stars={p.matchup_stars}
                                        oppDvpRank={p.opp_dvp_rank}
                                        position={p.player_position_id || p.position}
                                      />
                                      <span
                                        className={`pill ${p.opp_dvp_rank <= 10 ? 'rose' : p.opp_dvp_rank >= 21 ? 'emerald' : 'amber'}`}
                                        style={{ fontSize: '9.5px', padding: '1px 5px', fontWeight: 700, lineHeight: 1.1 }}
                                        title={`Opponent ranks #${p.opp_dvp_rank} in fantasy points allowed to ${p.player_position_id || p.position || 'this position'} (1=toughest, 32=softest)`}
                                      >
                                        DvP #{p.opp_dvp_rank}
                                      </span>
                                    </div>
                                  )}
                                </div>
                              </td>
                              <td>
                                {p.tier ? (
                                  <span className="pill zinc" style={{ fontSize: '11px', padding: '1px 6px' }}>
                                    T{p.tier}
                                  </span>
                                ) : '—'}
                              </td>
                              <td>
                                {grade ? (
                                  <span
                                    className={`grade-pill ${grade.startsWith('A') ? 'grade-a' : grade.startsWith('B') ? 'grade-b' : grade.startsWith('C') ? 'grade-c' : 'grade-d'}`}
                                  >
                                    {grade}
                                  </span>
                                ) : '—'}
                              </td>
                              <td>{p.rank_ave ? Number(p.rank_ave).toFixed(1) : '—'}</td>
                              <td>
                                {std !== null ? (
                                  <span style={{ color: std <= 0.8 ? '#10b981' : std >= 1.5 ? '#f59e0b' : 'inherit', fontWeight: 600 }}>
                                    ±{std.toFixed(2)} {std <= 0.8 ? '🔒 Lock' : std >= 1.8 ? '🚀 Boom' : ''}
                                  </span>
                                ) : '—'}
                              </td>
                              <td>{p.rank_min && p.rank_max ? `${p.rank_min} - ${p.rank_max}` : '—'}</td>
                              <td style={{ fontWeight: 700, color: '#facc15' }}>
                                {p.r2p_pts ? `${Number(p.r2p_pts).toFixed(1)} pts` : '—'}
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
            </div>
          ) : fpRankings.length > 0 ? (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <h4 style={{ fontSize: '15px', fontWeight: 800, color: 'var(--accent-cyan)' }}>
                  {fpPosFilter === 'TOP 100' ? `🏆 FantasyPros Top 100 Overall PPR Rankings (Week ${selectedFpWeek})` : `📋 ${fpPosFilter} Expert Consensus PPR Rankings (Week ${selectedFpWeek})`}
                </h4>
                <span className="pill cyan">{fpRankings.length} Ranked Players</span>
              </div>
              <div className="table-responsive">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Rank</th>
                      <th>Player</th>
                      <th>PPR Pos Rank</th>
                      <th>Team</th>
                      <th>Opponent & Matchup (DvP)</th>
                      <th>Tier</th>
                      <th>Grade</th>
                      <th>Expert Avg</th>
                      <th>Std Dev (Spread)</th>
                      <th>Min - Max</th>
                      <th>Proj PPR Pts</th>
                    </tr>
                  </thead>
                  <tbody>
                    {fpRankings.map((p: any, idx: number) => {
                      const std = p.rank_std ? Number(p.rank_std) : null
                      const grade = p.start_sit_grade
                      return (
                        <tr key={idx}>
                          <td>
                            <span style={{ fontWeight: 800, color: '#38bdf8' }}>
                              #{p.rank_ecr}
                            </span>
                          </td>
                          <td style={{ fontWeight: 700 }}>
                            {p.player_name || p.name}
                          </td>
                          <td>
                            <span className="pill cyan" style={{ fontSize: '11px', padding: '1px 6px', fontWeight: 700 }} title="FantasyPros PPR Positional Rank">
                              {p.pos_rank || p.player_position_id || p.position || '—'}
                            </span>
                          </td>
                          <td>{p.player_team_id || p.team_id || 'FA'}</td>
                          <td>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', minWidth: '105px' }}>
                              <div style={{ fontWeight: 700, fontSize: '13px', color: '#f8fafc' }}>
                                {p.player_opponent || p.opponent || '—'}
                              </div>
                              {p.opp_dvp_rank !== undefined && p.opp_dvp_rank !== null && (
                                <div style={{ display: 'flex', alignItems: 'center', gap: '4px', flexWrap: 'wrap' }}>
                                  <MatchupStarRating
                                    stars={p.matchup_stars}
                                    oppDvpRank={p.opp_dvp_rank}
                                    position={p.player_position_id || p.position}
                                  />
                                  <span
                                    className={`pill ${p.opp_dvp_rank <= 10 ? 'rose' : p.opp_dvp_rank >= 21 ? 'emerald' : 'amber'}`}
                                    style={{ fontSize: '9.5px', padding: '1px 5px', fontWeight: 700, lineHeight: 1.1 }}
                                    title={`Opponent ranks #${p.opp_dvp_rank} in fantasy points allowed to ${p.player_position_id || p.position || 'this position'} (1=toughest, 32=softest)`}
                                  >
                                    DvP #{p.opp_dvp_rank}
                                  </span>
                                </div>
                              )}
                            </div>
                          </td>
                          <td>
                            {p.tier ? (
                              <span className="pill zinc" style={{ fontSize: '11px', padding: '1px 6px' }}>
                                T{p.tier}
                              </span>
                            ) : '—'}
                          </td>
                          <td>
                            {grade ? (
                              <span
                                className={`grade-pill ${grade.startsWith('A') ? 'grade-a' : grade.startsWith('B') ? 'grade-b' : grade.startsWith('C') ? 'grade-c' : 'grade-d'}`}
                                title={`FantasyPros Start/Sit Grade: ${grade}`}
                              >
                                {grade}
                              </span>
                            ) : '—'}
                          </td>
                          <td>{p.rank_ave ? Number(p.rank_ave).toFixed(1) : '—'}</td>
                          <td>
                            {std !== null ? (
                              <span style={{ color: std <= 0.8 ? '#10b981' : std >= 1.5 ? '#f59e0b' : 'inherit', fontWeight: 600 }}>
                                ±{std.toFixed(2)} {std <= 0.8 ? '🔒 Lock' : std >= 1.8 ? '🚀 Boom' : ''}
                              </span>
                            ) : '—'}
                          </td>
                          <td>{p.rank_min && p.rank_max ? `${p.rank_min} - ${p.rank_max}` : '—'}</td>
                          <td style={{ fontWeight: 700, color: '#facc15' }}>
                            {p.r2p_pts ? `${Number(p.r2p_pts).toFixed(1)} pts` : '—'}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>
              No rankings loaded for this position.
            </div>
          )}
        </div>
      )}

      {/* VIEW 2: WEEKLY STATISTICAL PROJECTIONS */}
      {fpViewMode === 'projections' && (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px', marginBottom: '16px' }}>
            <div>
              <h3 style={{ fontSize: '17px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span>📊 Weekly Statistical Projections</span>
                <span className="pill emerald" style={{ fontSize: '11px', padding: '1px 6px' }}>PPR Output</span>
              </h3>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                Week {selectedFpWeek} FantasyPros model projections with itemized box-score stats
              </div>
            </div>

            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              {['ALL', 'QB', 'RB', 'WR', 'TE', 'K', 'DST'].map((pos) => (
                <button
                  key={pos}
                  className={`btn btn-sm ${fpPosFilter === pos ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => {
                    setFpPosFilter(pos)
                    loadFantasyProsProjections(pos, selectedFpWeek)
                  }}
                >
                  {pos}
                </button>
              ))}
            </div>
          </div>

          {isLoadingFpProj ? (
            <div style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>
              Loading FantasyPros Week {selectedFpWeek} projections...
            </div>
          ) : fpPosFilter === 'ALL' && fpAllProjections ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {Object.entries(fpAllProjections).map(([posKey, posProjs]) => (
                <div key={posKey}>
                  <h4 style={{ fontSize: '14px', fontWeight: 800, color: 'var(--accent-cyan)', marginBottom: '8px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '4px' }}>
                    {posKey} Projections ({posProjs.length} Players)
                  </h4>
                  <div className="table-responsive">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>#</th>
                          <th>Player</th>
                          <th>Pos</th>
                          <th>Team</th>
                          <th>Projected PPR Pts</th>
                          <th>Stat Details</th>
                        </tr>
                      </thead>
                      <tbody>
                        {posProjs.map((p: any, idx: number) => {
                          const s = p.stats || {}
                          let statSummary = ''
                          if (p.position === 'QB') {
                            statSummary = `${s.pass_yds || 0} pass yds, ${s.pass_tds || 0} TD, ${s.rush_yds || 0} rush yds`
                          } else if (p.position === 'RB') {
                            statSummary = `${s.rush_att || 0} att, ${s.rush_yds || 0} rush yds, ${s.rec_rec || 0} rec, ${s.rec_yds || 0} rec yds`
                          } else if (p.position === 'WR' || p.position === 'TE') {
                            statSummary = `${s.rec_rec || 0} rec, ${s.rec_yds || 0} rec yds, ${s.rec_tds || 0} TD`
                          } else if (p.position === 'K') {
                            statSummary = `${s.fg || 0} FG, ${s.xpt || 0} XP`
                          } else if (p.position === 'DST') {
                            statSummary = `${s.def_sack || 0} sacks, ${s.def_int || 0} INT, ${s.def_pa || 0} PA`
                          }

                          return (
                            <tr key={idx}>
                              <td style={{ fontWeight: 800, color: '#38bdf8' }}>#{idx + 1}</td>
                              <td style={{ fontWeight: 700 }}>{p.player_name}</td>
                              <td><span className="pill cyan">{p.position}</span></td>
                              <td>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                  <NFLTeamLogo team={p.team} size={18} />
                                  <span>{p.team || 'FA'}</span>
                                </div>
                              </td>
                              <td style={{ fontWeight: 800, color: '#facc15', fontSize: '14px' }}>
                                {p.projected_points ? `${Number(p.projected_points).toFixed(1)} pts` : '—'}
                              </td>
                              <td style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                                {statSummary || 'Model consensus projection'}
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
            </div>
          ) : fpProjections.length > 0 ? (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <h4 style={{ fontSize: '15px', fontWeight: 800, color: 'var(--accent-cyan)' }}>
                  📊 {fpPosFilter === 'TOP 100' ? 'RB' : fpPosFilter} Statistical Projections (Week {selectedFpWeek} • Full PPR)
                </h4>
                <span className="pill emerald">PPR Validated</span>
              </div>
              <div className="table-responsive">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Player</th>
                      <th>Pos</th>
                      <th>Team</th>
                      <th>Projected PPR Pts</th>
                      {fpPosFilter === 'QB' && (
                        <>
                          <th>Pass Cmp / Att</th>
                          <th>Pass Yds</th>
                          <th>Pass TDs</th>
                          <th>Pass INTs</th>
                          <th>Rush Yds / TD</th>
                        </>
                      )}
                      {(fpPosFilter === 'RB' || fpPosFilter === 'TOP 100') && (
                        <>
                          <th>Rush Carries</th>
                          <th>Rush Yds</th>
                          <th>Rush TDs</th>
                          <th>Receptions</th>
                          <th>Rec Yds</th>
                          <th>Rec TDs</th>
                        </>
                      )}
                      {(fpPosFilter === 'WR' || fpPosFilter === 'TE' || fpPosFilter === 'FLX') && (
                        <>
                          <th>Receptions</th>
                          <th>Rec Yds</th>
                          <th>Rec TDs</th>
                          <th>Rush Yds</th>
                          <th>Rush TDs</th>
                        </>
                      )}
                      {fpPosFilter === 'K' && (
                        <>
                          <th>Field Goals</th>
                          <th>FG Attempts</th>
                          <th>Extra Points</th>
                        </>
                      )}
                      {fpPosFilter === 'DST' && (
                        <>
                          <th>Sacks</th>
                          <th>Interceptions</th>
                          <th>Fumble Rec</th>
                          <th>Def TDs</th>
                          <th>Points Allowed</th>
                        </>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {fpProjections.map((p: any, idx: number) => {
                      const s = p.stats || {}
                      return (
                        <tr key={idx}>
                          <td style={{ fontWeight: 800, color: '#38bdf8' }}>#{idx + 1}</td>
                          <td style={{ fontWeight: 700 }}>{p.player_name}</td>
                          <td><span className="pill cyan">{p.position}</span></td>
                          <td>{p.team || 'FA'}</td>
                          <td style={{ fontWeight: 800, color: '#facc15', fontSize: '14px' }}>
                            {p.projected_points ? `${Number(p.projected_points).toFixed(1)} pts` : '—'}
                          </td>
                          {fpPosFilter === 'QB' && (
                            <>
                              <td>{s.pass_cmp ? `${s.pass_cmp.toFixed(1)} / ${s.pass_att?.toFixed(1)}` : '—'}</td>
                              <td>{s.pass_yds ? `${s.pass_yds.toFixed(1)}` : '—'}</td>
                              <td style={{ color: '#34d399', fontWeight: 600 }}>{s.pass_tds ? `${s.pass_tds.toFixed(1)}` : '—'}</td>
                              <td style={{ color: '#f87171' }}>{s.pass_ints ? `${s.pass_ints.toFixed(1)}` : '—'}</td>
                              <td>{s.rush_yds ? `${s.rush_yds.toFixed(1)} yds (${s.rush_tds?.toFixed(1)} TD)` : '—'}</td>
                            </>
                          )}
                          {(fpPosFilter === 'RB' || fpPosFilter === 'TOP 100') && (
                            <>
                              <td>{s.rush_att ? `${s.rush_att.toFixed(1)}` : '—'}</td>
                              <td>{s.rush_yds ? `${s.rush_yds.toFixed(1)}` : '—'}</td>
                              <td style={{ color: '#34d399', fontWeight: 600 }}>{s.rush_tds ? `${s.rush_tds.toFixed(1)}` : '—'}</td>
                              <td style={{ color: '#38bdf8', fontWeight: 700 }}>{s.rec_rec ? `${s.rec_rec.toFixed(1)}` : '—'}</td>
                              <td>{s.rec_yds ? `${s.rec_yds.toFixed(1)}` : '—'}</td>
                              <td style={{ color: '#34d399', fontWeight: 600 }}>{s.rec_tds ? `${s.rec_tds.toFixed(1)}` : '—'}</td>
                            </>
                          )}
                          {(fpPosFilter === 'WR' || fpPosFilter === 'TE' || fpPosFilter === 'FLX') && (
                            <>
                              <td style={{ color: '#38bdf8', fontWeight: 700 }}>{s.rec_rec ? `${s.rec_rec.toFixed(1)}` : '—'}</td>
                              <td>{s.rec_yds ? `${s.rec_yds.toFixed(1)}` : '—'}</td>
                              <td style={{ color: '#34d399', fontWeight: 600 }}>{s.rec_tds ? `${s.rec_tds.toFixed(1)}` : '—'}</td>
                              <td>{s.rush_yds ? `${s.rush_yds.toFixed(1)}` : '0.0'}</td>
                              <td>{s.rush_tds ? `${s.rush_tds.toFixed(1)}` : '0.0'}</td>
                            </>
                          )}
                          {fpPosFilter === 'K' && (
                            <>
                              <td>{s.fg ? `${s.fg.toFixed(1)}` : '—'}</td>
                              <td>{s.fga ? `${s.fga.toFixed(1)}` : '—'}</td>
                              <td>{s.xpt ? `${s.xpt.toFixed(1)}` : '—'}</td>
                            </>
                          )}
                          {fpPosFilter === 'DST' && (
                            <>
                              <td>{s.def_sack ? `${s.def_sack.toFixed(1)}` : '—'}</td>
                              <td>{s.def_int ? `${s.def_int.toFixed(1)}` : '—'}</td>
                              <td>{s.def_fr ? `${s.def_fr.toFixed(1)}` : '—'}</td>
                              <td style={{ color: '#34d399', fontWeight: 600 }}>{s.def_td ? `${s.def_td.toFixed(1)}` : '—'}</td>
                              <td>{s.def_pa ? `${s.def_pa.toFixed(1)}` : '—'}</td>
                            </>
                          )}
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>
              No projections loaded for this position.
            </div>
          )}
        </div>
      )}

      {/* 8-MAN STREAMING CHEAT SHEET */}
      <div className="card" style={{ border: '1px solid rgba(16, 185, 129, 0.35)', background: 'rgba(6, 78, 59, 0.12)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px', marginBottom: '16px' }}>
          <div>
            <h3 style={{ fontSize: '17px', fontWeight: 800, color: '#34d399', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>🎯 8-Team Streaming Cheat Sheet (Week {selectedFpWeek})</span>
              <span className="pill emerald" style={{ fontSize: '11px', padding: '2px 8px' }}>High Leverage</span>
            </h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginTop: '4px' }}>
              Cross-referencing real-time FantasyPros Expert Consensus with your league waiver wire to identify immediate streaming upgrades for Week {selectedFpWeek}.
            </p>
          </div>

          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              className={`btn btn-sm ${fpStreamerPos === 'DST' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => {
                setFpStreamerPos('DST')
                loadFantasyProsStreamers('DST', selectedFpWeek)
              }}
            >
              🛡️ D/ST Streamers
            </button>
            <button
              className={`btn btn-sm ${fpStreamerPos === 'K' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => {
                setFpStreamerPos('K')
                loadFantasyProsStreamers('K', selectedFpWeek)
              }}
            >
              🎯 Kicker Streamers
            </button>
          </div>
        </div>

        {fpStreamers.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '20px', color: 'var(--text-muted)' }}>
            Loading top streaming candidates...
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '12px' }}>
            {fpStreamers.map((s, idx) => (
              <div
                key={idx}
                style={{
                  background: s.is_rostered ? 'rgba(15, 23, 42, 0.6)' : 'rgba(16, 185, 129, 0.1)',
                  border: s.is_rostered ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid rgba(16, 185, 129, 0.4)',
                  borderRadius: '10px',
                  padding: '14px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <div style={{ fontWeight: 800, fontSize: '15px', color: '#f8fafc' }}>
                      {s.player_name}
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap', marginTop: '2px' }}>
                      <NFLTeamLogo team={s.pro_team} size={16} />
                      <span>{s.pro_team}</span>
                      <span>•</span>
                      {s.opponent && s.opponent !== 'TBD' && <NFLTeamLogo team={s.opponent} size={16} />}
                      <span>{s.opponent || 'TBD'}</span>
                      {s.opp_dvp_rank !== undefined && s.opp_dvp_rank !== null && (
                        <>
                          <MatchupStarRating
                            stars={s.matchup_stars}
                            oppDvpRank={s.opp_dvp_rank}
                            position={s.position}
                          />
                          <span
                            className={`pill ${s.opp_dvp_rank <= 10 ? 'rose' : s.opp_dvp_rank >= 21 ? 'emerald' : 'amber'}`}
                            style={{ fontSize: '9.5px', padding: '1px 5px', fontWeight: 700, lineHeight: 1.1 }}
                            title={`Opponent ranks #${s.opp_dvp_rank} in fantasy points allowed to ${s.position}`}
                          >
                            DvP #{s.opp_dvp_rank}
                          </span>
                        </>
                      )}
                    </div>
                  </div>

                  <div style={{ textAlign: 'right' }}>
                    <span style={{ fontSize: '14px', fontWeight: 800, color: '#38bdf8' }}>
                      #{s.rank_ecr} {s.pos_rank}
                    </span>
                    {s.grade && (
                      <span style={{ marginLeft: '6px', fontSize: '11px', fontWeight: 800, background: 'rgba(16, 185, 129, 0.2)', color: '#34d399', padding: '1px 5px', borderRadius: '4px' }}>
                        {s.grade}
                      </span>
                    )}
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '12px', marginTop: '4px', paddingTop: '8px', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                  <div>
                    {s.r2p_pts ? (
                      <span style={{ color: '#facc15', fontWeight: 700 }}>
                        {s.r2p_pts.toFixed(1)} proj pts
                      </span>
                    ) : (
                      <span style={{ color: 'var(--text-muted)' }}>No stat proj</span>
                    )}
                    {s.rank_std !== null && s.rank_std !== undefined && (
                      <span style={{ marginLeft: '6px', color: 'var(--text-muted)', fontSize: '11px' }}>
                        (±{s.rank_std.toFixed(1)})
                      </span>
                    )}
                  </div>

                  <div>
                    {!s.is_rostered ? (
                      <span style={{ background: '#059669', color: '#ecfdf5', fontWeight: 800, fontSize: '10px', padding: '2px 8px', borderRadius: '12px' }}>
                        ✨ WAIVER TARGET
                      </span>
                    ) : (
                      <span style={{ background: 'rgba(255,255,255,0.08)', color: 'var(--text-muted)', fontSize: '10px', padding: '2px 6px', borderRadius: '12px' }}>
                        {s.rostered_by_team_name || 'Rostered'}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
