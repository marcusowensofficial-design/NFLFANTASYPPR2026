import React, { useState, useMemo, useEffect } from 'react'
import type {
  LeagueSummaryResponse,
  OptimizedLineupResult,
  DvPRecordItem,
  DvPStatusResponse,
} from '../../types'
import { NFLTeamLogo } from '../shared/NFLTeamLogo'
import { Tooltip } from '../shared/Tooltip'

export interface DvpTabProps {
  league?: LeagueSummaryResponse | null
  lineup?: OptimizedLineupResult | null
  selectedTeamId?: number | null
  onNavigateTab?: (tab: string) => void
}

export const DvpTab: React.FC<DvpTabProps> = ({
  league,
  lineup,
  selectedTeamId: _selectedTeamId,
  onNavigateTab: _onNavigateTab,
}) => {
  // Defense vs Position (DvP) state
  const [dvpPosition, setDvpPosition] = useState<'QB' | 'RB' | 'WR' | 'TE'>('QB')
  const [dvpRatings, setDvpRatings] = useState<DvPRecordItem[]>([])
  const [dvpStatus, setDvpStatus] = useState<DvPStatusResponse | null>(null)
  const [isLoadingDvp, setIsLoadingDvp] = useState<boolean>(false)
  const [isSyncingDvp, setIsSyncingDvp] = useState<boolean>(false)
  const [dvpSortCol, setDvpSortCol] = useState<'rank_softness' | 'rank_defense' | 'dk_fpa' | 'vs_avg' | 'team_name'>('rank_softness')
  const [dvpSortAsc, setDvpSortAsc] = useState<boolean>(true)
  const [dvpSyncMsg, setDvpSyncMsg] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [tierFilter, setTierFilter] = useState<'ALL' | 'SMASH' | 'FAVORABLE' | 'TOUGH' | 'LOCKDOWN' | 'ROSTER'>('ALL')

  // Fetch DvP Fantasy Points Allowed ratings and sync status
  useEffect(() => {
    const fetchDvp = async () => {
      setIsLoadingDvp(true)
      try {
        const [ratingsRes, statusRes] = await Promise.all([
          fetch(`/api/analysis/dvp-ratings?position=${dvpPosition}`),
          fetch('/api/analysis/dvp-status'),
        ])
        if (ratingsRes.ok) {
          const data: DvPRecordItem[] = await ratingsRes.json()
          setDvpRatings(data)
        }
        if (statusRes.ok) {
          const sData: DvPStatusResponse = await statusRes.json()
          setDvpStatus(sData)
        }
      } catch (err) {
        console.error('Failed to load DvP data:', err)
      } finally {
        setIsLoadingDvp(false)
      }
    }
    fetchDvp()
  }, [dvpPosition])

  const handleSyncDvp = async () => {
    setIsSyncingDvp(true)
    setDvpSyncMsg(null)
    try {
      const res = await fetch('/api/analysis/dvp-sync', { method: 'POST' })
      if (res.ok) {
        const result = await res.json()
        setDvpSyncMsg(`✅ Synced ${result.records_updated} teams across all 4 positions!`)
        const [ratingsRes, statusRes] = await Promise.all([
          fetch(`/api/analysis/dvp-ratings?position=${dvpPosition}`),
          fetch('/api/analysis/dvp-status'),
        ])
        if (ratingsRes.ok) setDvpRatings(await ratingsRes.json())
        if (statusRes.ok) setDvpStatus(await statusRes.json())
      } else {
        setDvpSyncMsg('⚠️ Sync completed with cached baseline.')
      }
    } catch (err) {
      setDvpSyncMsg('❌ Sync encountered a network error.')
    } finally {
      setIsSyncingDvp(false)
      setTimeout(() => setDvpSyncMsg(null), 5000)
    }
  }

  // Map opponent teams faced by active roster to highlight DvP rows
  const rosterOpponents = useMemo(() => {
    const map = new Map<string, Array<{ full_name: string; position: string; is_starter: boolean }>>()
    if (!lineup) return map
    for (const s of lineup.starters) {
      const p = s.recommended_player
      const opp = p.opponent?.toUpperCase().trim()
      if (!opp) continue
      const list = map.get(opp) || []
      list.push({ full_name: p.full_name, position: p.position, is_starter: true })
      map.set(opp, list)
    }
    for (const b of lineup.bench) {
      const opp = b.opponent?.toUpperCase().trim()
      if (!opp) continue
      const list = map.get(opp) || []
      list.push({ full_name: b.full_name, position: b.position, is_starter: false })
      map.set(opp, list)
    }
    return map
  }, [lineup])

  // Filtered and sorted DvP ratings
  const sortedDvpRatings = useMemo(() => {
    let list = [...dvpRatings]

    // Search query filter
    if (searchQuery) {
      const q = searchQuery.toLowerCase().trim()
      list = list.filter(
        (r) =>
          r.team_name.toLowerCase().includes(q) ||
          r.pro_team.toLowerCase().includes(q) ||
          r.tier_label.toLowerCase().includes(q)
      )
    }

    // Tier filter
    if (tierFilter === 'SMASH') {
      list = list.filter((r) => r.tier === 'SMASH')
    } else if (tierFilter === 'FAVORABLE') {
      list = list.filter((r) => r.tier === 'FAVORABLE')
    } else if (tierFilter === 'TOUGH') {
      list = list.filter((r) => r.tier === 'TOUGH')
    } else if (tierFilter === 'LOCKDOWN') {
      list = list.filter((r) => r.tier === 'LOCKDOWN')
    } else if (tierFilter === 'ROSTER') {
      list = list.filter((r) => (rosterOpponents.get(r.pro_team.toUpperCase()) || []).length > 0)
    }

    // Sort column
    list.sort((a, b) => {
      const aVal: any = a[dvpSortCol]
      const bVal: any = b[dvpSortCol]
      if (typeof aVal === 'string') {
        return dvpSortAsc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal)
      }
      const numA = aVal ?? 0
      const numB = bVal ?? 0
      return dvpSortAsc ? numA - numB : numB - numA
    })
    return list
  }, [dvpRatings, searchQuery, tierFilter, dvpSortCol, dvpSortAsc, rosterOpponents])

  // KPI Quick Calculations for the current position
  const positionKpis = useMemo(() => {
    if (dvpRatings.length === 0) {
      return {
        softestTeam: null as DvPRecordItem | null,
        toughestTeam: null as DvPRecordItem | null,
        avgFpa: 0,
        rosterFacingSmashCount: 0,
      }
    }

    const sortedBySoftness = [...dvpRatings].sort((a, b) => a.rank_softness - b.rank_softness)
    const softest = sortedBySoftness[0] || null
    const toughest = sortedBySoftness[sortedBySoftness.length - 1] || null
    const avg = dvpRatings.reduce((acc, r) => acc + r.dk_fpa, 0) / (dvpRatings.length || 1)

    // Count active roster players facing top-8 defenses for this position
    let smashCount = 0
    for (const r of dvpRatings) {
      if (r.rank_softness <= 8) {
        const facing = rosterOpponents.get(r.pro_team.toUpperCase()) || []
        const posFacing = facing.filter((p) => p.position === dvpPosition)
        smashCount += posFacing.length
      }
    }

    return {
      softestTeam: softest,
      toughestTeam: toughest,
      avgFpa: avg,
      rosterFacingSmashCount: smashCount,
    }
  }, [dvpRatings, dvpPosition, rosterOpponents])

  return (
    <div className="intel-container" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* 1. EXECUTIVE HERO HEADER */}
      <div className="intel-hero-card">
        <div className="intel-hero-top">
          <div className="intel-title-group">
            <div className="intel-icon-badge" style={{ background: 'linear-gradient(135deg, #0ea5e9, #6366f1)', color: '#fff' }}>
              🛡️
            </div>
            <div>
              <h2 className="intel-heading">DEFENSES VS POSITION (DvP)</h2>
              <p className="intel-subtitle">
                32-team defensive matchup generosity, Fantasy Points Allowed (Half-PPR & Full-PPR), and active roster leverage.
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span className="pill cyan" style={{ fontWeight: 700 }}>
              Week {league?.current_week || 2} DvP Matrix
            </span>
            <button
              type="button"
              onClick={handleSyncDvp}
              disabled={isSyncingDvp}
              className="btn btn-primary btn-sm"
              style={{ padding: '6px 14px', fontSize: '12px', fontWeight: 700 }}
            >
              {isSyncingDvp ? '⏳ Syncing DraftEdge...' : '🔄 Sync DvP Feed'}
            </button>
          </div>
        </div>
      </div>

      {/* 2. BASELINE STATUS & METHODOLOGY BANNER */}
      <div className="intel-dvp-banner">
        <div className="intel-dvp-banner-content">
          <div className="intel-dvp-banner-title">
            <span>🛡️ NFL Defense vs Position (DvP) Fantasy Points Allowed (FPA) Calibration</span>
            <span className="pill cyan" style={{ fontSize: '10px' }}>Half-PPR (FanDuel) & Full-PPR (ESPN)</span>
          </div>
          <p className="intel-dvp-banner-text">
            Rankings evaluate defensive generosity per position group. For <strong>Week {league?.current_week || 2}</strong>, ratings blend realized game data with the weighted 2025-26 baseline. As additional 2026-27 games conclude, current-season sample weights expand dynamically. Higher Fantasy Points Allowed (FPA) indicates softer, high-ceiling fantasy matchups.
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginTop: '6px' }}>
            <span className="pill purple" style={{ fontSize: '10.5px' }}>
              ℹ️ Status: {dvpStatus?.is_baseline ? '2025-26 Weighted Baseline Active' : 'Current Season Calibrated'}
            </span>
            <span className="pill zinc" style={{ fontSize: '10.5px' }}>
              2026-27 Sample: {dvpStatus?.sample_games_current ?? 0} games
            </span>
            {dvpStatus?.last_updated && (
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                Last Synced: {new Date(dvpStatus.last_updated).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
              </span>
            )}
            {dvpSyncMsg && (
              <span style={{ fontSize: '11.5px', fontWeight: 700, color: 'var(--accent-emerald)' }}>
                {dvpSyncMsg}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* 3. POSITIONAL KPI PULSE STRIP */}
      <div className="intel-pulse-grid">
        <div className="intel-pulse-card">
          <div className="intel-pulse-label">
            <span>🔥 #1 Softest {dvpPosition} Matchup</span>
          </div>
          <div className="intel-pulse-val" style={{ color: 'var(--accent-emerald)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            {positionKpis.softestTeam ? (
              <>
                <NFLTeamLogo team={positionKpis.softestTeam.pro_team} size={22} />
                <span>{positionKpis.softestTeam.team_name}</span>
              </>
            ) : (
              '—'
            )}
          </div>
          <div className="intel-pulse-desc">
            Allows {positionKpis.softestTeam ? `${positionKpis.softestTeam.dk_fpa.toFixed(1)} Half-PPR / ${positionKpis.softestTeam.fd_fpa ? positionKpis.softestTeam.fd_fpa.toFixed(1) : '—'} Full-PPR FPA` : 'Calculating...'}
          </div>
        </div>

        <div className="intel-pulse-card">
          <div className="intel-pulse-label">
            <span>🛑 #32 Toughest {dvpPosition} Defense</span>
          </div>
          <div className="intel-pulse-val" style={{ color: 'var(--accent-rose)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            {positionKpis.toughestTeam ? (
              <>
                <NFLTeamLogo team={positionKpis.toughestTeam.pro_team} size={22} />
                <span>{positionKpis.toughestTeam.team_name}</span>
              </>
            ) : (
              '—'
            )}
          </div>
          <div className="intel-pulse-desc">
            Restricts to {positionKpis.toughestTeam ? `${positionKpis.toughestTeam.dk_fpa.toFixed(1)} FPA (${positionKpis.toughestTeam.vs_avg.toFixed(1)} vs avg)` : 'Calculating...'}
          </div>
        </div>

        <div className="intel-pulse-card">
          <div className="intel-pulse-label">
            <span>📊 Positional Average FPA</span>
          </div>
          <div className="intel-pulse-val" style={{ color: 'var(--accent-cyan)' }}>
            {positionKpis.avgFpa.toFixed(1)} <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>pts/game</span>
          </div>
          <div className="intel-pulse-desc">NFL baseline fantasy scoring environment for {dvpPosition}s</div>
        </div>

        <div className="intel-pulse-card">
          <div className="intel-pulse-label">
            <span>⚔️ My Roster Smash Matchups</span>
          </div>
          <div className="intel-pulse-val" style={{ color: positionKpis.rosterFacingSmashCount > 0 ? 'var(--accent-emerald)' : 'var(--text-secondary)' }}>
            {positionKpis.rosterFacingSmashCount} <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>{dvpPosition}s</span>
          </div>
          <div className="intel-pulse-desc">Rostered players facing top-8 softest defenses (Rank ≤ 8)</div>
        </div>
      </div>

      {/* 4. CONTROLS: POSITION SELECTOR, TIER FILTERS & SEARCH */}
      <div className="intel-filter-bar" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          {/* Position Selector */}
          <div className="intel-dvp-pos-selector">
            {(['QB', 'RB', 'WR', 'TE'] as const).map((pos) => (
              <button
                key={pos}
                type="button"
                onClick={() => setDvpPosition(pos)}
                className={`intel-dvp-pos-btn ${dvpPosition === pos ? 'active' : ''}`}
                style={{ fontSize: '13px', padding: '8px 16px' }}
              >
                {pos === 'QB' ? '🎯 QB Matchups' : pos === 'RB' ? '🏃 RB Matchups' : pos === 'WR' ? '⚡ WR Matchups' : '🛡️ TE Matchups'}
              </button>
            ))}
          </div>

          {/* Tier Quick Filter Buttons */}
          <div style={{ display: 'flex', gap: '4px' }}>
            {(['ALL', 'SMASH', 'FAVORABLE', 'TOUGH', 'LOCKDOWN', 'ROSTER'] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTierFilter(t)}
                className={`btn btn-sm ${tierFilter === t ? 'btn-primary' : 'btn-secondary'}`}
                style={{ padding: '4px 10px', fontSize: '11px' }}
              >
                {t === 'ALL'
                  ? 'All 32 Teams'
                  : t === 'SMASH'
                  ? '🚀 Smash'
                  : t === 'FAVORABLE'
                  ? '👍 Favorable'
                  : t === 'TOUGH'
                  ? '⚠️ Tough'
                  : t === 'LOCKDOWN'
                  ? '🛑 Lockdown'
                  : '⚔️ My Matchups'}
              </button>
            ))}
          </div>
        </div>

        {/* Search Bar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Filter by team (e.g. KC, Bills, Ravens)..."
            className="intel-search-input"
            style={{ width: '240px' }}
          />
        </div>
      </div>

      {/* 5. DVP FULL INTERACTIVE MATRIX TABLE */}
      {isLoadingDvp ? (
        <div className="card" style={{ textAlign: 'center', padding: '60px', color: 'var(--text-muted)' }}>
          <div style={{ fontSize: '32px', marginBottom: '12px' }}>⏳</div>
          Loading {dvpPosition} Defense vs Position ratings and projections...
        </div>
      ) : sortedDvpRatings.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '48px', color: 'var(--text-muted)' }}>
          No defensive teams found matching your filter criteria.
        </div>
      ) : (
        <div className="intel-dvp-table-wrap">
          <table className="intel-dvp-table">
            <thead>
              <tr>
                <th onClick={() => { setDvpSortCol('rank_softness'); setDvpSortAsc(!dvpSortAsc) }}>
                  Softness Rank {dvpSortCol === 'rank_softness' ? (dvpSortAsc ? '▲' : '▼') : ''}
                </th>
                <th onClick={() => { setDvpSortCol('team_name'); setDvpSortAsc(!dvpSortAsc) }}>
                  Defensive Team {dvpSortCol === 'team_name' ? (dvpSortAsc ? '▲' : '▼') : ''}
                </th>
                <th>Matchup Tier</th>
                <th>My Roster Exposure</th>
                <th onClick={() => { setDvpSortCol('dk_fpa'); setDvpSortAsc(!dvpSortAsc) }}>
                  <Tooltip term="DVP_FPA">
                    <span>Half-PPR FPA (FanDuel) {dvpSortCol === 'dk_fpa' ? (dvpSortAsc ? '▲' : '▼') : ''}</span>
                  </Tooltip>
                </th>
                <th>
                  <Tooltip term="DVP_FULL_PPR_FPA">
                    <span>Full-PPR FPA (ESPN Fantasy)</span>
                  </Tooltip>
                </th>
                <th onClick={() => { setDvpSortCol('vs_avg'); setDvpSortAsc(!dvpSortAsc) }}>
                  vs Pos Avg {dvpSortCol === 'vs_avg' ? (dvpSortAsc ? '▲' : '▼') : ''}
                </th>
                <th>2025-26 Base</th>
                <th>2026-27 Curr</th>
                <th>L4 Trend</th>

                {/* Position-Specific Stat Columns */}
                {dvpPosition === 'QB' && (
                  <>
                    <th>Pass Yds/G</th>
                    <th>Pass TD/G</th>
                    <th>Sacks/G</th>
                    <th>Rush Yds/G</th>
                  </>
                )}
                {dvpPosition === 'RB' && (
                  <>
                    <th>Rush Yds/G</th>
                    <th>Rush TD/G</th>
                    <th>Targets/G</th>
                    <th>Rec Yds/G</th>
                  </>
                )}
                {dvpPosition === 'WR' && (
                  <>
                    <th>Rec Yds/G</th>
                    <th>Rec TD/G</th>
                    <th>Targets/G</th>
                    <th>Rec/G</th>
                  </>
                )}
                {dvpPosition === 'TE' && (
                  <>
                    <th>Rec Yds/G</th>
                    <th>Rec TD/G</th>
                    <th>Targets/G</th>
                    <th>Rec/G</th>
                  </>
                )}
              </tr>
            </thead>
            <tbody>
              {sortedDvpRatings.map((row) => {
                const facingPlayers = rosterOpponents.get(row.pro_team.toUpperCase()) || []
                const isFacingMyTeam = facingPlayers.length > 0
                const posFacing = facingPlayers.filter((p) => p.position === dvpPosition)

                return (
                  <tr
                    key={row.id}
                    className={isFacingMyTeam ? 'roster-facing' : ''}
                  >
                    {/* Softness Rank */}
                    <td>
                      <span
                        className={`pill ${
                          row.rank_softness <= 8
                            ? 'emerald'
                            : row.rank_softness <= 16
                            ? 'cyan'
                            : row.rank_softness <= 24
                            ? 'amber'
                            : 'rose'
                        }`}
                        style={{ fontWeight: 800, fontSize: '11px', minWidth: '46px', justifyContent: 'center' }}
                      >
                        #{row.rank_softness}
                      </span>
                    </td>

                    {/* Defensive Team */}
                    <td>
                      <div className="intel-dvp-team-cell">
                        <NFLTeamLogo team={row.pro_team} size={24} />
                        <div>
                          <strong style={{ color: 'var(--text-primary)', fontSize: '13px' }}>
                            {row.team_name}
                          </strong>
                          <span style={{ fontSize: '10.5px', color: 'var(--text-muted)', marginLeft: '4px' }}>
                            ({row.pro_team})
                          </span>
                        </div>
                      </div>
                    </td>

                    {/* Tier */}
                    <td>
                      <span
                        className={`pill ${
                          row.tier === 'SMASH'
                            ? 'emerald'
                            : row.tier === 'FAVORABLE'
                            ? 'cyan'
                            : row.tier === 'TOUGH'
                            ? 'amber'
                            : row.tier === 'LOCKDOWN'
                            ? 'rose'
                            : 'zinc'
                        }`}
                        style={{ fontSize: '10px', fontWeight: 800 }}
                      >
                        {row.tier_label}
                      </span>
                    </td>

                    {/* My Roster Exposure */}
                    <td>
                      {posFacing.length > 0 ? (
                        <span
                          className="pill cyan"
                          style={{ fontSize: '10px', fontWeight: 700 }}
                          title={`Facing your active ${dvpPosition}: ${posFacing.map((p) => p.full_name).join(', ')}`}
                        >
                          ⚔️ Faces Your {dvpPosition} ({posFacing.map((p) => p.full_name.split(' ').pop()).join(', ')})
                        </span>
                      ) : isFacingMyTeam ? (
                        <span
                          className="pill zinc"
                          style={{ fontSize: '9.5px' }}
                          title={`Facing other roster players: ${facingPlayers.map((p) => `${p.full_name} (${p.position})`).join(', ')}`}
                        >
                          Facing {facingPlayers[0].full_name.split(' ').pop()} ({facingPlayers[0].position})
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>—</span>
                      )}
                    </td>

                    {/* Half-PPR FPA (FanDuel) */}
                    <td>
                      <strong
                        className="intel-dvp-val-mono"
                        style={{
                          color:
                            row.rank_softness <= 8
                              ? 'var(--accent-emerald)'
                              : row.rank_softness >= 25
                              ? 'var(--accent-rose)'
                              : 'var(--text-primary)',
                          fontSize: '13.5px',
                        }}
                      >
                        {row.dk_fpa.toFixed(1)}
                      </strong>
                    </td>

                    {/* Full-PPR FPA (ESPN) */}
                    <td>
                      <span className="intel-dvp-val-mono" style={{ color: 'var(--text-secondary)' }}>
                        {row.fd_fpa ? row.fd_fpa.toFixed(1) : '—'}
                      </span>
                    </td>

                    {/* vs Average */}
                    <td>
                      <span
                        className="intel-dvp-val-mono"
                        style={{
                          color:
                            row.vs_avg > 0
                              ? 'var(--accent-emerald)'
                              : row.vs_avg < 0
                              ? 'var(--accent-rose)'
                              : 'var(--text-muted)',
                        }}
                      >
                        {row.vs_avg > 0 ? `+${row.vs_avg.toFixed(1)}` : row.vs_avg.toFixed(1)}
                      </span>
                    </td>

                    {/* Prior Season Baseline */}
                    <td>
                      <span style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                        {row.prior_season_fpa ? row.prior_season_fpa.toFixed(1) : '—'}
                      </span>
                    </td>

                    {/* Current Season */}
                    <td>
                      <span style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                        {row.sample_games_current > 0 && row.current_season_fpa
                          ? row.current_season_fpa.toFixed(1)
                          : 'Stabilizing...'}
                      </span>
                    </td>

                    {/* Trend */}
                    <td>
                      <span
                        className={`pill ${
                          row.trend === 'UP' ? 'emerald' : row.trend === 'DOWN' ? 'rose' : 'zinc'
                        }`}
                        style={{ fontSize: '10px', padding: '1px 6px', fontWeight: 700 }}
                      >
                        {row.trend === 'UP' ? '📈 Softening' : row.trend === 'DOWN' ? '📉 Stiffening' : '⚖️ Stable'}
                      </span>
                    </td>

                    {/* Position-Specific Key Allowed Stats */}
                    {dvpPosition === 'QB' && (
                      <>
                        <td>{row.supporting_stats?.pass_yds ? `${row.supporting_stats.pass_yds.toFixed(0)} yds` : '—'}</td>
                        <td>{row.supporting_stats?.pass_td ? row.supporting_stats.pass_td.toFixed(2) : '—'}</td>
                        <td>{row.supporting_stats?.sacks ? row.supporting_stats.sacks.toFixed(1) : '—'}</td>
                        <td>{row.supporting_stats?.rush_yds ? `${row.supporting_stats.rush_yds.toFixed(0)} yds` : '—'}</td>
                      </>
                    )}
                    {dvpPosition === 'RB' && (
                      <>
                        <td>{row.supporting_stats?.rush_yds ? `${row.supporting_stats.rush_yds.toFixed(0)} yds` : '—'}</td>
                        <td>{row.supporting_stats?.rush_td ? row.supporting_stats.rush_td.toFixed(2) : '—'}</td>
                        <td>{row.supporting_stats?.targets ? row.supporting_stats.targets.toFixed(1) : '—'}</td>
                        <td>{row.supporting_stats?.rec_yds ? `${row.supporting_stats.rec_yds.toFixed(0)} yds` : '—'}</td>
                      </>
                    )}
                    {dvpPosition === 'WR' && (
                      <>
                        <td>{row.supporting_stats?.rec_yds ? `${row.supporting_stats.rec_yds.toFixed(0)} yds` : '—'}</td>
                        <td>{row.supporting_stats?.rec_td ? row.supporting_stats.rec_td.toFixed(2) : '—'}</td>
                        <td>{row.supporting_stats?.targets ? row.supporting_stats.targets.toFixed(1) : '—'}</td>
                        <td>{row.supporting_stats?.rec ? row.supporting_stats.rec.toFixed(1) : '—'}</td>
                      </>
                    )}
                    {dvpPosition === 'TE' && (
                      <>
                        <td>{row.supporting_stats?.rec_yds ? `${row.supporting_stats.rec_yds.toFixed(0)} yds` : '—'}</td>
                        <td>{row.supporting_stats?.rec_td ? row.supporting_stats.rec_td.toFixed(2) : '—'}</td>
                        <td>{row.supporting_stats?.targets ? row.supporting_stats.targets.toFixed(1) : '—'}</td>
                        <td>{row.supporting_stats?.rec ? row.supporting_stats.rec.toFixed(1) : '—'}</td>
                      </>
                    )}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
