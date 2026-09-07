import React, { useState, useEffect, useMemo } from 'react'
import {
  getFantasyProsPlayerUrl,
  isInjuryStatus,
} from './types'
import type {
  LeagueSummaryResponse,
  OptimizedLineupResult,
  WaiverAnalysisResult,
  ComparisonResult,
  ScoringWeights,
  ScoringSettings,
  BacktestReport,
  PreFlightPushPreview,
  LineupPushResponse,
  PlayerDirectoryItem,
  InjuryFeedResponse,
  StartSitEvaluation,
  MatchupResponseItem,
  ConsolidationTradeAnalysisResult,
  StreamerRecommendation,
  FactorScoreDetail,
} from './types'

const InstitutionalStatCard: React.FC<{ player: StartSitEvaluation; activeSource?: string }> = ({ player: p, activeSource = 'MODEL' }) => {
  const prov = p.model_provenance
  const currentActive = p.active_projection_source || activeSource || 'MODEL'
  const modelPts = p.proj_model ?? prov?.raw_model_ppr ?? p.projected_points
  const fpPts = p.proj_fantasypros ?? p.fp_r2p_pts ?? prov?.fantasypros_ppr
  const espnPts = p.proj_espn ?? prov?.espn_ppr
  const consensusPts = p.proj_consensus ?? prov?.consensus_ppr ?? p.projected_points
  
  // Real itemized stats from FantasyPros or Quant Model
  const stats: Record<string, any> = useMemo(() => {
    if (currentActive === 'FANTASYPROS' && p.fp_itemized_stats && Object.keys(p.fp_itemized_stats).length > 0) {
      const hasFpVolume = Object.entries(p.fp_itemized_stats).some(([k, v]) =>
        ['rush_att', 'rush_yds', 'rec_rec', 'receptions', 'pass_att', 'fg', 'def_sack'].includes(k) && Number(v) > 0
      )
      if (hasFpVolume) return p.fp_itemized_stats
    }
    return p.itemized_stats || p.fp_itemized_stats || {}
  }, [currentActive, p.fp_itemized_stats, p.itemized_stats])

  // Volatility calculations: realistic fantasy points floor and ceiling
  const floorPts = (p.floor_points && p.floor_points > 0 && p.floor_points < p.projected_points)
    ? p.floor_points
    : (p.floor_score && p.floor_score < p.projected_points && p.floor_score > 0)
      ? p.floor_score
      : Math.max(0, Math.round(p.projected_points * 0.65 * 10) / 10)

  const ceilingPts = (p.ceiling_points && p.ceiling_points > p.projected_points)
    ? p.ceiling_points
    : (p.ceiling_score && p.ceiling_score > p.projected_points && p.ceiling_score <= p.projected_points * 2.5)
      ? p.ceiling_score
      : Math.round(p.projected_points * 1.45 * 10) / 10

  const rangeSpan = Math.max(1, ceilingPts - floorPts)
  const markerPct = Math.min(100, Math.max(0, ((p.projected_points - floorPts) / rangeSpan) * 100))

  // Agreement indicator
  const spread = p.consensus_spread ?? (
    Math.max(modelPts || 0, fpPts || 0, espnPts || 0) - Math.min(modelPts || 999, fpPts || 999, espnPts || 999)
  )
  const agreement = p.consensus_agreement || (spread <= 2.2 ? 'HIGH_AGREEMENT' : spread <= 4.5 ? 'MODERATE' : 'SHARP_DIVERGENCE')

  return (
    <div className="institutional-stat-card">
      {/* Header Bar */}
      <div className="statcard-header">
        <div className="statcard-title-group">
          <span className="statcard-player-title">
            📊 {p.full_name} ({p.position} • {p.pro_team})
          </span>
          <span className="matchup-tag" style={{ fontSize: '11px' }}>
            {p.is_home ? 'vs' : '@'} {p.opponent}
          </span>
          {p.game_date && (
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              ⏰ {new Date(p.game_date).toLocaleDateString(undefined, { weekday: 'short', hour: 'numeric', minute: '2-digit' })}
            </span>
          )}
        </div>
        <div className="statcard-pills-row">
          {p.opp_dvp_rank && (
            <span
              className={`pill ${p.opp_dvp_rank <= 10 ? 'rose' : p.opp_dvp_rank >= 21 ? 'emerald' : 'amber'}`}
              style={{ fontSize: '11px', fontWeight: 700 }}
              title={`FantasyPros Consensus: Defense DvP #${p.opp_dvp_rank} vs ${p.position}`}
            >
              🛡️ DvP #{p.opp_dvp_rank}
            </span>
          )}
          {p.opp_dvp_rank && (
            <MatchupStarRating stars={p.matchup_stars} oppDvpRank={p.opp_dvp_rank} position={p.position} />
          )}
          {(p.fp_pos_rank || p.fp_rank_ecr) && (
            <span
              className="consensus-pill"
              title={`FantasyPros Consensus: ${p.fp_pos_rank || '#' + p.fp_rank_ecr} PPR`}
            >
              ⭐ FP {p.fp_pos_rank || `#${p.fp_rank_ecr}`}
            </span>
          )}
          {p.fp_tier && (
            <span className="pill zinc" style={{ fontSize: '11px' }}>
              Tier {p.fp_tier}
            </span>
          )}
        </div>
      </div>

      {/* 4-Way Multi-Source Projections Matrix */}
      <div className="multi-source-matrix">
        {/* Source 1: Quant Model */}
        <div className={`source-matrix-card ${currentActive === 'MODEL' ? 'active' : ''}`}>
          {currentActive === 'MODEL' && <span className="source-card-badge">ACTIVE CHOICE</span>}
          <div className="source-card-header">
            <span>⚡</span> Our Quant Model
          </div>
          <div className="source-card-pts">
            {modelPts ? `${modelPts.toFixed(1)}` : '—'} <span style={{ fontSize: '13px', fontWeight: 600 }}>pts</span>
          </div>
          <div className="source-card-sub">
            Vegas Micro-Volume Script
          </div>
        </div>

        {/* Source 2: FantasyPros */}
        <div className={`source-matrix-card ${currentActive === 'FANTASYPROS' ? 'active' : ''}`}>
          {currentActive === 'FANTASYPROS' && <span className="source-card-badge">ACTIVE CHOICE</span>}
          <div className="source-card-header">
            <span>🌐</span> FantasyPros (PPR)
          </div>
          <div className="source-card-pts">
            {fpPts ? `${fpPts.toFixed(1)}` : '—'} <span style={{ fontSize: '13px', fontWeight: 600 }}>pts</span>
          </div>
          <div className="source-card-sub">
            {p.consensus_rank ? `ECR #${p.consensus_rank.toFixed(0)} Consensus` : 'Weekly Consensus PPR'}
          </div>
        </div>

        {/* Source 3: ESPN Official */}
        <div className={`source-matrix-card ${currentActive === 'ESPN' ? 'active' : ''}`}>
          {currentActive === 'ESPN' && <span className="source-card-badge">ACTIVE CHOICE</span>}
          <div className="source-card-header">
            <span>🏈</span> ESPN Official
          </div>
          <div className="source-card-pts">
            {espnPts ? `${espnPts.toFixed(1)}` : '—'} <span style={{ fontSize: '13px', fontWeight: 600 }}>pts</span>
          </div>
          <div className="source-card-sub">
            ESPN Official League PPR
          </div>
        </div>

        {/* Source 4: 3-Way Consensus */}
        <div className={`source-matrix-card ${currentActive === 'CONSENSUS' ? 'active' : ''}`}>
          {currentActive === 'CONSENSUS' && <span className="source-card-badge">ACTIVE CHOICE</span>}
          <div className="source-card-header">
            <span>⭐</span> 3-Way Consensus
          </div>
          <div className="source-card-pts" style={{ color: currentActive === 'CONSENSUS' ? '#38bdf8' : '#facc15' }}>
            {consensusPts ? `${consensusPts.toFixed(1)}` : '—'} <span style={{ fontSize: '13px', fontWeight: 600 }}>pts</span>
          </div>
          <div className="source-card-sub">
            Outlier-Protected Bayesian
          </div>
        </div>
      </div>

      {/* Consensus Divergence Strip */}
      <div className="consensus-spread-strip">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span>⚖️ <strong>Expert Disparity:</strong></span>
          <span>
            {spread > 0 ? `±${(spread / 2).toFixed(1)} pts range (Spread: ${spread.toFixed(1)} pts)` : 'Unanimous Alignment'}
          </span>
        </div>
        <div>
          <span className={`pill ${agreement === 'HIGH_AGREEMENT' ? 'emerald' : agreement === 'MODERATE' ? 'amber' : 'rose'}`} style={{ fontSize: '11px' }}>
            {agreement === 'HIGH_AGREEMENT' ? '🟢 High Expert Agreement' : agreement === 'MODERATE' ? '🟡 Moderate Consensus' : '🔴 Sharp Expert Divergence'}
          </span>
        </div>
      </div>

      {/* Real Itemized Stats Section */}
      <div className="statcard-grid-title">
        <span>📈</span> Projected Box Score & Touch Volume (PPR Week 1)
      </div>
      <div className="statcard-itemized-grid">
        {p.position === 'QB' && (
          <>
            <div className="statcard-box">
              <span className="statcard-box-val">{(stats.pass_cmp ?? 0).toFixed(1)} / {(stats.pass_att ?? 0).toFixed(1)}</span>
              <span className="statcard-box-lbl">Pass Cmp / Att</span>
            </div>
            <div className="statcard-box highlight">
              <span className="statcard-box-val emerald">{(stats.pass_yds ?? 0).toFixed(1)}</span>
              <span className="statcard-box-lbl">Passing Yards</span>
            </div>
            <div className="statcard-box">
              <span className="statcard-box-val">{(stats.pass_td ?? stats.pass_tds ?? 0).toFixed(2)}</span>
              <span className="statcard-box-lbl">Passing TDs</span>
            </div>
            <div className="statcard-box">
              <span className="statcard-box-val">{(stats.pass_int ?? stats.pass_ints ?? 0).toFixed(2)}</span>
              <span className="statcard-box-lbl">Interceptions</span>
            </div>
            <div className="statcard-box">
              <span className="statcard-box-val">{(stats.rush_att ?? 0).toFixed(1)} car, {(stats.rush_yds ?? 0).toFixed(1)} yds</span>
              <span className="statcard-box-lbl">Rush Volume</span>
            </div>
          </>
        )}

        {p.position === 'RB' && (
          <>
            <div className="statcard-box highlight">
              <span className="statcard-box-val emerald">{(stats.rush_att ?? 0).toFixed(1)}</span>
              <span className="statcard-box-lbl">Projected Carries</span>
            </div>
            <div className="statcard-box">
              <span className="statcard-box-val">{(stats.rush_yds ?? 0).toFixed(1)}</span>
              <span className="statcard-box-lbl">Rushing Yards</span>
            </div>
            <div className="statcard-box">
              <span className="statcard-box-val">{(stats.rush_td ?? stats.rush_tds ?? 0).toFixed(2)}</span>
              <span className="statcard-box-lbl">Rushing TDs</span>
            </div>
            <div className="statcard-box highlight">
              <span className="statcard-box-val emerald">{
                (stats.targets !== undefined && stats.targets !== null && stats.targets > 0
                  ? stats.targets
                  : stats.receptions
                    ? Math.round((stats.receptions / 0.72) * 10) / 10
                    : stats.rec_rec
                      ? Math.round((stats.rec_rec / 0.72) * 10) / 10
                      : 0
                ).toFixed(1)
              }</span>
              <span className="statcard-box-lbl">Targets</span>
            </div>
            <div className="statcard-box">
              <span className="statcard-box-val">{(stats.receptions ?? stats.rec_rec ?? 0).toFixed(1)}</span>
              <span className="statcard-box-lbl">Receptions</span>
            </div>
            <div className="statcard-box">
              <span className="statcard-box-val">{(stats.rec_yds ?? 0).toFixed(1)}</span>
              <span className="statcard-box-lbl">Receiving Yards</span>
            </div>
            <div className="statcard-box">
              <span className="statcard-box-val">{(stats.rec_td ?? stats.rec_tds ?? 0).toFixed(2)}</span>
              <span className="statcard-box-lbl">Receiving TDs</span>
            </div>
          </>
        )}

        {(p.position === 'WR' || p.position === 'TE') && (
          <>
            <div className="statcard-box highlight">
              <span className="statcard-box-val emerald">{
                (stats.targets !== undefined && stats.targets !== null && stats.targets > 0
                  ? stats.targets
                  : stats.receptions
                    ? Math.round((stats.receptions / 0.72) * 10) / 10
                    : stats.rec_rec
                      ? Math.round((stats.rec_rec / 0.72) * 10) / 10
                      : 0
                ).toFixed(1)
              }</span>
              <span className="statcard-box-lbl">Projected Targets</span>
            </div>
            <div className="statcard-box">
              <span className="statcard-box-val">{(stats.receptions ?? stats.rec_rec ?? 0).toFixed(1)}</span>
              <span className="statcard-box-lbl">Receptions</span>
            </div>
            <div className="statcard-box highlight">
              <span className="statcard-box-val emerald">{(stats.rec_yds ?? 0).toFixed(1)}</span>
              <span className="statcard-box-lbl">Receiving Yards</span>
            </div>
            <div className="statcard-box">
              <span className="statcard-box-val">{(stats.rec_td ?? stats.rec_tds ?? 0).toFixed(2)}</span>
              <span className="statcard-box-lbl">Receiving TDs</span>
            </div>
            {(stats.targets || stats.receptions || stats.rec_rec) && (
              <div className="statcard-box">
                <span className="statcard-box-val">
                  {(() => {
                    const rec = stats.receptions ?? stats.rec_rec ?? 0
                    const tgt = stats.targets ?? (rec > 0 ? rec / 0.72 : 1)
                    return tgt > 0 ? `${Math.min(100, Math.round((rec / tgt) * 100))}%` : '—'
                  })()}
                </span>
                <span className="statcard-box-lbl">Catch Rate Exp</span>
              </div>
            )}
            {stats.rush_yds !== undefined && stats.rush_yds > 0 && (
              <div className="statcard-box">
                <span className="statcard-box-val">{stats.rush_yds.toFixed(1)} yds</span>
                <span className="statcard-box-lbl">Designed Rush</span>
              </div>
            )}
          </>
        )}

        {(p.position === 'K' || p.position === 'PK') && (
          <>
            <div className="statcard-box highlight">
              <span className="statcard-box-val emerald">{(stats.fg_made ?? stats.fg ?? 1.8).toFixed(1)}</span>
              <span className="statcard-box-lbl">Field Goals Made</span>
            </div>
            <div className="statcard-box">
              <span className="statcard-box-val">{(stats.pat_made ?? stats.xpt ?? 2.5).toFixed(1)}</span>
              <span className="statcard-box-lbl">PATs Made</span>
            </div>
          </>
        )}

        {(p.position === 'D/ST' || p.position === 'DST') && (
          <>
            <div className="statcard-box highlight">
              <span className="statcard-box-val emerald">{(stats.sacks ?? stats.def_sack ?? 2.4).toFixed(1)}</span>
              <span className="statcard-box-lbl">Projected Sacks</span>
            </div>
            <div className="statcard-box">
              <span className="statcard-box-val">{(stats.turnovers ?? (stats.def_int !== undefined ? (stats.def_int + (stats.def_fr || 0)) : 1.2)).toFixed(1)}</span>
              <span className="statcard-box-lbl">Turnovers Forced</span>
            </div>
            <div className="statcard-box">
              <span className="statcard-box-val">{(stats.pts_allowed ?? stats.def_pa ?? 21.0).toFixed(1)}</span>
              <span className="statcard-box-lbl">Expected Points Allowed</span>
            </div>
          </>
        )}

        <div className="statcard-box" style={{ background: 'rgba(56, 189, 248, 0.1)', borderColor: 'rgba(56, 189, 248, 0.3)' }}>
          <span className="statcard-box-val" style={{ color: '#38bdf8' }}>
            {p.projected_points.toFixed(2)} pts
          </span>
          <span className="statcard-box-lbl">Active Total ({currentActive})</span>
        </div>
      </div>

      {/* Probabilistic Volatility Range Track */}
      <div className="volatility-track-container">
        <div className="volatility-track-header">
          <span>🎯 PROBABILISTIC OUTCOME SPECTRUM</span>
          <span>Volatility Index: ±{p.fp_rank_std ? p.fp_rank_std.toFixed(1) : '1.2'}</span>
        </div>
        <div className="volatility-track-bar">
          <div className="volatility-track-marker" style={{ left: `${markerPct}%` }} title={`Active Projection: ${p.projected_points.toFixed(1)} pts`} />
        </div>
        <div className="volatility-track-labels">
          <span className="volatility-track-lbl floor">🛡️ 20th % Floor: {floorPts.toFixed(1)} pts</span>
          <span className="volatility-track-lbl median">🎯 Active: {p.projected_points.toFixed(1)} pts</span>
          <span className="volatility-track-lbl ceiling">🚀 90th % Ceiling: {ceilingPts.toFixed(1)} pts</span>
        </div>
      </div>

      {/* Vegas Macro & Matchup Provenance */}
      <div className="provenance-grid" style={{ marginTop: '12px' }}>
        <div className="provenance-col">
          <div className="provenance-col-title">
            <span>🏟️</span> Vegas Macro Script
          </div>
          <div className="provenance-item">
            <span>Implied Team Total:</span>
            <span className="provenance-val">{prov?.vegas_implied_team_total ? `${prov.vegas_implied_team_total.toFixed(1)} pts` : (p.implied_team_total ? `${p.implied_team_total.toFixed(1)} pts` : '22.5 pts')}</span>
          </div>
          <div className="provenance-item">
            <span>Spread Script:</span>
            <span className="provenance-val">
              {prov?.vegas_spread !== undefined
                ? `${prov.vegas_spread > 0 ? '+' : ''}${prov.vegas_spread.toFixed(1)} (${prov.vegas_spread <= 0 ? 'Favorite' : 'Underdog'})`
                : 'Pk'}
            </span>
          </div>
          <div className="provenance-item">
            <span>Expected Plays:</span>
            <span className="provenance-val">{p.team_projected_plays ? `${p.team_projected_plays.toFixed(1)}` : (prov?.team_expected_plays?.toFixed(1) || '63.5')}</span>
          </div>
        </div>

        <div className="provenance-col">
          <div className="provenance-col-title">
            <span>🎯</span> Matchup & Volume Leverage
          </div>
          <div className="provenance-item">
            <span>Volume Share:</span>
            <span className="provenance-val">
              {p.volume_share !== undefined && p.volume_share !== null
                ? `${(p.volume_share > 1.0 ? p.volume_share : p.volume_share * 100).toFixed(1)}% ${p.position === 'RB' ? 'Carries' : p.position === 'QB' ? 'Pass Base' : 'Targets'}`
                : '18.0% Share'}
            </span>
          </div>
          <div className="provenance-item">
            <span>Matchup Efficiency Adj:</span>
            <span className="provenance-val" style={{ color: (p.efficiency_multiplier ?? 0) >= 0 ? 'var(--accent-emerald)' : 'var(--accent-rose)' }}>
              {p.efficiency_multiplier !== undefined && p.efficiency_multiplier !== null
                ? `${p.efficiency_multiplier > 0 ? '+' : ''}${
                    Math.abs(p.efficiency_multiplier) <= 0.5 && p.efficiency_multiplier !== 0
                      ? ((p.efficiency_multiplier - 1) * 100).toFixed(1)
                      : p.efficiency_multiplier.toFixed(1)
                  }%`
                : '0.0%'}
            </span>
          </div>
          <div className="provenance-item">
            <span>Opponent Defense:</span>
            <span className="provenance-val">
              {p.position === 'D/ST' ? (p.opp_off_rank ? `Offense #${p.opp_off_rank}` : 'Avg') : (p.opp_def_rank ? `Def #${p.opp_def_rank}` : 'Avg')}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}


export function getMatchupStars(rankOrStars?: number | null, oppDvpRank?: number | null): number {
  if (typeof rankOrStars === 'number' && rankOrStars >= 1 && rankOrStars <= 5) {
    return rankOrStars
  }
  if (typeof oppDvpRank === 'number' && oppDvpRank >= 1 && oppDvpRank <= 32) {
    if (oppDvpRank <= 6) return 1
    if (oppDvpRank <= 12) return 2
    if (oppDvpRank <= 20) return 3
    if (oppDvpRank <= 26) return 4
    return 5
  }
  return 3
}

export function getMatchupTierInfo(stars: number, position?: string): { label: string; desc: string; dvpRange: string } {
  const isDst = position === 'D/ST' || position === 'DST'
  switch (stars) {
    case 1:
      return { 
        label: 'Bad Matchup', 
        desc: isDst ? 'Stifling offense rarely concedes sacks or turnovers' : 'Stingy defense allows minimal fantasy points', 
        dvpRange: 'DvP #1–6' 
      }
    case 2:
      return { 
        label: 'Tough Matchup', 
        desc: isDst ? 'Efficient offense with solid pass protection & ball security' : 'Below average matchup; stiff defensive resistance', 
        dvpRange: 'DvP #7–12' 
      }
    case 3:
      return { 
        label: 'Neutral Matchup', 
        desc: isDst ? 'Average turnover and sack rate expected' : 'Middle of the pack; standard baseline volume', 
        dvpRange: 'DvP #13–20' 
      }
    case 4:
      return { 
        label: 'Good Matchup', 
        desc: isDst ? 'Vulnerable offense prone to sacks and stalled drives' : 'Above average matchup; favorable defensive leaks', 
        dvpRange: 'DvP #21–26' 
      }
    case 5:
      return { 
        label: 'Amazing Matchup', 
        desc: isDst ? 'Prime streaming smash: High turnover/sack rate & low implied total' : 'Prime smash matchup; porous defense allows high ceiling', 
        dvpRange: 'DvP #27–32' 
      }
    default:
      return { label: 'Neutral Matchup', desc: 'Middle of the pack matchup', dvpRange: 'DvP #13–20' }
  }
}

export const MatchupStarRating: React.FC<{
  stars?: number | null
  oppDvpRank?: number | null
  position?: string
}> = ({ stars: propStars, oppDvpRank, position }) => {
  const stars = getMatchupStars(propStars, oppDvpRank)
  const tierInfo = getMatchupTierInfo(stars, position)

  return (
    <span
      className={`matchup-stars-badge tier-${stars}`}
      title={`FantasyPros Matchup Rating: ${stars}/5 Stars (${tierInfo.label})\n${tierInfo.desc}${oppDvpRank ? `\nOpponent DvP: #${oppDvpRank}${position ? ` vs ${position}` : ''}` : ''}`}
    >
      <span className="matchup-stars-row" aria-label={`${stars} of 5 stars`}>
        {[1, 2, 3, 4, 5].map((s) => (
          <span key={s} className={`star-icon ${s <= stars ? 'filled' : 'empty'}`}>
            ★
          </span>
        ))}
      </span>
      <span className="matchup-stars-text">{stars}/5</span>
    </span>
  )
}

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

export const MatchupRatingKey: React.FC<{

  isOpen: boolean
  onToggle: () => void
}> = ({ isOpen, onToggle }) => {
  const tiers = [
    { stars: 1, label: 'Bad Matchup', dvp: 'DvP #1–6', desc: 'Stifling Opponent (Fewest Pts Conceded)' },
    { stars: 2, label: 'Tough', dvp: 'DvP #7–12', desc: 'Below Average Matchup' },
    { stars: 3, label: 'Neutral', dvp: 'DvP #13–20', desc: 'Middle of the Pack' },
    { stars: 4, label: 'Good Matchup', dvp: 'DvP #21–26', desc: 'Above Average Matchup' },
    { stars: 5, label: 'Amazing Matchup', dvp: 'DvP #27–32', desc: 'Generous / Smash Matchup (Most Pts Conceded)' },
  ]

  return (
    <div className="matchup-key-banner">
      <div className="matchup-key-header" onClick={onToggle}>
        <div className="matchup-key-title-group">
          <span className="matchup-key-title">
            <span>⭐</span> FantasyPros Matchup Rating Key
          </span>
          <span className="matchup-key-subtitle">
            1 Star (Worst) to 5 Stars (Best) scale calibrated against Opponent Defense vs Position (DvP #1–32)
          </span>
        </div>
        <button
          type="button"
          className="matchup-key-toggle-btn"
          onClick={(e) => {
            e.stopPropagation()
            onToggle()
          }}
        >
          {isOpen ? '▲ Collapse Key' : '▼ View Rating Key'}
        </button>
      </div>

      {isOpen && (
        <div className="matchup-key-grid">
          {tiers.map((t) => (
            <div key={t.stars} className={`matchup-key-card tier-${t.stars}`}>
              <div className="matchup-key-card-header">
                <span className="matchup-stars-row">
                  {[1, 2, 3, 4, 5].map((s) => (
                    <span key={s} className={`star-icon ${s <= t.stars ? 'filled' : 'empty'}`}>
                      ★
                    </span>
                  ))}
                </span>
                <span className="matchup-stars-text">{t.stars}/5</span>
              </div>
              <div className={`matchup-key-card-label tier-${t.stars}`}>{t.label}</div>
              <div className="matchup-key-card-desc">
                <strong style={{ color: 'var(--text-primary)' }}>{t.dvp}</strong> • {t.desc}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>('lineup')
  const [league, setLeague] = useState<LeagueSummaryResponse | null>(null)
  const [selectedTeamId, setSelectedTeamId] = useState<number>(1)
  const [lineup, setLineup] = useState<OptimizedLineupResult | null>(null)
  const [waivers, setWaivers] = useState<WaiverAnalysisResult | null>(null)
  const [backtest, setBacktest] = useState<BacktestReport | null>(null)
  const [showMatchupKey, setShowMatchupKey] = useState<boolean>(true)
  const [weights, setWeights] = useState<ScoringWeights>({
    projection_weight: 0.35,
    opportunity_weight: 0.20,
    matchup_weight: 0.20,
    environment_weight: 0.10,
    health_weight: 0.10,
    weather_weight: 0.05,
  })

  // Strategy Mode (8-Man League Game Theory: Balanced, Ceiling, Floor, or Auto-Spread)
  const [strategyMode, setStrategyMode] = useState<'BALANCED' | 'CEILING' | 'FLOOR' | 'AUTO'>('BALANCED')
  const [leagueSizeSetting, setLeagueSizeSetting] = useState<number>(8)

  // Multi-Source Projections State (Quant Model, Consensus, FantasyPros, ESPN)
  const [projectionSource, setProjectionSource] = useState<'MODEL' | 'CONSENSUS' | 'FANTASYPROS' | 'ESPN'>('MODEL')

  // What-If Roster Bench-Swap Simulator State
  const [customSubstitutions, setCustomSubstitutions] = useState<Record<number, StartSitEvaluation>>({})
  const [activeSwapSlotIndex, setActiveSwapSlotIndex] = useState<number | null>(null)

  // 2-for-1 Consolidation Trades State
  const [consolidationTrades, setConsolidationTrades] = useState<ConsolidationTradeAnalysisResult | null>(null)
  const [isLoadingTrades, setIsLoadingTrades] = useState<boolean>(false)
  const [copiedPitchId, setCopiedPitchId] = useState<string | null>(null)

  // Comparison Tab State
  const [compareIds, setCompareIds] = useState<number[]>([])
  const [comparisonResult, setComparisonResult] = useState<ComparisonResult | null>(null)
  const [selectedRosterTeamId, setSelectedRosterTeamId] = useState<number>(1)
  const [teamRosterData, setTeamRosterData] = useState<any | null>(null)
  const [allPlayers, setAllPlayers] = useState<PlayerDirectoryItem[]>([])
  const [comparePosFilter, setComparePosFilter] = useState<string>('ALL')
  const [compareScope, setCompareScope] = useState<'roster' | 'all'>('roster')
  const [expandedCardFormula, setExpandedCardFormula] = useState<{ [playerId: number]: 'projection' | 'opportunity' | 'matchup' | 'environment' | 'all' | null }>({})

  const toggleFactorFormula = (playerId: number, factor: 'projection' | 'opportunity' | 'matchup' | 'environment' | 'all') => {
    setExpandedCardFormula((prev) => {
      const curr = prev[playerId]
      if (curr === factor) {
        const next = { ...prev }
        delete next[playerId]
        return next
      }
      return { ...prev, [playerId]: factor }
    })
  }


  // Live NFL Injury Wire State
  const [injuriesFeed, setInjuriesFeed] = useState<InjuryFeedResponse | null>(null)
  const [injurySearch, setInjurySearch] = useState<string>('')
  const [injuryPosFilter, setInjuryPosFilter] = useState<string>('ALL')
  const [injuryStatusFilter, setInjuryStatusFilter] = useState<string>('ALL')
  const [isLoadingInjuries, setIsLoadingInjuries] = useState<boolean>(false)

  // Sync / Loading state
  const [isSyncing, setIsSyncing] = useState<boolean>(false)
  const [syncMessage, setSyncMessage] = useState<string | null>(null)
  const [expandedWhy, setExpandedWhy] = useState<number | null>(null)
  const [expandedStatsPlayerId, setExpandedStatsPlayerId] = useState<number | null>(null)
  const [tuningMessage, setTuningMessage] = useState<string | null>(null)
  const [lineupViewMode, setLineupViewMode] = useState<'split' | 'unified'>('split')

  // 1-Click Lineup Push to ESPN State
  const [showPushModal, setShowPushModal] = useState<boolean>(false)
  const [pushPreview, setPushPreview] = useState<PreFlightPushPreview | null>(null)
  const [isPushing, setIsPushing] = useState<boolean>(false)
  const [pushResult, setPushResult] = useState<LineupPushResponse | null>(null)
  const [selectedMoveIds, setSelectedMoveIds] = useState<number[]>([])

  // Matchups & League Standings State
  const [matchups, setMatchups] = useState<MatchupResponseItem[]>([])
  const [matchupWeek, setMatchupWeek] = useState<number>(1)

  // FantasyPros ECR, Projections & Week State
  const [selectedFpWeek, setSelectedFpWeek] = useState<number>(1)
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


  // Initial load
  useEffect(() => {
    loadLeagueData()
    loadWeights()
    loadAllPlayers()
    loadInjuries()
  }, [])

  // Update default FantasyPros week when league data loads
  useEffect(() => {
    if (league?.current_week) {
      setSelectedFpWeek(league.current_week)
    }
  }, [league?.current_week])

  // Auto-load FantasyPros data when navigating to ECR tab or week changes
  useEffect(() => {
    if (activeTab === 'fantasypros') {
      if (fpViewMode === 'rankings') {
        loadFantasyProsRankings(fpPosFilter, selectedFpWeek)
      } else {
        loadFantasyProsProjections(fpPosFilter === 'TOP 100' ? 'RB' : fpPosFilter, selectedFpWeek)
      }
      loadFantasyProsStreamers(fpStreamerPos, selectedFpWeek)
    }
  }, [activeTab, selectedFpWeek, fpViewMode])

  // When matchupWeek changes, fetch matchups
  useEffect(() => {
    loadMatchups(matchupWeek)
  }, [matchupWeek])

  const loadMatchups = async (week: number) => {
    try {
      const res = await fetch(`/api/league/matchups?week=${week}`)
      if (res.ok) {
        const data: MatchupResponseItem[] = await res.json()
        setMatchups(data)
      }
    } catch (err) {
      console.error('Failed to load matchups:', err)
    }
  }

  // When selected team changes, fetch new lineup, waivers, and consolidation trades
  useEffect(() => {
    if (selectedTeamId) {
      loadTeamLineup(selectedTeamId)
      loadWaivers(selectedTeamId)
      loadBacktestReport(selectedTeamId)
      loadConsolidationTrades(selectedTeamId)
    }
  }, [selectedTeamId])

  const loadConsolidationTrades = async (teamId: number) => {
    setIsLoadingTrades(true)
    try {
      const res = await fetch(`/api/recommendation/trades/consolidation?team_id=${teamId}`)
      if (res.ok) {
        const data: ConsolidationTradeAnalysisResult = await res.json()
        setConsolidationTrades(data)
      }
    } catch (err) {
      console.error('Failed to load consolidation trades:', err)
    } finally {
      setIsLoadingTrades(false)
    }
  }

  const loadBacktestReport = async (teamId: number) => {
    try {
      const res = await fetch(`/api/backtest/report?team_id=${teamId}`)
      if (res.ok) {
        const data: BacktestReport = await res.json()
        setBacktest(data)
      }
    } catch (err) {
      console.error('Failed to load backtest report:', err)
    }
  }

  // Load team roster when team roster tab selection changes
  useEffect(() => {
    if (selectedRosterTeamId) {
      loadTeamRoster(selectedRosterTeamId)
    }
  }, [selectedRosterTeamId])

  const loadLeagueData = async () => {
    try {
      const res = await fetch('/api/league/summary')
      if (res.ok) {
        const data: LeagueSummaryResponse = await res.json()
        setLeague(data)
        const userTeam = data.user_team_id || (data.teams.length > 0 ? data.teams[0].id : 1)
        setSelectedTeamId(userTeam)
        setSelectedRosterTeamId(userTeam)
        const currentWeek = data.current_week || 1
        setMatchupWeek(currentWeek)
        loadMatchups(currentWeek)
      } else {
        // Auto-sync with ESPN if DB is empty
        await handleSync(true)
      }
    } catch {
      await handleSync(true)
    }
  }

  const loadTeamLineup = async (teamId: number, mode?: string, source?: string) => {
    try {
      const activeMode = mode || strategyMode
      const activeSource = source || projectionSource
      const res = await fetch(`/api/lineup/optimal?team_id=${teamId}&mode=${activeMode}&projection_source=${activeSource}`)
      if (res.ok) {
        const data: OptimizedLineupResult = await res.json()
        setLineup(data)
        setCustomSubstitutions({})
        setActiveSwapSlotIndex(null)
        // Default comparator candidates to close call or top positional dilemma on team
        if (compareIds.length === 0) {
          if (data.close_calls && data.close_calls.length > 0) {
            const cc = data.close_calls[0]
            const ids = [cc.starter.player_id, cc.bench_player.player_id]
            setCompareIds(ids)
            runComparison(ids, activeMode)
          } else if (data.starters.length > 0 && data.bench.length > 0) {
            const benchCand = data.bench[0]
            const matchingStarter = data.starters.find(
              (s) => s.recommended_player.position === benchCand.position || ['RB', 'WR', 'TE'].includes(benchCand.position)
            )
            const starterId = matchingStarter ? matchingStarter.recommended_player.player_id : data.starters[0].recommended_player.player_id
            const ids = [starterId, benchCand.player_id]
            setCompareIds(ids)
            runComparison(ids, activeMode)
          }
        }
      }
    } catch (err) {
      console.error('Error loading lineup:', err)
    }
  }

  const handleProjectionSourceChange = (newSource: 'MODEL' | 'CONSENSUS' | 'FANTASYPROS' | 'ESPN') => {
    setProjectionSource(newSource)
    loadTeamLineup(selectedTeamId, strategyMode, newSource)
  }

  // Calculate effective starters and bench considering manual user substitutions
  const { effectiveStarters, effectiveBench, customGainVsOptimal, hasCustomSwaps, currentLineupProjectedTotal } = useMemo(() => {
    if (!lineup) {
      return {
        effectiveStarters: [],
        effectiveBench: [],
        customGainVsOptimal: 0,
        hasCustomSwaps: false,
        currentLineupProjectedTotal: 0,
      }
    }

    const substitutedStarterOriginals: StartSitEvaluation[] = []
    const substitutedBenchPlayerIds: number[] = []

    const effectiveStarters = lineup.starters.map((slot, idx) => {
      if (customSubstitutions[idx]) {
        const benchReplacement = customSubstitutions[idx]
        substitutedStarterOriginals.push(slot.recommended_player)
        substitutedBenchPlayerIds.push(benchReplacement.player_id)
        const starterPts = slot.recommended_player.projected_points
        const benchPts = benchReplacement.projected_points
        return {
          ...slot,
          is_custom_swap: true,
          original_recommended: slot.recommended_player,
          recommended_player: benchReplacement,
          net_projected_delta: Math.round((benchPts - (slot.current_starter?.projected_points ?? starterPts)) * 10) / 10,
        }
      }
      return {
        ...slot,
        is_custom_swap: false,
        original_recommended: slot.recommended_player,
      }
    })

    let effectiveBench = lineup.bench.filter((b) => !substitutedBenchPlayerIds.includes(b.player_id))
    effectiveBench = [...effectiveBench, ...substitutedStarterOriginals]

    const optimalTotal = lineup.starters.reduce((sum, s) => sum + s.recommended_player.projected_points, 0)
    const currentTotal = effectiveStarters.reduce((sum, s) => sum + s.recommended_player.projected_points, 0)
    const customGainVsOptimal = Math.round((currentTotal - optimalTotal) * 10) / 10

    return {
      effectiveStarters,
      effectiveBench,
      customGainVsOptimal,
      hasCustomSwaps: Object.keys(customSubstitutions).length > 0,
      currentLineupProjectedTotal: Math.round(currentTotal * 10) / 10,
    }
  }, [lineup, customSubstitutions])

  const getEligibleBenchForSlot = (slotName: string, benchList: StartSitEvaluation[]) => {
    if (slotName === 'QB') return benchList.filter((b) => b.position === 'QB')
    if (slotName === 'RB') return benchList.filter((b) => b.position === 'RB')
    if (slotName === 'WR') return benchList.filter((b) => b.position === 'WR')
    if (slotName === 'TE') return benchList.filter((b) => b.position === 'TE')
    if (slotName === 'FLEX') return benchList.filter((b) => ['RB', 'WR', 'TE'].includes(b.position))
    if (slotName === 'KICKER' || slotName === 'K') return benchList.filter((b) => ['K', 'PK'].includes(b.position))
    if (slotName === 'DEFENSE' || slotName === 'DST' || slotName === 'D/ST') return benchList.filter((b) => ['DST', 'D/ST', 'DEF'].includes(b.position))
    return benchList
  }

  const handlePerformSwap = (slotIdx: number, benchPlayer: StartSitEvaluation) => {
    setCustomSubstitutions((prev) => ({
      ...prev,
      [slotIdx]: benchPlayer,
    }))
    setActiveSwapSlotIndex(null)
  }

  const handleRevertSlot = (slotIdx: number) => {
    setCustomSubstitutions((prev) => {
      const next = { ...prev }
      delete next[slotIdx]
      return next
    })
  }

  const handleResetToOptimal = () => {
    setCustomSubstitutions({})
    setActiveSwapSlotIndex(null)
  }

  const loadWaivers = async (teamId: number) => {
    try {
      const res = await fetch(`/api/waiver/upgrades?team_id=${teamId}`)
      if (res.ok) {
        const data: WaiverAnalysisResult = await res.json()
        setWaivers(data)
      }
    } catch (err) {
      console.error('Error loading waivers:', err)
    }
  }

  const loadTeamRoster = async (teamId: number) => {
    try {
      const res = await fetch(`/api/league/teams/${teamId}/roster`)
      if (res.ok) {
        const data = await res.json()
        setTeamRosterData(data)
      }
    } catch (err) {
      console.error('Error loading team roster:', err)
    }
  }

  const loadWeights = async () => {
    try {
      const res = await fetch('/api/recommendation/settings')
      if (res.ok) {
        const data: ScoringSettings = await res.json()
        setWeights(data.weights)
        setLeagueSizeSetting(data.league_size)
      } else {
        const fallbackRes = await fetch('/api/recommendation/weights')
        if (fallbackRes.ok) {
          const data: ScoringWeights = await fallbackRes.json()
          setWeights(data)
        }
      }
    } catch (err) {
      console.error('Error loading weights/settings:', err)
    }
  }

  const handleSync = async (force: boolean = false) => {
    if (isSyncing) return
    setIsSyncing(true)
    setSyncMessage(null)
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 45000)
    try {
      const res = await fetch(`/api/league/sync?force=${force}`, {
        method: 'POST',
        signal: controller.signal,
      })
      const data = await res.json()
      setSyncMessage(data.message)
      // Reload league data
      const summaryRes = await fetch('/api/league/summary', { signal: controller.signal })
      if (summaryRes.ok) {
        const summaryData: LeagueSummaryResponse = await summaryRes.json()
        setLeague(summaryData)
        const teamId = summaryData.user_team_id || (summaryData.teams.length > 0 ? summaryData.teams[0].id : 1)
        setSelectedTeamId(teamId)
        loadTeamLineup(teamId)
        loadWaivers(teamId)
        loadAllPlayers()
        loadInjuries()
        loadMatchups(summaryData.current_week || 1)
      }
    } catch (err: any) {
      if (err?.name === 'AbortError') {
        setSyncMessage('Sync timed out after 45 seconds. Check connection and try again.')
      } else {
        setSyncMessage(`Sync failed: ${err?.message || err}`)
      }
    } finally {
      clearTimeout(timeoutId)
      setIsSyncing(false)
    }
  }

  const loadAllPlayers = async () => {
    try {
      const res = await fetch('/api/league/players')
      if (res.ok) {
        const data: PlayerDirectoryItem[] = await res.json()
        setAllPlayers(data)
      }
    } catch (err) {
      console.error('Failed to load players directory:', err)
    }
  }

  const loadInjuries = async () => {
    setIsLoadingInjuries(true)
    try {
      const res = await fetch('/api/injuries?limit=250')
      if (res.ok) {
        const data: InjuryFeedResponse = await res.json()
        setInjuriesFeed(data)
      }
    } catch (err) {
      console.error('Failed to load injuries:', err)
    } finally {
      setIsLoadingInjuries(false)
    }
  }

  const runComparison = async (ids: number[], mode?: string) => {
    if (ids.length < 2) return
    try {
      const activeMode = mode || strategyMode
      const res = await fetch('/api/recommendation/compare', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ player_ids: ids, mode: activeMode }),
      })
      if (res.ok) {
        const data: ComparisonResult = await res.json()
        setComparisonResult(data)
      }
    } catch (err) {
      console.error('Comparison error:', err)
    }
  }

  const handlePlayerSelect = (index: number, newId: number) => {
    const next = [...compareIds]
    next[index] = newId
    setCompareIds(next)
    runComparison(next, strategyMode)
  }

  const handleStrategyChange = (newMode: 'BALANCED' | 'CEILING' | 'FLOOR' | 'AUTO') => {
    setStrategyMode(newMode)
    loadTeamLineup(selectedTeamId, newMode, projectionSource)
    if (compareIds.length >= 2) {
      runComparison(compareIds, newMode)
    }
  }

  const handleSwapPlayers = () => {
    if (compareIds.length >= 2) {
      const next = [compareIds[1], compareIds[0], ...compareIds.slice(2)]
      setCompareIds(next)
      runComparison(next)
    }
  }

  const handleAddComparePlayer = () => {
    if (compareIds.length >= 4) return
    const pool = compareScope === 'roster' ? currentTeamPlayers : allPlayers
    const candidate = pool.find((p) => !compareIds.includes(p.id))
    if (candidate) {
      const next = [...compareIds, candidate.id]
      setCompareIds(next)
      runComparison(next)
    }
  }

  const handleRemoveComparePlayer = (index: number) => {
    if (compareIds.length <= 2) return
    const next = compareIds.filter((_, i) => i !== index)
    setCompareIds(next)
    runComparison(next)
  }

  // Focused team metadata
  const focusedTeamName = league?.teams.find((t) => t.id === selectedTeamId)?.name || 'My Team'

  // Filter players for comparator dropdowns based on position filter
  const filteredPlayersForDropdown = allPlayers.filter((p) => {
    if (comparePosFilter === 'ALL') return true
    if (comparePosFilter === 'FLEX') return ['RB', 'WR', 'TE'].includes(p.position)
    return p.position === comparePosFilter
  })

  // Selected team's roster (strictly focused team, defaults to user's team)
  const currentTeamPlayers = filteredPlayersForDropdown.filter((p) => p.team_id === selectedTeamId)
  const myStarters = currentTeamPlayers.filter((p) => p.is_starter)
  const myBench = currentTeamPlayers.filter((p) => !p.is_starter)
  const freeAgents = filteredPlayersForDropdown.filter((p) => p.is_free_agent)
  const otherTeams = filteredPlayersForDropdown.filter((p) => p.team_id !== selectedTeamId && !p.is_free_agent)

  // Roster Dilemmas for 1-Click shortcuts
  const rosterDilemmas = useMemo(() => {
    if (!lineup) return []
    const dilemmas: Array<{
      id: string
      label: string
      slotName: string
      starterId: number
      starterName: string
      benchId: number
      benchName: string
      delta: number
      isCloseCall: boolean
    }> = []

    // 1. Add close calls flagged by the optimizer
    lineup.close_calls.forEach((cc, idx) => {
      dilemmas.push({
        id: `cc-${idx}`,
        label: `${cc.starter.full_name} vs ${cc.bench_player.full_name}`,
        slotName: cc.slot_name,
        starterId: cc.starter.player_id,
        starterName: cc.starter.full_name,
        benchId: cc.bench_player.player_id,
        benchName: cc.bench_player.full_name,
        delta: Math.abs(Math.round((cc.starter.start_score - cc.bench_player.start_score) * 10) / 10),
        isCloseCall: true,
      })
    })

    // 2. Add same-position starter vs bench battles
    const starterPlayers = lineup.starters.map((s) => s.recommended_player)
    lineup.bench.forEach((b) => {
      const match = starterPlayers.find((s) => s.position === b.position)
      if (match && !dilemmas.some((d) => d.starterId === match.player_id && d.benchId === b.player_id)) {
        const delta = Math.abs(Math.round((match.start_score - b.start_score) * 10) / 10)
        dilemmas.push({
          id: `pos-${match.player_id}-${b.player_id}`,
          label: `${match.full_name} vs ${b.full_name}`,
          slotName: b.position,
          starterId: match.player_id,
          starterName: match.full_name,
          benchId: b.player_id,
          benchName: b.full_name,
          delta,
          isCloseCall: delta <= 5.0,
        })
      }
    })

    return dilemmas.slice(0, 6)
  }, [lineup])

  const handleSelectDilemma = (starterId: number, benchId: number) => {
    setCompareScope('roster')
    const ids = [starterId, benchId]
    setCompareIds(ids)
    runComparison(ids)
  }

  const handleScopeChange = (newScope: 'roster' | 'all') => {
    setCompareScope(newScope)
    if (newScope === 'roster' && currentTeamPlayers.length >= 2) {
      const validIds = compareIds.filter((id) => currentTeamPlayers.some((p) => p.id === id))
      if (validIds.length < 2) {
        const newIds: number[] = []
        if (myStarters.length > 0) newIds.push(myStarters[0].id)
        if (myBench.length > 0) newIds.push(myBench[0].id)
        else if (myStarters.length > 1) newIds.push(myStarters[1].id)
        if (newIds.length >= 2) {
          setCompareIds(newIds)
          runComparison(newIds)
        }
      }
    }
  }

  const handleCompareBenchWithStarter = (benchPlayer: StartSitEvaluation) => {
    if (!lineup) return
    let targetStarter: StartSitEvaluation | null = null
    const samePosStarters = lineup.starters
      .map((s) => s.recommended_player)
      .filter((s) => s.position === benchPlayer.position)
      .sort((a, b) => a.start_score - b.start_score)

    if (samePosStarters.length > 0) {
      targetStarter = samePosStarters[0]
    } else if (['RB', 'WR', 'TE'].includes(benchPlayer.position)) {
      const flexStarters = lineup.starters
        .map((s) => s.recommended_player)
        .filter((s) => ['RB', 'WR', 'TE'].includes(s.position))
        .sort((a, b) => a.start_score - b.start_score)
      if (flexStarters.length > 0) {
        targetStarter = flexStarters[0]
      }
    }

    if (!targetStarter && lineup.starters.length > 0) {
      targetStarter = lineup.starters[0].recommended_player
    }

    if (targetStarter) {
      setCompareScope('roster')
      const ids = [targetStarter.player_id, benchPlayer.player_id]
      setCompareIds(ids)
      runComparison(ids)
      setActiveTab('compare')
    }
  }

  const handleCompareStarterWithBench = (starterPlayer: StartSitEvaluation) => {
    if (!lineup) return
    let challenger: StartSitEvaluation | null = null
    const samePosBench = lineup.bench
      .filter((b) => b.position === starterPlayer.position)
      .sort((a, b) => b.start_score - a.start_score)

    if (samePosBench.length > 0) {
      challenger = samePosBench[0]
    } else if (['RB', 'WR', 'TE'].includes(starterPlayer.position)) {
      const flexBench = lineup.bench
        .filter((b) => ['RB', 'WR', 'TE'].includes(b.position))
        .sort((a, b) => b.start_score - a.start_score)
      if (flexBench.length > 0) {
        challenger = flexBench[0]
      }
    }

    if (!challenger && lineup.bench.length > 0) {
      challenger = lineup.bench[0]
    }

    if (challenger) {
      setCompareScope('roster')
      const ids = [starterPlayer.player_id, challenger.player_id]
      setCompareIds(ids)
      runComparison(ids)
      setActiveTab('compare')
    }
  }

  // Filtered injuries for Tab 5
  const filteredInjuries = (injuriesFeed?.injuries || []).filter((inj) => {
    if (injurySearch && !inj.name.toLowerCase().includes(injurySearch.toLowerCase()) && !inj.team.toLowerCase().includes(injurySearch.toLowerCase())) {
      return false
    }
    if (injuryPosFilter !== 'ALL' && inj.position.toUpperCase() !== injuryPosFilter) {
      return false
    }
    if (injuryStatusFilter !== 'ALL') {
      if (injuryStatusFilter === 'OUT' && !inj.is_out) return false
      if (injuryStatusFilter === 'QUESTIONABLE' && !inj.status.toUpperCase().includes('QUESTIONABLE')) return false
      if (injuryStatusFilter === 'ACTIVE' && (inj.is_out || inj.status.toUpperCase().includes('QUESTIONABLE'))) return false
    }
    return true
  })

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
        loadLeagueData()
        if (selectedTeamId) {
          loadTeamLineup(selectedTeamId, strategyMode)
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

  const handleWeightChange = (key: keyof ScoringWeights, val: number) => {

    setWeights(prev => ({ ...prev, [key]: val }))
  }

  const saveWeights = async () => {
    try {
      const res = await fetch('/api/recommendation/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ league_size: leagueSizeSetting, weights }),
      })
      if (res.ok) {
        const updated: ScoringSettings = await res.json()
        setWeights(updated.weights)
        setLeagueSizeSetting(updated.league_size)
        // Re-optimize current lineup
        loadTeamLineup(selectedTeamId, strategyMode)
      }
    } catch (err) {
      console.error('Failed to save settings:', err)
    }
  }

  const runBacktesting = async () => {
    try {
      const res = await fetch(`/api/backtest/tune?team_id=${selectedTeamId}`, { method: 'POST' })
      if (res.ok) {
        const data = await res.json()
        setWeights(data.optimized_weights)
        setTuningMessage(data.message)
        loadTeamLineup(selectedTeamId)
        loadBacktestReport(selectedTeamId)
      }
    } catch (err) {
      setTuningMessage(`Tuning failed: ${err}`)
    }
  }

  const handleOpenPushModal = async () => {
    setIsPushing(true)
    setPushResult(null)
    try {
      const res = await fetch('/api/lineup/push', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          team_id: selectedTeamId,
          confirm: false,
          mode: strategyMode,
          projection_source: projectionSource,
          custom_starter_ids: hasCustomSwaps ? effectiveStarters.map((s) => s.recommended_player.player_id) : undefined,
        }),
      })
      if (res.ok) {
        const preview: PreFlightPushPreview = await res.json()
        setPushPreview(preview)
        setSelectedMoveIds(preview.moves.map((m) => m.player_id))
        setShowPushModal(true)
      }
    } catch (err) {
      console.error('Error getting pre-flight push preview:', err)
    } finally {
      setIsPushing(false)
    }
  }

  const handleExecutePush = async () => {
    if (!pushPreview) return
    setIsPushing(true)
    try {
      const movesToPush = pushPreview.moves
        .filter((m) => selectedMoveIds.includes(m.player_id))
        .map((m) => ({
          player_id: m.player_id,
          from_slot_id: m.from_slot_id,
          to_slot_id: m.to_slot_id,
        }))

      const res = await fetch('/api/lineup/push', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          team_id: selectedTeamId,
          confirm: true,
          mode: strategyMode,
          projection_source: projectionSource,
          custom_starter_ids: hasCustomSwaps ? effectiveStarters.map((s) => s.recommended_player.player_id) : undefined,
          selected_moves: movesToPush,
        }),
      })

      const data: LineupPushResponse = await res.json()
      setPushResult(data)
      if (data.success) {
        await loadTeamLineup(selectedTeamId, strategyMode, projectionSource)
        await loadLeagueData()
      }
    } catch (err) {
      setPushResult({
        success: false,
        message: `Failed to push lineup: ${err}`,
        moves_executed: 0,
        team_id: selectedTeamId,
      })
    } finally {
      setIsPushing(false)
    }
  }

  const toggleMoveSelection = (playerId: number) => {
    setSelectedMoveIds((prev) =>
      prev.includes(playerId) ? prev.filter((id) => id !== playerId) : [...prev, playerId]
    )
  }

  const getScoreColorClass = (score: number) => {
    if (score >= 80) return 'emerald'
    if (score >= 65) return 'cyan'
    if (score >= 50) return 'amber'
    return 'rose'
  }

  return (
    <div className="app-container">
      {/* App Header */}
      <header className="app-header">
        <div className="brand-section">
          <div className="brand-icon">🏈</div>
          <div>
            <h1 className="brand-title">Apex Fantasy Analytics</h1>
            <div className="brand-subtitle" style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              <span>{league ? `${league.name} • Season ${league.season} (Week ${league.current_week})` : '2026 Season'}</span>
              <span className="pill cyan" style={{ fontSize: '11px', padding: '2px 8px' }}>
                ⚡ 8-Team PPR Calibrated
              </span>
            </div>
          </div>
        </div>

        <div className="header-status">
          {/* Team Switcher */}
          {league && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Focus Team:</span>
              <select
                className="select-dropdown"
                value={selectedTeamId}
                onChange={(e) => setSelectedTeamId(Number(e.target.value))}
              >
                {league.teams.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}{t.primary_owner ? ` (${t.primary_owner})` : ''} • {t.record} {t.is_user_team ? '★ (My Team)' : ''}
                  </option>
                ))}
              </select>
            </div>
          )}

          <button
            className="btn btn-primary btn-sm"
            onClick={() => handleSync(true)}
            disabled={isSyncing}
          >
            {isSyncing ? '⏳ Syncing...' : '🔄 Sync ESPN Now'}
          </button>
        </div>
      </header>

      {syncMessage && (
        <div className="diag-box info" style={{ marginBottom: '20px' }}>
          {syncMessage}
        </div>
      )}

      {/* Main Tab Navigation */}
      <nav className="tab-nav">
        <button
          className={`tab-btn ${activeTab === 'lineup' ? 'active' : ''}`}
          onClick={() => setActiveTab('lineup')}
        >
          🏈 Optimal Lineup
          {lineup && lineup.differences_count > 0 && (
            <span className="badge-count">{lineup.differences_count} Diffs</span>
          )}
        </button>

        <button
          className={`tab-btn ${activeTab === 'compare' ? 'active' : ''}`}
          onClick={() => setActiveTab('compare')}
        >
          ⚖️ Start/Sit Comparator
        </button>

        <button
          className={`tab-btn ${activeTab === 'waivers' ? 'active' : ''}`}
          onClick={() => setActiveTab('waivers')}
        >
          🔄 Waiver Upgrades
          {waivers && waivers.top_upgrades.length > 0 && (
            <span className="badge-count emerald">+{waivers.top_upgrades.length}</span>
          )}
        </button>

        <button
          className={`tab-btn ${activeTab === 'trades' ? 'active' : ''}`}
          onClick={() => {
            setActiveTab('trades')
            if (!consolidationTrades && selectedTeamId) {
              loadConsolidationTrades(selectedTeamId)
            }
          }}
        >
          🤝 2-for-1 Trades
          {consolidationTrades && consolidationTrades.recommendations.length > 0 && (
            <span className="badge-count amber">+{consolidationTrades.recommendations.length}</span>
          )}
        </button>

        <button
          className={`tab-btn ${activeTab === 'league' ? 'active' : ''}`}
          onClick={() => setActiveTab('league')}
        >
          👥 League Rosters
        </button>

        <button
          className={`tab-btn ${activeTab === 'injuries' ? 'active' : ''}`}
          onClick={() => setActiveTab('injuries')}
        >
          🩺 Injury Wire
        </button>

        <button
          className={`tab-btn ${activeTab === 'fantasypros' ? 'active' : ''}`}
          onClick={() => {
            setActiveTab('fantasypros')
            loadFantasyProsRankings(fpPosFilter)
            loadFantasyProsStreamers(fpStreamerPos)
          }}
        >
          ⭐ FantasyPros ECR
        </button>

        <button
          className={`tab-btn ${activeTab === 'settings' ? 'active' : ''}`}
          onClick={() => setActiveTab('settings')}
        >
          ⚙️ Settings & Weights
        </button>
      </nav>


      {/* TAB 1: OPTIMAL LINEUP */}
      {activeTab === 'lineup' && (
        <div>
          {/* Multi-Source Projection Selector Card */}
          <div className="projection-source-card">
            <div className="projection-source-header">
              <div className="projection-source-title-group">
                <span style={{ fontSize: '18px' }}>📊</span>
                <div>
                  <div className="projection-source-label">
                    Projection Source Engine:
                    <span style={{ color: '#38bdf8', marginLeft: '6px' }}>
                      {projectionSource === 'MODEL' ? 'Our Quant Model (Default)' : projectionSource === 'CONSENSUS' ? '3-Way Consensus (Model + FP + ESPN)' : projectionSource === 'FANTASYPROS' ? 'FantasyPros (PPR)' : 'ESPN Official'}
                    </span>
                  </div>
                  <div className="projection-source-desc">
                    Re-solves optimal lineup & displays individual source stats for Week 1 (PPR scoring)
                  </div>
                </div>
              </div>
              <div className="source-selector-pills">
                <button
                  className={`source-pill-btn ${projectionSource === 'MODEL' ? 'active' : ''}`}
                  onClick={() => handleProjectionSourceChange('MODEL')}
                  title="Our Quantitative Vegas micro-volume script projection engine"
                >
                  ⚡ Quant Model {lineup?.total_model_projected ? `(${lineup.total_model_projected.toFixed(1)})` : ''}
                </button>
                <button
                  className={`source-pill-btn ${projectionSource === 'CONSENSUS' ? 'active' : ''}`}
                  onClick={() => handleProjectionSourceChange('CONSENSUS')}
                  title="Outlier-Protected Trimmed Bayesian Consensus: 40% Model + 40% FantasyPros + 20% ESPN"
                >
                  ⭐ 3-Way Consensus {lineup?.total_consensus_projected ? `(${lineup.total_consensus_projected.toFixed(1)})` : ''}
                </button>
                <button
                  className={`source-pill-btn ${projectionSource === 'FANTASYPROS' ? 'active' : ''}`}
                  onClick={() => handleProjectionSourceChange('FANTASYPROS')}
                  title="FantasyPros Multi-Expert ECR Consensus PPR Projections"
                >
                  🌐 FantasyPros {lineup?.total_fp_projected ? `(${lineup.total_fp_projected.toFixed(1)})` : ''}
                </button>
                <button
                  className={`source-pill-btn ${projectionSource === 'ESPN' ? 'active' : ''}`}
                  onClick={() => handleProjectionSourceChange('ESPN')}
                  title="ESPN Official League Projections"
                >
                  🏈 ESPN {lineup?.total_espn_projected ? `(${lineup.total_espn_projected.toFixed(1)})` : ''}
                </button>
              </div>
            </div>
          </div>

          {/* Strategy Mode Switcher Bar */}
          <div className="strategy-selector-bar">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '14px' }}>🎯</span>
              <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)' }}>
                Game-Theory Mode:
              </span>
            </div>
            <div className="strategy-selector">
              <button
                className={`strategy-pill-btn auto ${strategyMode === 'AUTO' ? 'active' : ''}`}
                onClick={() => handleStrategyChange('AUTO')}
                title="Automatically calculates matchup spread against your weekly opponent and selects Ceiling (underdog) or Floor (favorite)"
              >
                🤖 Auto-Spread (AI Game Theory)
              </button>
              <button
                className={`strategy-pill-btn balanced ${strategyMode === 'BALANCED' ? 'active' : ''}`}
                onClick={() => handleStrategyChange('BALANCED')}
              >
                🎯 Balanced (Standard)
              </button>
              <button
                className={`strategy-pill-btn ceiling ${strategyMode === 'CEILING' ? 'active' : ''}`}
                onClick={() => handleStrategyChange('CEILING')}
                title="Weights 90th percentile boom ceiling (air yards, shootout environments, goal line work) for underdog matchups"
              >
                🚀 Ceiling Mode (Underdog Boom)
              </button>
              <button
                className={`strategy-pill-btn floor ${strategyMode === 'FLOOR' ? 'active' : ''}`}
                onClick={() => handleStrategyChange('FLOOR')}
                title="Weights 20th percentile safe floor (stable touches, health certainty, high route participation) for favorite matchups"
              >
                🛡️ Floor Mode (Favorite Safe)
              </button>
            </div>
          </div>

          {/* What-If Interactive Lineup Sandbox Banner */}
          {hasCustomSwaps && (
            <div className="sandbox-banner">
              <div className="sandbox-banner-content">
                <span style={{ fontSize: '24px' }}>🧪</span>
                <div>
                  <div className="sandbox-banner-title">
                    Interactive What-If Roster Active ({Object.keys(customSubstitutions).length} Custom Swap{Object.keys(customSubstitutions).length > 1 ? 's' : ''})
                  </div>
                  <div className="sandbox-banner-sub">
                    Modified Roster Total: <strong style={{ color: '#ffffff' }}>{currentLineupProjectedTotal} pts</strong>{' '}
                    <span style={{ color: customGainVsOptimal >= 0 ? '#10b981' : '#f43f5e', fontWeight: 700 }}>
                      ({customGainVsOptimal >= 0 ? `+${customGainVsOptimal}` : customGainVsOptimal} pts vs Algorithmic Optimal)
                    </span>
                  </div>
                </div>
              </div>
              <div className="sandbox-banner-actions">
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={handleResetToOptimal}
                  title="Revert all custom substitutions back to the algorithmic optimal starters"
                >
                  🔄 Reset to Optimal Lineup
                </button>
                <button
                  className="btn btn-primary btn-sm"
                  style={{ backgroundColor: '#10b981', borderColor: '#10b981', color: '#022c22', fontWeight: 700 }}
                  onClick={handleOpenPushModal}
                >
                  🚀 Push Custom Lineup to ESPN
                </button>
              </div>
            </div>
          )}

          {/* 8-Man Matchup Game Theory Spread Banner */}
          {lineup && lineup.game_theory_posture && (
            <div
              style={{
                background: lineup.game_theory_posture.includes('UNDERDOG')
                  ? 'rgba(239, 68, 68, 0.10)'
                  : lineup.game_theory_posture.includes('FAVORITE')
                  ? 'rgba(16, 185, 129, 0.10)'
                  : 'rgba(59, 130, 246, 0.10)',
                border: `1px solid ${
                  lineup.game_theory_posture.includes('UNDERDOG')
                    ? 'rgba(239, 68, 68, 0.35)'
                    : lineup.game_theory_posture.includes('FAVORITE')
                    ? 'rgba(16, 185, 129, 0.35)'
                    : 'rgba(59, 130, 246, 0.35)'
                }`,
                borderRadius: '12px',
                padding: '14px 18px',
                marginBottom: '16px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '12px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <span style={{ fontSize: '26px' }}>
                  {lineup.game_theory_posture.includes('UNDERDOG') ? '🚀' : lineup.game_theory_posture.includes('FAVORITE') ? '🛡️' : '🎯'}
                </span>
                <div>
                  <div style={{ fontWeight: 800, fontSize: '14px', color: 'var(--text-primary)' }}>
                    8-Man Game-Theory Posture: {lineup.game_theory_posture.replace(/_/g, ' ')}
                    {lineup.implied_matchup_spread !== null && lineup.implied_matchup_spread !== undefined && (
                      <span
                        className={`pill ${lineup.implied_matchup_spread < 0 ? 'rose' : 'emerald'}`}
                        style={{ marginLeft: '10px' }}
                      >
                        Spread: {lineup.implied_matchup_spread > 0 ? `+${lineup.implied_matchup_spread}` : lineup.implied_matchup_spread} pts
                        {lineup.opponent_projected_points ? ` vs Opponent (${lineup.opponent_projected_points} pts)` : ''}
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                    {lineup.game_theory_recommendation}
                  </div>
                </div>
              </div>
              {strategyMode !== 'AUTO' && (
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => handleStrategyChange('AUTO')}
                >
                  Switch to Auto-Spread →
                </button>
              )}
            </div>
          )}

          {/* Tactical FLEX Timing Guardrail Alert */}
          {lineup && lineup.flex_timing_risk && (
            <div
              style={{
                background: 'rgba(245, 158, 11, 0.12)',
                border: '1px solid rgba(245, 158, 11, 0.45)',
                borderRadius: '12px',
                padding: '12px 18px',
                marginBottom: '16px',
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
              }}
            >
              <span style={{ fontSize: '24px' }}>⏰</span>
              <div style={{ fontSize: '13px', color: '#fde68a' }}>
                <strong>Anti-Thursday FLEX Guardrail:</strong> {lineup.flex_timing_warning}
              </div>
            </div>
          )}

          {/* Executive Overview Banner */}
          {lineup && (
            <div className="executive-banner">
              <div className="banner-metric">
                <span className="metric-label">{hasCustomSwaps ? 'Custom Lineup Total' : 'Optimal Projected Total'}</span>
                <span className="metric-val">{hasCustomSwaps ? currentLineupProjectedTotal : lineup.total_projected_points} pts</span>
                <span className="metric-sub">
                  Engine: {projectionSource === 'MODEL' ? 'Quant Model' : projectionSource === 'CONSENSUS' ? '3-Way Consensus' : projectionSource === 'FANTASYPROS' ? 'FantasyPros PPR' : 'ESPN Official'}
                </span>
              </div>

              <div className="banner-metric">
                <span className="metric-label">Current ESPN Projected</span>
                <span className="metric-val">{lineup.current_espn_projected || lineup.total_projected_points} pts</span>
                <span className="metric-sub">ESPN Lineup Baseline</span>
              </div>

              <div className="banner-metric">
                <span className="metric-label">Immediate Lineup Advantage</span>
                <span className={`metric-val ${lineup.net_projected_gain > 0 ? 'emerald' : 'cyan'}`}>
                  {hasCustomSwaps
                    ? `${customGainVsOptimal >= 0 ? '+' : ''}${customGainVsOptimal} pts vs Optimal`
                    : (lineup.net_projected_gain > 0 ? `+${lineup.net_projected_gain} pts` : 'Optimal Baseline')}
                </span>
                <span className="metric-sub">
                  {hasCustomSwaps
                    ? `${Object.keys(customSubstitutions).length} custom bench substitute(s)`
                    : `${lineup.differences_count} starting changes recommended`}
                </span>
              </div>
            </div>
          )}

          {/* High-Variance Correlation Stacking Banner */}
          {lineup && lineup.active_stacks && lineup.active_stacks.length > 0 && (
            <div className="card" style={{ marginBottom: '16px', background: 'rgba(99, 102, 241, 0.08)', borderColor: 'rgba(99, 102, 241, 0.3)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ fontSize: '20px' }}>🔥</span>
                <div>
                  <strong style={{ color: '#818cf8' }}>H2H High-Variance Stacking Synergy Active:</strong>
                  <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                    {lineup.active_stacks.join(' • ')} (Maximizes 90th percentile boom ceiling to conquer 8-man juggernauts)
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Close Calls Alert Banner */}
          {lineup && lineup.close_calls.length > 0 && (
            <div className="close-call-banner">
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <span style={{ fontSize: '24px' }}>⚡</span>
                <div>
                  <strong>{lineup.close_calls.length} Close Call Decisions Flagged:</strong>
                  <div style={{ fontSize: '13px', opacity: 0.9 }}>
                    Decisions separated by ≤ 2.5 StartScore points. Review matchups before locking lineup.
                  </div>
                </div>
              </div>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => {
                  const first = lineup.close_calls[0]
                  setCompareIds([first.starter.player_id, first.bench_player.player_id])
                  runComparison([first.starter.player_id, first.bench_player.player_id])
                  setActiveTab('compare')
                }}
              >
                Review Toss-Up Head-to-Head →
              </button>
            </div>
          )}

          {/* Recommended Starters Table */}
          <div className="card" style={{ marginBottom: '24px' }}>
            <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
              <div>
                <h3 className="card-title">⭐ Optimal Starting Lineup (Week {league?.current_week || 1})</h3>
                <div style={{ display: 'flex', gap: '6px', marginTop: '4px', flexWrap: 'wrap' }}>
                  <span className="pill emerald">Maximum StartScore</span>
                  <span className="pill zinc" style={{ fontSize: '11px' }}>QB • RB • RB • WR • WR • TE • FLEX • KICKER • DST</span>
                </div>
              </div>
              <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
                <div style={{ display: 'inline-flex', background: 'rgba(255, 255, 255, 0.06)', borderRadius: '8px', padding: '2px', border: '1px solid rgba(255, 255, 255, 0.1)' }}>
                  <button
                    className={`btn btn-sm ${lineupViewMode === 'split' ? 'btn-primary' : 'btn-secondary'}`}
                    style={{ padding: '3px 8px', fontSize: '11.5px' }}
                    onClick={() => setLineupViewMode('split')}
                  >
                    🗂️ Split Cards
                  </button>
                  <button
                    className={`btn btn-sm ${lineupViewMode === 'unified' ? 'btn-primary' : 'btn-secondary'}`}
                    style={{ padding: '3px 8px', fontSize: '11.5px' }}
                    onClick={() => setLineupViewMode('unified')}
                  >
                    📋 Full Sheet (17 Slots)
                  </button>
                </div>
                <button
                  className="btn btn-primary"
                  style={{
                    backgroundColor: '#10b981',
                    borderColor: '#10b981',
                    color: '#022c22',
                    fontWeight: 800,
                    boxShadow: '0 4px 14px rgba(16, 185, 129, 0.4)',
                  }}
                  onClick={handleOpenPushModal}
                  disabled={isPushing}
                >
                  {isPushing ? '⏳ Checking Moves...' : '🚀 Push Optimal Lineup to ESPN'}
                </button>
              </div>
            </div>

            <MatchupRatingKey
              isOpen={showMatchupKey}
              onToggle={() => setShowMatchupKey(!showMatchupKey)}
            />

            <div className="table-responsive">
              <table className="custom-table">
                <thead>
                  <tr>
                    <th>Slot</th>
                    <th>Player</th>
                    <th>NFL Matchup</th>
                    <th>StartScore</th>
                    <th>Proj. PPR</th>
                    <th>Matchup</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {effectiveStarters.map((slot, slotIdx) => {
                    const p = slot.recommended_player
                    const isExpanded = expandedWhy === p.player_id
                    const isStatsExpanded = expandedStatsPlayerId === p.player_id
                    return (
                      <React.Fragment key={slot.slot_name + p.player_id}>
                        <tr className={slot.is_diff ? 'diff-row' : ''}>
                          <td>
                            <span className="slot-badge">{slot.slot_name}</span>
                            {slot.slot_name === 'FLEX' && slot.is_flex_timing_optimal !== undefined && (
                              <div style={{ marginTop: '4px' }}>
                                <span
                                  className={`pill ${slot.is_flex_timing_optimal ? 'emerald' : 'rose'}`}
                                  style={{ fontSize: '10px', padding: '2px 6px', display: 'inline-block' }}
                                  title={slot.flex_timing_note || (slot.is_flex_timing_optimal ? 'Optimal late kickoff slotting' : 'Early kickoff in FLEX warning')}
                                >
                                  {slot.is_flex_timing_optimal ? '⏰ Late Lock' : '⚠️ Early Flex'}
                                </span>
                              </div>
                            )}
                          </td>
                          <td>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                              <span style={{ fontWeight: 700 }}>{p.full_name}</span>
                              {slot.is_custom_swap && (
                                <span className="pill amber" style={{ fontSize: '10px', padding: '1px 6px', fontWeight: 700 }} title={`Custom Bench Swap replacing ${slot.original_recommended?.full_name}`}>
                                  🔄 Sub for {slot.original_recommended?.full_name}
                                </span>
                              )}
                            </div>
                            <div style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap', marginTop: '2px' }}>
                              <span>{p.position} • {p.pro_team}</span>
                              {(p.fp_rank_ecr || p.fp_pos_rank) ? (
                                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                                  <span
                                    style={{
                                      color: '#38bdf8',
                                      fontWeight: 700,
                                      background: 'rgba(56, 189, 248, 0.15)',
                                      padding: '1px 6px',
                                      borderRadius: '4px',
                                      border: '1px solid rgba(56, 189, 248, 0.3)',
                                    }}
                                    title={`FantasyPros PPR Consensus: ${p.fp_pos_rank || '#' + p.fp_rank_ecr} (Avg: #${p.fp_rank_ave?.toFixed(1) || p.fp_rank_ecr}${p.fp_tier ? ` • Tier ${p.fp_tier}` : ''})`}
                                  >
                                    ⭐ FP {p.fp_pos_rank || `#${p.fp_rank_ecr}`} (PPR)
                                  </span>
                                  {p.fp_start_sit_grade && (
                                    <span
                                      className={`grade-pill ${p.fp_start_sit_grade.startsWith('A') ? 'grade-a' : p.fp_start_sit_grade.startsWith('B') ? 'grade-b' : p.fp_start_sit_grade.startsWith('C') ? 'grade-c' : 'grade-d'}`}
                                      title={`FantasyPros Matchup / Start-Sit Grade: ${p.fp_start_sit_grade}`}
                                    >
                                      {p.fp_start_sit_grade}
                                    </span>
                                  )}
                                  {p.fp_tier && (
                                    <span
                                      style={{
                                      fontSize: '10.5px',
                                      color: '#cbd5e1',
                                      background: 'rgba(255, 255, 255, 0.06)',
                                      padding: '1px 4px',
                                      borderRadius: '3px',
                                      border: '1px solid rgba(255, 255, 255, 0.1)',
                                    }}
                                      title={`FantasyPros Consensus Tier ${p.fp_tier}`}
                                    >
                                      T{p.fp_tier}
                                    </span>
                                  )}
                                  {p.fp_rank_std !== undefined && p.fp_rank_std !== null && (
                                    <span
                                      style={{ color: p.fp_rank_std <= 0.8 ? '#10b981' : p.fp_rank_std >= 1.5 ? '#f59e0b' : '#94a3b8', fontSize: '11px' }}
                                      title={`Expert Std Dev: ±${p.fp_rank_std.toFixed(2)} (${p.fp_rank_std <= 0.8 ? 'Consensus Lock' : 'High Boom/Variance'})`}
                                    >
                                      (±{p.fp_rank_std.toFixed(1)})
                                    </span>
                                  )}
                                </span>
                              ) : p.consensus_rank ? (
                                <span style={{ color: '#facc15', fontWeight: 600 }}>
                                  #{p.consensus_rank.toFixed(1)} PPR
                                </span>
                              ) : null}
                              {p.live_vorp !== undefined && p.live_vorp !== null && (
                                <span
                                  className="vorp-badge"
                                  title="Live-Wire VORP: Projected value over top unowned replacement on waiver wire"
                                >
                                  VORP: {p.live_vorp > 0 ? `+${p.live_vorp}` : p.live_vorp}
                                </span>
                              )}
                              {slot.is_diff && (
                                <span className="diff-pill">DIFF vs ESPN</span>
                              )}
                            </div>

                          </td>
                          <td>
                            <span className="matchup-tag">
                              {p.is_home ? 'vs' : '@'} {p.opponent}
                            </span>
                            {p.game_date && (
                              <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                                {new Date(p.game_date).toLocaleDateString(undefined, { weekday: 'short', hour: 'numeric', minute: '2-digit' })}
                              </div>
                            )}
                            {p.opponent && p.opponent !== 'BYE' && (
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', marginTop: '4px' }}>
                                {p.opp_dvp_rank !== undefined && p.opp_dvp_rank !== null && (
                                  <div>
                                    <span
                                      className={`pill ${p.opp_dvp_rank <= 10 ? 'rose' : p.opp_dvp_rank >= 21 ? 'emerald' : 'amber'}`}
                                      style={{ fontSize: '10.5px', padding: '1px 6px', fontWeight: 700 }}
                                      title={`FantasyPros Consensus DvP: Ranked #${p.opp_dvp_rank} vs ${p.position} (${p.opp_dvp_rank <= 10 ? 'Tough Matchup' : p.opp_dvp_rank >= 21 ? 'Generous Matchup' : 'Neutral'})`}
                                    >
                                      🛡️ DvP #{p.opp_dvp_rank}
                                    </span>
                                  </div>
                                )}
                                <div style={{ display: 'flex', gap: '4px', alignItems: 'center', flexWrap: 'wrap' }}>
                                  {p.opp_def_rank !== undefined && p.opp_def_rank !== null && (
                                    <span
                                      className="pill zinc"
                                      style={{ fontSize: '10.5px', padding: '1px 6px', fontWeight: 600 }}
                                      title={`FantasyPros Consensus: Overall NFL Defense Rank #${p.opp_def_rank}`}
                                    >
                                      Def #{p.opp_def_rank}
                                    </span>
                                  )}
                                  {(p.opp_dvp_rank !== undefined && p.opp_dvp_rank !== null) && (
                                    <MatchupStarRating
                                      stars={p.matchup_stars}
                                      oppDvpRank={p.opp_dvp_rank}
                                      position={p.position}
                                    />
                                  )}
                                </div>
                              </div>
                            )}
                          </td>
                          <td>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                              <span className={`score-badge ${getScoreColorClass(p.start_score)}`}>
                                {p.start_score}
                              </span>
                              <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                                {p.ceiling_score !== undefined && p.ceiling_score > 0 && (
                                  <span className="ceiling-floor-tag ceiling" title="90th Percentile Ceiling">
                                    🚀 {p.ceiling_score}
                                  </span>
                                )}
                                {p.floor_score !== undefined && p.floor_score > 0 && (
                                  <span className="ceiling-floor-tag floor" title="20th Percentile Floor">
                                    🛡️ {p.floor_score}
                                  </span>
                                )}
                              </div>
                            </div>
                          </td>
                          <td style={{ fontWeight: 600 }}>{p.projected_points} pts</td>
                          <td>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', alignItems: 'flex-start' }}>
                              <span className={`pill ${p.matchup_grade === 'FAVORABLE' ? 'emerald' : p.matchup_grade === 'TOUGH' ? 'rose' : 'cyan'}`}>
                                {p.matchup_grade}
                              </span>
                              {p.opp_dvp_rank !== undefined && p.opp_dvp_rank !== null && (
                                <span 
                                  style={{ fontSize: '10px', color: 'var(--text-muted)' }} 
                                  title={p.position === 'D/ST' 
                                    ? `FantasyPros Consensus: DvP #${p.opp_dvp_rank} vs D/ST, Opp Offense #${p.opp_off_rank ?? 'N/A'}` 
                                    : `FantasyPros Consensus: DvP #${p.opp_dvp_rank} vs ${p.position}, Overall Def #${p.opp_def_rank ?? 'N/A'}`
                                  }
                                >
                                  {p.position === 'D/ST' 
                                    ? `DvP #${p.opp_dvp_rank} • Offense #${p.opp_off_rank ?? 'N/A'}` 
                                    : `DvP #${p.opp_dvp_rank} • Def #${p.opp_def_rank ?? 'N/A'}`
                                  }
                                </span>
                              )}
                              {p.matchup_resilience === 'MATCHUP_RESILIENT_STUD' && (
                                <span className="pill purple" style={{ fontSize: '9px', padding: '1px 5px' }} title="Tier-1 Alpha: High volume makes player resilient to tough matchups">
                                  Stud Invariant
                                </span>
                              )}
                              {p.playoff_sos_grade && (
                                <span className={`pill ${p.playoff_sos_grade === 'ELITE' ? 'emerald' : p.playoff_sos_grade === 'FAVORABLE' ? 'cyan' : p.playoff_sos_grade === 'BRUTAL' ? 'rose' : 'zinc'}`} style={{ fontSize: '9px', padding: '1px 5px' }} title={`Fantasy Playoff SoS (Weeks 15-17): ${p.playoff_sos_score ?? 70} pts`}>
                                  Playoffs: {p.playoff_sos_grade}
                                </span>
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
                          <td>
                            <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap', position: 'relative' }}>
                              <button
                                className="btn-link"
                                onClick={() => setExpandedStatsPlayerId(isStatsExpanded ? null : p.player_id)}
                                style={{ color: isStatsExpanded ? 'var(--accent-cyan)' : 'var(--text-secondary)' }}
                              >
                                {isStatsExpanded ? 'Hide Stats' : '📊 Stats'}
                              </button>
                              <button
                                className="btn-link"
                                onClick={() => setExpandedWhy(isExpanded ? null : p.player_id)}
                              >
                                {isExpanded ? 'Hide Why' : 'Why?'}
                              </button>
                              <button
                                className="btn btn-secondary btn-sm"
                                style={{ padding: '2px 8px', fontSize: '11px' }}
                                onClick={() => handleCompareStarterWithBench(p)}
                              >
                                ⚖️ Compare
                              </button>
                              <button
                                className={`swap-btn ${slot.is_custom_swap ? 'active' : ''}`}
                                onClick={() => setActiveSwapSlotIndex(activeSwapSlotIndex === slotIdx ? null : slotIdx)}
                                title="Substitute this starter with an eligible bench player"
                              >
                                ⇄ {slot.is_custom_swap ? 'Substituted' : 'Swap'}
                              </button>
                              {slot.is_custom_swap && (
                                <button
                                  className="btn-link"
                                  style={{ fontSize: '11px', color: 'var(--accent-rose)' }}
                                  onClick={() => handleRevertSlot(slotIdx)}
                                  title="Revert back to optimal starter"
                                >
                                  ↺ Revert
                                </button>
                              )}

                              {/* Inline Slot Swap Popover */}
                              {activeSwapSlotIndex === slotIdx && (
                                <div className="swap-popover">
                                  <div className="swap-popover-header">
                                    <span className="swap-popover-title">⇄ Swap {slot.slot_name} Slot</span>
                                    <button className="swap-popover-close" onClick={() => setActiveSwapSlotIndex(null)}>✕</button>
                                  </div>
                                  <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                                    Current: <strong style={{ color: '#f8fafc' }}>{p.full_name}</strong> ({p.projected_points.toFixed(1)} pts)
                                  </div>
                                  <div className="swap-candidate-list">
                                    {getEligibleBenchForSlot(slot.slot_name, effectiveBench).length === 0 ? (
                                      <div style={{ fontSize: '11.5px', color: 'var(--text-muted)', padding: '12px 6px', textAlign: 'center' }}>
                                        No eligible bench players found for {slot.slot_name}.
                                      </div>
                                    ) : (
                                      getEligibleBenchForSlot(slot.slot_name, effectiveBench).map((cand) => {
                                        const delta = Math.round((cand.projected_points - p.projected_points) * 10) / 10
                                        return (
                                          <div
                                            key={cand.player_id}
                                            className="swap-candidate-card"
                                            onClick={() => handlePerformSwap(slotIdx, cand)}
                                          >
                                            <div>
                                              <div className="swap-cand-name">{cand.full_name}</div>
                                              <div className="swap-cand-sub">
                                                {cand.position} • {cand.pro_team} ({cand.is_home ? 'vs' : '@'} {cand.opponent})
                                              </div>
                                            </div>
                                            <div className="swap-cand-right">
                                              <div className="swap-cand-pts">{cand.projected_points.toFixed(1)} pts</div>
                                              <div className={`swap-cand-delta ${delta > 0 ? 'positive' : delta < 0 ? 'negative' : 'neutral'}`}>
                                                {delta > 0 ? `+${delta}` : delta} pts
                                              </div>
                                            </div>
                                          </div>
                                        )
                                      })
                                    )}
                                  </div>
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>

                        {/* Itemized Stat Drawer */}
                        {isStatsExpanded && (
                          <tr className="stat-drawer-row">
                            <td colSpan={8} style={{ padding: '0 0 16px 0', background: 'transparent' }}>
                              <InstitutionalStatCard player={p} activeSource={projectionSource} />
                            </td>
                          </tr>
                        )}

                        {/* Why Explanation Drawer */}
                        {isExpanded && (
                          <tr className="why-row">
                            <td colSpan={8}>
                              <div className="why-content">
                                <div className="why-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                                  <strong>Factor Analysis for {p.full_name} (Confidence: {p.confidence}):</strong>
                                  {p.opp_dvp_rank !== undefined && p.opp_dvp_rank !== null && (
                                    <span style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'inline-flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                                      <span>Opponent: <strong style={{ color: 'var(--text-primary)' }}>{p.opponent}</strong></span>
                                      <span>• DvP: <strong style={{ color: p.opp_dvp_rank <= 10 ? 'var(--accent-rose)' : p.opp_dvp_rank >= 21 ? 'var(--accent-emerald)' : 'var(--accent-cyan)' }}>#{p.opp_dvp_rank} vs {p.position}</strong></span>
                                      <span>• {p.position === 'D/ST' ? 'Offense:' : 'Def:'} <strong style={{ color: 'var(--text-primary)' }}>#{p.position === 'D/ST' ? (p.opp_off_rank ?? 'N/A') : (p.opp_def_rank ?? 'N/A')} Overall</strong></span>
                                      <MatchupStarRating stars={p.matchup_stars} oppDvpRank={p.opp_dvp_rank} position={p.position} />
                                    </span>
                                  )}
                                </div>
                                <div className="why-grid">
                                  <div>
                                    <div style={{ color: 'var(--accent-emerald)', fontWeight: 600, marginBottom: '6px' }}>
                                      Positive Factors:
                                    </div>
                                    <ul className="factor-list">
                                      {p.reasons_positive.map((r, i) => renderWhyFactorItem(r, true, i))}
                                    </ul>
                                  </div>
                                  <div>
                                    <div style={{ color: 'var(--accent-rose)', fontWeight: 600, marginBottom: '6px' }}>
                                      Risk & Negative Factors:
                                    </div>
                                    <ul className="factor-list">
                                      {p.reasons_negative.length > 0 ? (
                                        p.reasons_negative.map((r, i) => renderWhyFactorItem(r, false, i))
                                      ) : (
                                        <li style={{ color: 'var(--text-muted)' }}>None identified (optimal setup)</li>
                                      )}
                                    </ul>
                                  </div>
                                </div>
                                <div className="component-bars">
                                  <span>Proj: {p.components.projection_score}</span>
                                  <span>Vol: {p.components.opportunity_score}</span>
                                  <span>Def: {p.components.matchup_score}</span>
                                  <span>Env: {p.components.environment_score}</span>
                                  <span>Hlth: {p.components.health_score}</span>
                                  <span>Wth: {p.components.weather_score}</span>
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    )
                  })}

                  {lineupViewMode === 'unified' && (
                    <>
                      {/* Bench Section Header Divider */}
                      <tr style={{ background: 'rgba(56, 189, 248, 0.1)', borderTop: '2px solid rgba(56, 189, 248, 0.4)', borderBottom: '1px solid rgba(56, 189, 248, 0.2)' }}>
                        <td colSpan={8} style={{ padding: '10px 14px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <strong style={{ color: '#38bdf8', fontSize: '13px' }}>
                              🪑 BENCH ROSTER ({lineup?.bench.length || 0} / {lineup?.bench_slots_count || 7} SLOTS)
                            </strong>
                            <span className="pill cyan" style={{ fontSize: '10px' }}>7 Bench Spots</span>
                          </div>
                        </td>
                      </tr>

                      {/* Bench Players */}
                      {lineup?.bench.map((b) => (
                        <tr key={`unified-bench-${b.player_id}`}>
                          <td>
                            <span className="slot-badge" style={{ background: 'rgba(148, 163, 184, 0.15)', borderColor: 'rgba(148, 163, 184, 0.3)', color: '#cbd5e1' }}>
                              BENCH
                            </span>
                          </td>
                          <td>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                              <span style={{ fontWeight: 600 }}>{b.full_name}</span>
                            </div>
                            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                              <span>{b.position} • {b.pro_team}</span>
                              {b.fp_pos_rank && <span style={{ marginLeft: '6px', color: '#38bdf8', fontWeight: 600 }}>⭐ FP {b.fp_pos_rank}</span>}
                            </div>
                          </td>
                          <td>
                            <span className="matchup-tag">{b.is_home ? 'vs' : '@'} {b.opponent}</span>
                            {b.opp_dvp_rank && <div style={{ fontSize: '10.5px', color: 'var(--text-muted)', marginTop: '2px' }}>DvP #{b.opp_dvp_rank}</div>}
                          </td>
                          <td>
                            <span className={`score-badge ${getScoreColorClass(b.start_score)}`}>{b.start_score}</span>
                          </td>
                          <td style={{ fontWeight: 600 }}>{b.projected_points} pts</td>
                          <td>
                            <span className={`pill ${b.matchup_grade === 'FAVORABLE' ? 'emerald' : b.matchup_grade === 'TOUGH' ? 'rose' : 'cyan'}`}>{b.matchup_grade}</span>
                          </td>
                          <td>
                            <InjuryStatusPill
                              status={b.injury_status}
                              fullName={b.full_name}
                              position={b.position}
                              injuryNote={b.fp_injury_note}
                            />
                          </td>
                          <td>
                            <button
                              className="btn btn-secondary btn-sm"
                              style={{ padding: '2px 8px', fontSize: '11px' }}
                              onClick={() => handleCompareBenchWithStarter(b)}
                            >
                              ⚖️ Compare
                            </button>
                          </td>
                        </tr>
                      ))}

                      {/* Empty Bench Spots */}
                      {Array.from({ length: Math.max(0, (lineup?.bench_slots_count || 7) - (lineup?.bench.length || 0)) }).map((_, idx) => (
                        <tr key={`unified-empty-bench-${idx}`} style={{ opacity: 0.65 }}>
                          <td><span className="slot-badge" style={{ opacity: 0.6 }}>BENCH</span></td>
                          <td><span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>Empty Bench Spot</span></td>
                          <td style={{ color: 'var(--text-muted)' }}>—</td>
                          <td style={{ color: 'var(--text-muted)' }}>—</td>
                          <td style={{ color: 'var(--text-muted)' }}>0.0 pts</td>
                          <td><span className="pill zinc" style={{ fontSize: '10.5px' }}>FREE SPOT</span></td>
                          <td><span className="status-pill" style={{ opacity: 0.5 }}>OPEN</span></td>
                          <td style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Open Spot</td>
                        </tr>
                      ))}

                      {/* IR Section Header Divider */}
                      <tr style={{ background: 'rgba(16, 185, 129, 0.1)', borderTop: '2px solid rgba(16, 185, 129, 0.4)', borderBottom: '1px solid rgba(16, 185, 129, 0.2)' }}>
                        <td colSpan={8} style={{ padding: '10px 14px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <strong style={{ color: '#34d399', fontSize: '13px' }}>
                              🏥 INJURY RESERVE (1 FREE SPOT)
                            </strong>
                            <span className="pill emerald" style={{ fontSize: '10px', fontWeight: 800 }}>✨ 1 FREE SPOT AVAILABLE</span>
                          </div>
                        </td>
                      </tr>

                      {/* IR Rostered Players (if any) */}
                      {lineup?.ir && lineup.ir.length > 0 ? (
                        lineup.ir.map((p) => (
                          <tr key={`unified-ir-${p.player_id}`}>
                            <td><span className="slot-badge rose">IR</span></td>
                            <td><strong style={{ color: '#f87171' }}>{p.full_name}</strong></td>
                            <td>{p.position} • {p.pro_team}</td>
                            <td>{p.opponent}</td>
                            <td><span className={`score-badge ${getScoreColorClass(p.start_score)}`}>{p.start_score}</span></td>
                            <td style={{ fontWeight: 600 }}>{p.projected_points} pts</td>
                            <td>
                              <InjuryStatusPill
                                status={p.injury_status}
                                fullName={p.full_name}
                                position={p.position}
                                injuryNote={p.fp_injury_note}
                              />
                            </td>
                            <td style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>On Injury Reserve</td>
                          </tr>
                        ))
                      ) : (
                        <tr style={{ background: 'rgba(16, 185, 129, 0.03)' }}>
                          <td><span className="slot-badge emerald" style={{ borderColor: 'rgba(16, 185, 129, 0.4)', color: '#34d399', fontWeight: 800 }}>IR</span></td>
                          <td>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <span style={{ fontWeight: 700, color: '#34d399' }}>Empty IR Slot</span>
                              <span className="pill emerald" style={{ fontSize: '10px', padding: '1px 6px', fontWeight: 800 }}>1 FREE SPOT</span>
                            </div>
                          </td>
                          <td style={{ color: 'var(--text-muted)' }}>Any Eligible</td>
                          <td style={{ color: 'var(--text-muted)' }}>—</td>
                          <td>—</td>
                          <td style={{ color: 'var(--text-muted)' }}>0.0 pts</td>
                          <td><span className="pill emerald" style={{ fontSize: '11px', padding: '2px 8px' }}>Open Stash</span></td>
                          <td style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Free Stash Spot (OUT/IR)</td>
                        </tr>
                      )}
                    </>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {lineupViewMode === 'split' && (
            <>
              {/* Bench Table */}
          <div className="card">
            <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <h3 className="card-title">🪑 Bench Roster</h3>
                <span className="pill cyan">{lineup?.bench.length || 0} / {lineup?.bench_slots_count || 7} Players</span>
              </div>
              <span className="pill zinc" style={{ fontSize: '11px' }}>
                {lineup?.bench_slots_count || 7} Bench Spots
              </span>
            </div>

            <div className="table-responsive">
              <table className="custom-table">
                <thead>
                  <tr>
                    <th>Slot</th>
                    <th>Player</th>
                    <th>Position</th>
                    <th>Opponent</th>
                    <th>StartScore</th>
                    <th>Proj. PPR</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {effectiveBench.map((b) => {
                    const isStatsExpanded = expandedStatsPlayerId === b.player_id
                    return (
                      <React.Fragment key={b.player_id}>
                        <tr>
                          <td>
                            <span className="slot-badge" style={{ background: 'rgba(148, 163, 184, 0.15)', borderColor: 'rgba(148, 163, 184, 0.3)', color: '#cbd5e1' }}>
                              BENCH
                            </span>
                          </td>
                          <td>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                              <span style={{ fontWeight: 600 }}>{b.full_name}</span>
                            </div>
                            <div style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap', marginTop: '2px' }}>
                              {(b.fp_rank_ecr || b.fp_pos_rank) ? (
                                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                                  <span
                                    style={{
                                      color: '#38bdf8',
                                      fontWeight: 700,
                                      background: 'rgba(56, 189, 248, 0.15)',
                                      padding: '1px 5px',
                                      borderRadius: '4px',
                                      border: '1px solid rgba(56, 189, 248, 0.3)',
                                    }}
                                    title={`FantasyPros PPR Consensus: ${b.fp_pos_rank || '#' + b.fp_rank_ecr} (Avg: #${b.fp_rank_ave?.toFixed(1) || b.fp_rank_ecr}${b.fp_tier ? ` • Tier ${b.fp_tier}` : ''})`}
                                  >
                                    ⭐ FP {b.fp_pos_rank || `#${b.fp_rank_ecr}`} (PPR)
                                  </span>
                                  {b.fp_start_sit_grade && (
                                    <span
                                      className={`grade-pill ${b.fp_start_sit_grade.startsWith('A') ? 'grade-a' : b.fp_start_sit_grade.startsWith('B') ? 'grade-b' : b.fp_start_sit_grade.startsWith('C') ? 'grade-c' : 'grade-d'}`}
                                      title={`FantasyPros Matchup / Start-Sit Grade: ${b.fp_start_sit_grade}`}
                                    >
                                      {b.fp_start_sit_grade}
                                    </span>
                                  )}
                                  {b.fp_tier && (
                                    <span
                                      style={{
                                        fontSize: '10px',
                                        color: '#cbd5e1',
                                        background: 'rgba(255, 255, 255, 0.06)',
                                        padding: '1px 4px',
                                        borderRadius: '3px',
                                        border: '1px solid rgba(255, 255, 255, 0.1)',
                                      }}
                                      title={`FantasyPros Consensus Tier ${b.fp_tier}`}
                                    >
                                      T{b.fp_tier}
                                    </span>
                                  )}
                                  {b.fp_rank_std !== undefined && b.fp_rank_std !== null && (
                                    <span
                                      style={{ color: b.fp_rank_std <= 0.8 ? '#10b981' : b.fp_rank_std >= 1.5 ? '#f59e0b' : '#94a3b8' }}
                                      title={`Expert Std Dev: ±${b.fp_rank_std.toFixed(2)}`}
                                    >
                                      ±{b.fp_rank_std.toFixed(1)}
                                    </span>
                                  )}
                                </span>
                              ) : b.consensus_rank ? (
                                <span>Consensus: #{b.consensus_rank.toFixed(1)} PPR</span>
                              ) : null}
                            </div>

                          </td>
                          <td>{b.position} • {b.pro_team}</td>
                          <td>
                            <span className="matchup-tag">
                              {b.is_home ? 'vs' : '@'} {b.opponent}
                            </span>
                            {b.opponent && b.opponent !== 'BYE' && (
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', marginTop: '4px' }}>
                                {b.opp_dvp_rank !== undefined && b.opp_dvp_rank !== null && (
                                  <div>
                                    <span
                                      className={`pill ${b.opp_dvp_rank <= 10 ? 'rose' : b.opp_dvp_rank >= 21 ? 'emerald' : 'amber'}`}
                                      style={{ fontSize: '10px', padding: '1px 5px', fontWeight: 700 }}
                                      title={`FantasyPros Consensus DvP: #${b.opp_dvp_rank} vs ${b.position}`}
                                    >
                                      🛡️ DvP #{b.opp_dvp_rank}
                                    </span>
                                  </div>
                                )}
                                <div style={{ display: 'flex', gap: '4px', alignItems: 'center', flexWrap: 'wrap' }}>
                                  {b.position === 'D/ST' ? (
                                    b.opp_off_rank !== undefined && b.opp_off_rank !== null && (
                                      <span
                                        className="pill zinc"
                                        style={{ fontSize: '10px', padding: '1px 5px', fontWeight: 600 }}
                                        title={`FantasyPros Consensus: Opposing NFL Offense Rank #${b.opp_off_rank}`}
                                      >
                                        Offense #{b.opp_off_rank}
                                      </span>
                                    )
                                  ) : (
                                    b.opp_def_rank !== undefined && b.opp_def_rank !== null && (
                                      <span
                                        className="pill zinc"
                                        style={{ fontSize: '10px', padding: '1px 5px', fontWeight: 600 }}
                                        title={`FantasyPros Consensus: Overall NFL Defense Rank #${b.opp_def_rank}`}
                                      >
                                        Def #{b.opp_def_rank}
                                      </span>
                                    )
                                  )}
                                  {(b.opp_dvp_rank !== undefined && b.opp_dvp_rank !== null) && (
                                    <MatchupStarRating
                                      stars={b.matchup_stars}
                                      oppDvpRank={b.opp_dvp_rank}
                                      position={b.position}
                                    />
                                  )}
                                </div>
                              </div>
                            )}
                          </td>
                          <td>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                              <span className={`score-badge ${getScoreColorClass(b.start_score)}`}>
                                {b.start_score}
                              </span>
                              <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                                {b.ceiling_score !== undefined && b.ceiling_score > 0 && (
                                  <span className="ceiling-floor-tag ceiling" title="90th Percentile Ceiling">
                                    🚀 {b.ceiling_score}
                                  </span>
                                )}
                                {b.floor_score !== undefined && b.floor_score > 0 && (
                                  <span className="ceiling-floor-tag floor" title="20th Percentile Floor">
                                    🛡️ {b.floor_score}
                                  </span>
                                )}
                                {b.contingency_score !== undefined && b.contingency_score > 0 && (
                                  <span className="ceiling-floor-tag contingent" title="Contingent Workhorse Upside">
                                    ⚡ {b.contingency_score}
                                  </span>
                                )}
                              </div>
                            </div>
                          </td>
                          <td>{b.projected_points} pts</td>
                          <td>
                            <InjuryStatusPill
                              status={b.injury_status}
                              fullName={b.full_name}
                              position={b.position}
                              injuryNote={b.fp_injury_note}
                            />
                          </td>
                          <td>
                            <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                              <button
                                className="btn-link"
                                onClick={() => setExpandedStatsPlayerId(isStatsExpanded ? null : b.player_id)}
                                style={{ color: isStatsExpanded ? 'var(--accent-cyan)' : 'var(--text-secondary)' }}
                              >
                                {isStatsExpanded ? 'Hide' : '📊 Stats'}
                              </button>
                              <button
                                className="btn-link"
                                onClick={() => setExpandedWhy(expandedWhy === b.player_id ? null : b.player_id)}
                                style={{ color: expandedWhy === b.player_id ? 'var(--accent-cyan)' : 'var(--text-secondary)' }}
                              >
                                {expandedWhy === b.player_id ? 'Hide Why' : 'Why?'}
                              </button>
                              <button
                                className="btn btn-secondary btn-sm"
                                onClick={() => handleCompareBenchWithStarter(b)}
                              >
                                ⚖️ Compare
                              </button>
                            </div>
                          </td>
                        </tr>

                        {isStatsExpanded && (
                          <tr className="stat-drawer-row">
                            <td colSpan={8} style={{ padding: '0 0 16px 0', background: 'transparent' }}>
                              <InstitutionalStatCard player={b} activeSource={projectionSource} />
                            </td>
                          </tr>
                        )}

                        {/* Bench Why Explanation Drawer */}
                        {expandedWhy === b.player_id && (
                          <tr className="why-row">
                            <td colSpan={8}>
                              <div className="why-content">
                                <div className="why-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                                  <strong>Factor Analysis for {b.full_name} (Confidence: {b.confidence}):</strong>
                                  {b.opp_dvp_rank !== undefined && b.opp_dvp_rank !== null && (
                                    <span style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'inline-flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                                      <span>Opponent: <strong style={{ color: 'var(--text-primary)' }}>{b.opponent}</strong></span>
                                      <span>• DvP: <strong style={{ color: b.opp_dvp_rank <= 10 ? 'var(--accent-rose)' : b.opp_dvp_rank >= 21 ? 'var(--accent-emerald)' : 'var(--accent-cyan)' }}>#{b.opp_dvp_rank} vs {b.position}</strong></span>
                                      <span>• Def: <strong style={{ color: 'var(--text-primary)' }}>#{b.opp_def_rank} Overall</strong></span>
                                      <MatchupStarRating stars={b.matchup_stars} oppDvpRank={b.opp_dvp_rank} position={b.position} />
                                    </span>
                                  )}
                                </div>
                                <div className="why-grid">
                                  <div>
                                    <div style={{ color: 'var(--accent-emerald)', fontWeight: 600, marginBottom: '6px' }}>
                                      Positive Factors:
                                    </div>
                                    <ul className="factor-list">
                                      {b.reasons_positive.map((r, i) => renderWhyFactorItem(r, true, i))}
                                    </ul>
                                  </div>
                                  <div>
                                    <div style={{ color: 'var(--accent-rose)', fontWeight: 600, marginBottom: '6px' }}>
                                      Risk & Negative Factors:
                                    </div>
                                    <ul className="factor-list">
                                      {b.reasons_negative.length > 0 ? (
                                        b.reasons_negative.map((r, i) => renderWhyFactorItem(r, false, i))
                                      ) : (
                                        <li style={{ color: 'var(--text-muted)' }}>None identified (optimal setup)</li>
                                      )}
                                    </ul>
                                  </div>
                                </div>
                                <div className="component-bars">
                                  <span>Proj: {b.components.projection_score}</span>
                                  <span>Vol: {b.components.opportunity_score}</span>
                                  <span>Def: {b.components.matchup_score}</span>
                                  <span>Env: {b.components.environment_score}</span>
                                  <span>Hlth: {b.components.health_score}</span>
                                  <span>Wth: {b.components.weather_score}</span>
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    )
                  })}

                  {Array.from({ length: Math.max(0, (lineup?.bench_slots_count || 7) - (lineup?.bench.length || 0)) }).map((_, idx) => (
                    <tr key={`empty-bench-${idx}`} style={{ opacity: 0.65 }}>
                      <td>
                        <span className="slot-badge" style={{ opacity: 0.6 }}>BENCH</span>
                      </td>
                      <td>
                        <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>Empty Bench Spot</span>
                      </td>
                      <td style={{ color: 'var(--text-muted)' }}>—</td>
                      <td style={{ color: 'var(--text-muted)' }}>—</td>
                      <td style={{ color: 'var(--text-muted)' }}>—</td>
                      <td style={{ color: 'var(--text-muted)' }}>0.0 pts</td>
                      <td>
                        <span className="pill zinc" style={{ fontSize: '10.5px' }}>FREE SPOT</span>
                      </td>
                      <td>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Available bench spot</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Injury Reserve (IR) Card */}
          <div className="card" style={{ marginTop: '24px' }}>
            <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <h3 className="card-title">🏥 Injury Reserve (IR)</h3>
                <span className="pill zinc">
                  {(lineup?.ir?.length || 0)} / {(lineup?.ir_slots_count || 1)} Roster Slot
                </span>
              </div>
              {(lineup?.ir?.length || 0) < (lineup?.ir_slots_count || 1) && (
                <span className="pill emerald" style={{ fontWeight: 800, padding: '3px 8px' }}>
                  ✨ 1 FREE SPOT AVAILABLE
                </span>
              )}
            </div>

            <div className="table-responsive">
              <table className="custom-table">
                <thead>
                  <tr>
                    <th>Slot</th>
                    <th>Player</th>
                    <th>Position</th>
                    <th>Opponent</th>
                    <th>StartScore</th>
                    <th>Proj. PPR</th>
                    <th>Status</th>
                    <th>Tactical Stash Note</th>
                  </tr>
                </thead>
                <tbody>
                  {lineup?.ir && lineup.ir.length > 0 ? (
                    lineup.ir.map((p) => (
                      <tr key={p.player_id}>
                        <td>
                          <span className="slot-badge rose">IR</span>
                        </td>
                        <td>
                          <strong style={{ color: '#f87171' }}>{p.full_name}</strong>
                        </td>
                        <td>{p.position} • {p.pro_team}</td>
                        <td>{p.opponent}</td>
                        <td>
                          <span className={`score-badge ${getScoreColorClass(p.start_score)}`}>
                            {p.start_score}
                          </span>
                        </td>
                        <td>{p.projected_points} pts</td>
                        <td>
                          <InjuryStatusPill
                            status={p.injury_status}
                            fullName={p.full_name}
                            position={p.position}
                            injuryNote={p.fp_injury_note}
                          />
                        </td>
                        <td style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                          Occupying designated ESPN IR roster spot
                        </td>
                      </tr>
                    ))
                  ) : null}

                  {Array.from({ length: Math.max(1, (lineup?.ir_slots_count || 1) - (lineup?.ir?.length || 0)) }).map((_, idx) => (
                    <tr key={`empty-ir-${idx}`} style={{ background: 'rgba(16, 185, 129, 0.03)' }}>
                      <td>
                        <span className="slot-badge emerald" style={{ borderColor: 'rgba(16, 185, 129, 0.4)', color: '#34d399', fontWeight: 800 }}>
                          IR
                        </span>
                      </td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span style={{ fontWeight: 700, color: '#34d399' }}>
                            Empty IR Slot
                          </span>
                          <span className="pill emerald" style={{ fontSize: '10px', padding: '1px 6px', fontWeight: 800 }}>
                            1 FREE SPOT
                          </span>
                        </div>
                      </td>
                      <td style={{ color: 'var(--text-muted)' }}>Any Eligible</td>
                      <td style={{ color: 'var(--text-muted)' }}>—</td>
                      <td style={{ color: 'var(--text-muted)' }}>—</td>
                      <td style={{ color: 'var(--text-muted)' }}>0.0 pts</td>
                      <td>
                        <span className="pill emerald" style={{ fontSize: '11px', padding: '2px 8px' }}>
                          Open Stash Spot
                        </span>
                      </td>
                      <td style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                        Free roster slot: Eligible to stash injured players (OUT/IR) without counting against your 7-man bench limit.
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
        </div>
      )}

      {/* TAB 2: START/SIT COMPARATOR */}
      {activeTab === 'compare' && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">⚖️ Head-to-Head Start/Sit Comparator (2-4 Players)</h3>
            <span className="pill cyan">Transparent Formula</span>
          </div>

          {/* Strategy Mode Switcher Bar in Comparator */}
          <div className="strategy-selector-bar" style={{ marginBottom: '16px' }}>
            <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)' }}>
              Evaluate Under Strategy:
            </span>
            <div className="strategy-selector">
              <button
                className={`strategy-pill-btn balanced ${strategyMode === 'BALANCED' ? 'active' : ''}`}
                onClick={() => handleStrategyChange('BALANCED')}
              >
                🎯 Balanced
              </button>
              <button
                className={`strategy-pill-btn ceiling ${strategyMode === 'CEILING' ? 'active' : ''}`}
                onClick={() => handleStrategyChange('CEILING')}
              >
                🚀 Ceiling (Boom)
              </button>
              <button
                className={`strategy-pill-btn floor ${strategyMode === 'FLOOR' ? 'active' : ''}`}
                onClick={() => handleStrategyChange('FLOOR')}
              >
                🛡️ Floor (Safe)
              </button>
            </div>
          </div>

          <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '20px' }}>
            Select players from your roster or available pool to inspect factor-by-factor score differences.
          </p>

          {/* Scope Mode Toggle Bar */}
          <div className="comparator-scope-bar">
            <div className="scope-toggle-group">
              <button
                className={`scope-toggle-btn ${compareScope === 'roster' ? 'active' : ''}`}
                onClick={() => handleScopeChange('roster')}
              >
                🏠 Team Roster (Compact Mode)
              </button>
              <button
                className={`scope-toggle-btn ${compareScope === 'all' ? 'active' : ''}`}
                onClick={() => handleScopeChange('all')}
              >
                🌐 League & Free Agents (Full Pool)
              </button>
            </div>

            <div className="scope-team-indicator">
              <span style={{ color: 'var(--text-muted)' }}>Focus Team:</span>
              <strong style={{ color: 'var(--text-primary)' }}>{focusedTeamName}</strong>
              <span className="pill cyan" style={{ padding: '2px 8px', fontSize: '11px' }}>
                {compareScope === 'roster' ? `${currentTeamPlayers.length} Roster Players` : `${allPlayers.length} Total Pool`}
              </span>
            </div>
          </div>

          {/* 1-Click Lineup Dilemmas Tray */}
          {rosterDilemmas.length > 0 && (
            <div className="dilemma-tray">
              <span className="dilemma-tray-label">⚡ 1-Click Roster Dilemmas:</span>
              {rosterDilemmas.map((d) => (
                <button
                  key={d.id}
                  className={`dilemma-chip ${d.isCloseCall ? 'close-call' : ''}`}
                  onClick={() => handleSelectDilemma(d.starterId, d.benchId)}
                  title={`Compare ${d.starterName} vs ${d.benchName} (Δ ${d.delta} pts)`}
                >
                  <span className="dilemma-chip-tag">{d.slotName}</span>
                  <span>{d.starterName} vs {d.benchName}</span>
                  <span style={{ fontSize: '11px', color: d.isCloseCall ? 'var(--accent-amber)' : 'var(--accent-cyan)', fontWeight: 700 }}>
                    {d.isCloseCall ? `⚡ Δ${d.delta}` : `Δ${d.delta}`}
                  </span>
                </button>
              ))}
            </div>
          )}

          {/* Position Filter Tabs */}
          <div style={{ marginBottom: '18px', display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Filter By Position:
            </span>
            {['ALL', 'QB', 'RB', 'WR', 'TE', 'FLEX', 'K', 'D/ST'].map((pos) => (
              <button
                key={pos}
                className={`btn btn-sm ${comparePosFilter === pos ? 'btn-primary' : 'btn-secondary'}`}
                style={{ padding: '4px 12px', fontSize: '12px' }}
                onClick={() => setComparePosFilter(pos)}
              >
                {pos}
              </button>
            ))}
          </div>

          {/* Interactive Player Dropdown Pickers */}
          <div style={{
            background: 'rgba(15, 23, 42, 0.65)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            padding: '18px',
            marginBottom: '24px',
          }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '16px', alignItems: 'flex-end' }}>
              {compareIds.map((pid, idx) => (
                <div key={idx} style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <label style={{ fontSize: '12px', fontWeight: 700, color: idx === 0 ? 'var(--accent-cyan)' : idx === 1 ? 'var(--accent-purple)' : 'var(--text-secondary)' }}>
                      {idx === 0 ? '👤 Candidate #1 (Primary)' : idx === 1 ? '⚔️ Candidate #2 (Challenger)' : `Candidate #${idx + 1}`}
                    </label>
                    {idx >= 2 && (
                      <button
                        className="btn btn-secondary btn-sm"
                        style={{ padding: '2px 8px', fontSize: '11px', color: 'var(--accent-rose)' }}
                        onClick={() => handleRemoveComparePlayer(idx)}
                      >
                        ✕ Remove
                      </button>
                    )}
                  </div>
                  <select
                    className="select-dropdown"
                    style={{ width: '100%', padding: '10px 14px', fontSize: '13px' }}
                    value={pid}
                    onChange={(e) => handlePlayerSelect(idx, Number(e.target.value))}
                  >
                    <option value="" disabled>Select Player...</option>
                    {myStarters.length > 0 && (
                      <optgroup label={`⭐ ${focusedTeamName} Starters (${myStarters.length})`}>
                        {myStarters.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.full_name} ({p.position} - {p.pro_team}) • {p.slot_name ? `${p.slot_name} • ` : ''}{p.projected_points} pts [Starter]
                          </option>
                        ))}
                      </optgroup>
                    )}
                    {myBench.length > 0 && (
                      <optgroup label={`🔄 ${focusedTeamName} Bench (${myBench.length})`}>
                        {myBench.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.full_name} ({p.position} - {p.pro_team}) • {p.projected_points} pts [Bench]
                          </option>
                        ))}
                      </optgroup>
                    )}
                    {compareScope === 'all' && freeAgents.length > 0 && (
                      <optgroup label={`🟢 Top Available Free Agents (${freeAgents.length})`}>
                        {freeAgents.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.full_name} ({p.position} - {p.pro_team}) • {p.projected_points} pts [Free Agent]
                          </option>
                        ))}
                      </optgroup>
                    )}
                    {compareScope === 'all' && otherTeams.length > 0 && (
                      <optgroup label={`👥 Other League Rosters (${otherTeams.length})`}>
                        {otherTeams.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.full_name} ({p.position} - {p.pro_team}) • {p.projected_points} pts ({p.team_abbrev || 'League'})
                          </option>
                        ))}
                      </optgroup>
                    )}
                  </select>
                </div>
              ))}
            </div>

            {/* Action Bar: Swap and Add 3rd/4th Candidate */}
            <div style={{ display: 'flex', gap: '10px', marginTop: '14px', flexWrap: 'wrap', alignItems: 'center' }}>
              <button
                className="btn btn-secondary btn-sm"
                onClick={handleSwapPlayers}
                disabled={compareIds.length < 2}
              >
                ⇄ Swap Candidates #1 & #2
              </button>

              {compareIds.length < 4 && (
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={handleAddComparePlayer}
                  style={{ borderColor: 'var(--accent-purple)' }}
                >
                  + Add Player to Compare ({compareIds.length + 1} of 4)
                </button>
              )}
            </div>
          </div>

          {/* Comparison Outcome Banner */}
          {comparisonResult && (
            <div className={`comp-banner ${comparisonResult.is_close_call ? 'toss-up' : 'clear-win'}`}>
              <div className="comp-title">{comparisonResult.headline}</div>
              <div className="comp-desc">{comparisonResult.detailed_rationale}</div>
            </div>
          )}

          {/* Side-by-Side Comparison Cards */}
          {comparisonResult && (
            <div className="comparator-grid">
              {comparisonResult.players.map((p, idx) => (
                <div key={p.player_id} className={`comp-card ${idx === 0 ? 'winner' : ''}`}>
                  {idx === 0 && <div className="winner-tag">RECOMMENDED START ✓</div>}
                  <div className="comp-player-name">{p.full_name}</div>
                  <div className="comp-player-meta" style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap', marginTop: '3px' }}>
                    <span>{p.position} • {p.pro_team} • {p.is_home ? 'vs' : '@'} {p.opponent}</span>
                    {p.opp_dvp_rank !== undefined && p.opp_dvp_rank !== null && (
                      <span
                        className={`pill ${p.opp_dvp_rank <= 10 ? 'rose' : p.opp_dvp_rank >= 21 ? 'emerald' : 'cyan'}`}
                        style={{ fontSize: '10px', padding: '1px 5px', fontWeight: 700 }}
                        title={`FantasyPros Consensus DvP: #${p.opp_dvp_rank} vs ${p.position}`}
                      >
                        DvP #{p.opp_dvp_rank}
                      </span>
                    )}
                    {p.opp_def_rank !== undefined && p.opp_def_rank !== null && (
                      <span
                        className="pill zinc"
                        style={{ fontSize: '10px', padding: '1px 5px', fontWeight: 600 }}
                        title={`FantasyPros Overall Defense Rank: #${p.opp_def_rank}`}
                      >
                        Def #{p.opp_def_rank}
                      </span>
                    )}
                    {p.opp_dvp_rank !== undefined && p.opp_dvp_rank !== null && (
                      <MatchupStarRating
                        stars={p.matchup_stars}
                        oppDvpRank={p.opp_dvp_rank}
                        position={p.position}
                      />
                    )}
                  </div>

                  <div className="comp-score-row">
                    <div>
                      <div className="metric-label">StartScore</div>
                      <div className={`metric-val ${getScoreColorClass(p.start_score)}`}>
                        {p.start_score}
                      </div>
                    </div>
                    <div>
                      <div className="metric-label">Projected</div>
                      <div className="metric-val">{p.projected_points} pts</div>
                    </div>
                    <div>
                      <div className="metric-label">Confidence</div>
                      <span className={`pill ${p.confidence === 'HIGH' ? 'emerald' : p.confidence === 'LOW' ? 'rose' : 'cyan'}`}>
                        {p.confidence}
                      </span>
                    </div>
                  </div>

                  {/* Factor Breakdown Bars with Interactive Transparency */}
                  <div className="factor-breakdown">
                    {/* 1. Projection Score */}
                    <div
                      className="factor-item-interactive"
                      onClick={() => toggleFactorFormula(p.player_id, 'projection')}
                      title="Click to inspect raw inputs & transparent formula"
                    >
                      <div className="factor-bar-label">
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span>Projection Score</span>
                          {p.comparator_factors?.projection && (
                            <span className={`factor-bar-badge ${p.comparator_factors.projection.bucket_color}`}>
                              {p.comparator_factors.projection.bucket}
                            </span>
                          )}
                        </div>
                        <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{p.components.projection_score}</span>
                      </div>
                      <div className="bar-bg">
                        <div
                          className="bar-fill"
                          style={{
                            width: `${p.components.projection_score}%`,
                            background: p.comparator_factors?.projection.bucket_color === 'emerald'
                              ? 'linear-gradient(to right, #10b981, #34d399)'
                              : p.comparator_factors?.projection.bucket_color === 'amber'
                              ? 'linear-gradient(to right, #f59e0b, #fbbf24)'
                              : p.comparator_factors?.projection.bucket_color === 'rose'
                              ? 'linear-gradient(to right, #f43f5e, #fb7185)'
                              : 'linear-gradient(to right, #06b6d4, #38bdf8)',
                          }}
                        />
                      </div>
                    </div>

                    {/* 2. Opportunity Volume */}
                    <div
                      className="factor-item-interactive"
                      onClick={() => toggleFactorFormula(p.player_id, 'opportunity')}
                      title="Click to inspect raw inputs & transparent formula"
                    >
                      <div className="factor-bar-label">
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span>Opportunity Volume</span>
                          {p.comparator_factors?.opportunity && (
                            <span className={`factor-bar-badge ${p.comparator_factors.opportunity.bucket_color}`}>
                              {p.comparator_factors.opportunity.bucket}
                            </span>
                          )}
                        </div>
                        <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{p.components.opportunity_score}</span>
                      </div>
                      <div className="bar-bg">
                        <div
                          className="bar-fill"
                          style={{
                            width: `${p.components.opportunity_score}%`,
                            background: p.comparator_factors?.opportunity.bucket_color === 'emerald'
                              ? 'linear-gradient(to right, #10b981, #34d399)'
                              : p.comparator_factors?.opportunity.bucket_color === 'amber'
                              ? 'linear-gradient(to right, #f59e0b, #fbbf24)'
                              : p.comparator_factors?.opportunity.bucket_color === 'rose'
                              ? 'linear-gradient(to right, #f43f5e, #fb7185)'
                              : 'linear-gradient(to right, #06b6d4, #38bdf8)',
                          }}
                        />
                      </div>
                    </div>

                    {/* 3. Defensive Matchup */}
                    <div
                      className="factor-item-interactive"
                      onClick={() => toggleFactorFormula(p.player_id, 'matchup')}
                      title="Click to inspect raw inputs & transparent formula"
                    >
                      <div className="factor-bar-label">
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span>Defensive Matchup</span>
                          {p.comparator_factors?.matchup && (
                            <span className={`factor-bar-badge ${p.comparator_factors.matchup.bucket_color}`}>
                              {p.comparator_factors.matchup.bucket}
                            </span>
                          )}
                        </div>
                        <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{p.components.matchup_score}</span>
                      </div>
                      <div className="bar-bg">
                        <div
                          className="bar-fill"
                          style={{
                            width: `${p.components.matchup_score}%`,
                            background: p.comparator_factors?.matchup.bucket_color === 'emerald'
                              ? 'linear-gradient(to right, #10b981, #34d399)'
                              : p.comparator_factors?.matchup.bucket_color === 'amber'
                              ? 'linear-gradient(to right, #f59e0b, #fbbf24)'
                              : p.comparator_factors?.matchup.bucket_color === 'rose'
                              ? 'linear-gradient(to right, #f43f5e, #fb7185)'
                              : 'linear-gradient(to right, #06b6d4, #38bdf8)',
                          }}
                        />
                      </div>
                    </div>

                    {/* 4. Game Environment */}
                    <div
                      className="factor-item-interactive"
                      onClick={() => toggleFactorFormula(p.player_id, 'environment')}
                      title="Click to inspect raw inputs & transparent formula"
                    >
                      <div className="factor-bar-label">
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span>Game Environment</span>
                          {p.comparator_factors?.environment && (
                            <span className={`factor-bar-badge ${p.comparator_factors.environment.bucket_color}`}>
                              {p.comparator_factors.environment.bucket}
                            </span>
                          )}
                        </div>
                        <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{p.components.environment_score}</span>
                      </div>
                      <div className="bar-bg">
                        <div
                          className="bar-fill"
                          style={{
                            width: `${p.components.environment_score}%`,
                            background: p.comparator_factors?.environment.bucket_color === 'emerald'
                              ? 'linear-gradient(to right, #10b981, #34d399)'
                              : p.comparator_factors?.environment.bucket_color === 'amber'
                              ? 'linear-gradient(to right, #f59e0b, #fbbf24)'
                              : p.comparator_factors?.environment.bucket_color === 'rose'
                              ? 'linear-gradient(to right, #f43f5e, #fb7185)'
                              : 'linear-gradient(to right, #06b6d4, #38bdf8)',
                          }}
                        />
                      </div>
                    </div>
                  </div>

                  {/* Toggle Button for Transparent Formula Inspector */}
                  <button
                    type="button"
                    className={`formula-inspect-toggle-btn ${expandedCardFormula[p.player_id] ? 'active' : ''}`}
                    onClick={() => toggleFactorFormula(p.player_id, 'all')}
                  >
                    <span>{expandedCardFormula[p.player_id] ? '▲ Collapse Formula Breakdown' : '🔍 Inspect Transparent Formulas'}</span>
                  </button>

                  {/* Transparent Formula Drawer */}
                  {expandedCardFormula[p.player_id] && p.comparator_factors && (
                    <div className="factor-inspector-drawer">
                      <div className="inspector-factor-tab-bar">
                        {(['all', 'projection', 'opportunity', 'matchup', 'environment'] as const).map((tabKey) => (
                          <button
                            key={tabKey}
                            type="button"
                            className={`inspector-tab-btn ${expandedCardFormula[p.player_id] === tabKey ? 'active' : ''}`}
                            onClick={() => toggleFactorFormula(p.player_id, tabKey)}
                          >
                            {tabKey === 'all' && '📋 All'}
                            {tabKey === 'projection' && '🎯 Projection'}
                            {tabKey === 'opportunity' && '🚜 Opportunity'}
                            {tabKey === 'matchup' && '🛡️ Matchup'}
                            {tabKey === 'environment' && '🚀 Environment'}
                          </button>
                        ))}
                      </div>

                      {(expandedCardFormula[p.player_id] === 'all' || expandedCardFormula[p.player_id] === 'projection') &&
                        renderFactorDetailBox('projection', 'Projection Score Calibration', '🎯', p.comparator_factors.projection)}

                      {(expandedCardFormula[p.player_id] === 'all' || expandedCardFormula[p.player_id] === 'opportunity') &&
                        renderFactorDetailBox('opportunity', 'Opportunity Volume Index', '🚜', p.comparator_factors.opportunity)}

                      {(expandedCardFormula[p.player_id] === 'all' || expandedCardFormula[p.player_id] === 'matchup') &&
                        renderFactorDetailBox('matchup', 'Defensive Matchup Quality', '🛡️', p.comparator_factors.matchup)}

                      {(expandedCardFormula[p.player_id] === 'all' || expandedCardFormula[p.player_id] === 'environment') &&
                        renderFactorDetailBox('environment', 'Game Environment & Weather', '🚀', p.comparator_factors.environment)}
                    </div>
                  )}

                  {/* Reasons Bullets */}
                  <div style={{ marginTop: '16px' }}>
                    <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '8px' }}>
                      EVALUATION DRIVERS & FACTOR BREAKDOWN:
                    </div>
                    <ul className="factor-list">
                      {p.reasons_positive.map((r, i) => renderWhyFactorItem(r, true, `comp-pos-${i}`))}
                      {p.reasons_negative.map((r, i) => renderWhyFactorItem(r, false, `comp-neg-${i}`))}
                    </ul>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 3: WAIVER WIRE UPGRADES */}
      {activeTab === 'waivers' && (
        <div>
          {/* 8-Man Roster Architecture & Bench Audit */}
          {waivers?.architecture_audit && (
            <div className="roster-audit-card">
              <div className="roster-audit-header">
                <div className="audit-grade-display">
                  <div
                    className={`grade-badge-circle ${
                      waivers.architecture_audit.grade.startsWith('A')
                        ? 'grade-A'
                        : waivers.architecture_audit.grade.startsWith('B')
                        ? 'grade-B'
                        : waivers.architecture_audit.grade.startsWith('C')
                        ? 'grade-C'
                        : 'grade-D'
                    }`}
                  >
                    {waivers.architecture_audit.grade}
                  </div>
                  <div>
                    <h3 style={{ fontSize: '18px', fontWeight: 800, margin: 0, color: 'var(--text-primary)' }}>
                      8-Man Roster Architecture & Bench Audit
                    </h3>
                    <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                      Audit Score: <strong style={{ color: 'var(--text-primary)' }}>{waivers.architecture_audit.score} / 100</strong> • Bench Optimization Strategy for Shallow Leagues
                    </div>
                  </div>
                </div>

                <div className="audit-metrics-summary">
                  <div className="audit-metric-box">
                    <div className="label">Contingent RBs Stashed</div>
                    <div className="val" style={{ color: waivers.architecture_audit.handcuff_rb_count >= 2 ? '#34d399' : '#f59e0b' }}>
                      {waivers.architecture_audit.handcuff_rb_count} RBs {waivers.architecture_audit.handcuff_rb_count >= 2 ? '✓' : '⚠️'}
                    </div>
                  </div>

                  <div className="audit-metric-box">
                    <div className="label">Wasted Bench Slots</div>
                    <div className="val" style={{ color: waivers.architecture_audit.wasted_bench_slots.length === 0 ? '#34d399' : '#f43f5e' }}>
                      {waivers.architecture_audit.wasted_bench_slots.length === 0 ? '0 (Clean)' : `${waivers.architecture_audit.wasted_bench_slots.length} Wasted`}
                    </div>
                  </div>
                </div>
              </div>

              <div className="audit-grid">
                {/* Tactical Prescriptions */}
                <div className="audit-section-box">
                  <div className="audit-section-title" style={{ color: '#f59e0b' }}>
                    <span>🎯 Tactical Prescriptions ({waivers.architecture_audit.tactical_prescriptions.length})</span>
                  </div>
                  <ul className="audit-list">
                    {waivers.architecture_audit.tactical_prescriptions.map((rx, idx) => (
                      <li key={idx} className="prescription">
                        <span>→</span>
                        <span>{rx}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Key Strengths */}
                <div className="audit-section-box">
                  <div className="audit-section-title" style={{ color: '#10b981' }}>
                    <span>💪 Architecture Strengths</span>
                  </div>
                  <ul className="audit-list">
                    {waivers.architecture_audit.key_strengths.map((str, idx) => (
                      <li key={idx} className="strength">
                        <span>✓</span>
                        <span>{str}</span>
                      </li>
                    ))}
                    {waivers.architecture_audit.key_strengths.length === 0 && (
                      <li className="warning">
                        <span>⚠️</span>
                        <span>No core architecture strengths detected yet. Consolidate depth and clear backup K/DST.</span>
                      </li>
                    )}
                  </ul>
                </div>

                {/* Wasted Bench Flags (if any) */}
                {waivers.architecture_audit.wasted_bench_slots.length > 0 && (
                  <div className="audit-section-box">
                    <div className="audit-section-title" style={{ color: '#f43f5e' }}>
                      <span>🚫 8-Man Bench Capital Traps</span>
                    </div>
                    <ul className="audit-list">
                      {waivers.architecture_audit.wasted_bench_slots.map((wb, idx) => (
                        <li key={idx} className="warning">
                          <span>⚠️</span>
                          <span>Holding {wb}. In an 8-man league, this roster spot has zero upside. Drop immediately for a high-contingency RB.</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Deadweight Bench Purge Alert */}
          {waivers?.deadweight_drops && waivers.deadweight_drops.length > 0 && (
            <div className="card" style={{ marginBottom: '24px', borderColor: 'rgba(244, 63, 94, 0.4)', background: 'rgba(244, 63, 94, 0.05)' }}>
              <div className="card-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '20px' }}>⚠️</span>
                  <h3 className="card-title" style={{ color: '#f43f5e' }}>8-Man Deadweight Bench Purge Radar</h3>
                </div>
                <span className="pill rose">{waivers.deadweight_drops.length} Deadweight Assets</span>
              </div>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '14px' }}>
                In an 8-team PPR league, roster depth is abundant on waivers. Holding low-ceiling players with no contingent upside burns valuable roster spots needed for elite backup RBs or $0 streaming stashes.
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '12px' }}>
                {waivers.deadweight_drops.map((dw) => (
                  <div key={dw.player_id} style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: '8px', padding: '12px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <strong style={{ fontSize: '15px', color: 'var(--text-primary)' }}>{dw.full_name} ({dw.position})</strong>
                      <span className="pill rose" style={{ fontSize: '10px' }}>Purge Candidate</span>
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
                      Proj: {dw.projected_points} pts • Ceiling: {dw.ceiling_score} • StartScore: {dw.start_score}
                    </div>
                    <div style={{ fontSize: '12px', color: '#fda4af', marginTop: '6px', lineHeight: 1.4 }}>
                      {dw.diagnosis}
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--accent-emerald)', marginTop: '4px', fontWeight: 600 }}>
                      → {dw.suggested_action}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Week N+1 Lookahead Streaming Radar */}
          {((waivers?.lookahead_streaming_dst?.length ?? 0) > 0 || (waivers?.lookahead_streaming_k?.length ?? 0) > 0) && (
            <div className="card" style={{ marginBottom: '24px', borderColor: 'rgba(56, 189, 248, 0.3)', background: 'rgba(56, 189, 248, 0.04)' }}>
              <div className="card-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '20px' }}>🔭</span>
                  <h3 className="card-title" style={{ color: '#38bdf8' }}>Week N+1 Lookahead Streaming Radar</h3>
                </div>
                <span className="pill cyan">Exploit 8-Man Wire Depth</span>
              </div>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
                With 24 defenses and kickers sitting on waivers, world-class 8-man managers stash next week's smash matchups on Friday/Saturday for $0 FAAB before waivers run Tuesday.
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px' }}>
                {/* D/ST Lookaheads */}
                <div>
                  <h4 style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    🛡️ Top Week {waivers?.lookahead_streaming_dst?.[0]?.next_week || 2} D/ST Stashes
                  </h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {waivers?.lookahead_streaming_dst?.map((item) => (
                      <div key={item.player_id} style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: '8px', padding: '10px 12px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <strong style={{ fontSize: '14px', color: 'var(--text-primary)' }}>{item.full_name} ({item.pro_team})</strong>
                          <span className={`pill ${item.matchup_grade === 'FAVORABLE' ? 'emerald' : 'cyan'}`}>
                            {item.matchup_grade} ({item.matchup_score} pts)
                          </span>
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
                          vs {item.next_opponent} in Week {item.next_week}
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--accent-cyan)', marginTop: '4px' }}>
                          {item.tactical_reason}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Kicker Lookaheads */}
                <div>
                  <h4 style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    👟 Top Week {waivers?.lookahead_streaming_k?.[0]?.next_week || 2} Kicker Stashes
                  </h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {waivers?.lookahead_streaming_k?.map((item) => (
                      <div key={item.player_id} style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: '8px', padding: '10px 12px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <strong style={{ fontSize: '14px', color: 'var(--text-primary)' }}>{item.full_name} ({item.pro_team})</strong>
                          <span className={`pill ${item.matchup_grade === 'FAVORABLE' ? 'emerald' : 'cyan'}`}>
                            {item.matchup_grade} ({item.matchup_score} pts)
                          </span>
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
                          vs {item.next_opponent} in Week {item.next_week}
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--accent-emerald)', marginTop: '4px' }}>
                          {item.tactical_reason}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          <div className="card" style={{ marginBottom: '24px' }}>
            <div className="card-header">
              <h3 className="card-title">🎯 High-Impact Waiver Upgrades (Unowned Players)</h3>
              <span className="pill emerald">Drop-Protected</span>
            </div>

            <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '20px' }}>
              Every candidate is verified unowned across all 8 league teams. Suggestions pair the pickup with the
              safest bench drop candidate while protecting your core starters.
            </p>

            <div className="upgrades-list">
              {waivers?.top_upgrades.map((upg, idx) => (
                <div key={idx} className="upgrade-card">
                  <div className="upgrade-header">
                    <div>
                      <span className={`pill ${upg.upgrade_type === 'CONTINGENT_UPSIDE_STASH' ? 'amber' : upg.upgrade_type === 'STARTING_LINEUP_UPGRADE' ? 'emerald' : 'cyan'}`}>
                        {upg.upgrade_type === 'CONTINGENT_UPSIDE_STASH' ? '🚀 CONTINGENT UPSIDE STASH' : upg.upgrade_type}
                      </span>
                      {upg.pickup_player.contingency_score !== undefined && upg.pickup_player.contingency_score > 0 && (
                        <span className="ceiling-floor-tag contingent" style={{ marginLeft: '8px' }}>
                          ⚡ Workhorse Contingency: {upg.pickup_player.contingency_score}
                        </span>
                      )}
                      {upg.pickup_player.live_vorp !== undefined && upg.pickup_player.live_vorp !== null && (
                        <span className="vorp-badge" style={{ marginLeft: '8px' }} title="Live-Wire VORP">
                          VORP: {upg.pickup_player.live_vorp > 0 ? `+${upg.pickup_player.live_vorp}` : upg.pickup_player.live_vorp}
                        </span>
                      )}
                      <h4 style={{ fontSize: '18px', fontWeight: 800, marginTop: '6px' }}>
                        Pickup: {upg.pickup_player.full_name} ({upg.pickup_player.position} - {upg.pickup_player.pro_team})
                      </h4>
                    </div>

                    <div className="upgrade-delta">
                      <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Net Gain</span>
                      <span style={{ fontSize: '20px', fontWeight: 800, color: 'var(--accent-emerald)' }}>
                        +{upg.net_projected_delta} pts
                      </span>
                    </div>
                  </div>

                  <div className="upgrade-details">
                    <div>
                      <strong>Recommended Drop:</strong>{' '}
                      {upg.drop_player ? (
                        <span style={{ color: 'var(--accent-rose)' }}>
                          {upg.drop_player.full_name} ({upg.drop_player.position} - StartScore: {upg.drop_player.start_score})
                        </span>
                      ) : (
                        'Empty Roster Slot'
                      )}
                    </div>
                    <div style={{ marginTop: '6px', color: 'var(--text-secondary)' }}>
                      {upg.rationale}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Streaming Targets */}
          <div className="dashboard-grid">
            <div className="card">
              <h4 style={{ fontSize: '16px', fontWeight: 700, marginBottom: '12px' }}>🛡️ Top D/ST Streamers</h4>
              {waivers?.streaming_dst.map((d) => (
                <div key={d.player_id} className="streamer-item">
                  <span>{d.full_name}</span>
                  <span className="score-badge cyan">{d.start_score}</span>
                </div>
              ))}
            </div>

            <div className="card">
              <h4 style={{ fontSize: '16px', fontWeight: 700, marginBottom: '12px' }}>🎯 Top TE Streamers</h4>
              {waivers?.streaming_te.map((t) => (
                <div key={t.player_id} className="streamer-item">
                  <span>{t.full_name} ({t.pro_team})</span>
                  <span className="score-badge cyan">{t.start_score}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB: 2-FOR-1 CONSOLIDATION TRADES */}
      {activeTab === 'trades' && (
        <div>
          <div className="card" style={{ marginBottom: '24px' }}>
            <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
              <div>
                <h3 className="card-title">🤝 2-for-1 Consolidation Trade Engine (8-Team Alpha Acquirer)</h3>
                <span className="pill amber">Championship Equity</span>
              </div>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => selectedTeamId && loadConsolidationTrades(selectedTeamId)}
                disabled={isLoadingTrades}
              >
                {isLoadingTrades ? '⏳ Scanning League Rosters...' : '🔄 Re-Scan Rival Rosters'}
              </button>
            </div>

            <p style={{ color: 'var(--text-secondary)', fontSize: '14px', lineHeight: 1.5, marginBottom: '20px' }}>
              <strong>The 8-Team Paradigm:</strong> In shallow leagues, roster depth is virtually worthless because the waiver wire is
              saturated with starter-grade talent. The only way to generate true championship equity is packaging 2 solid starters
              for 1 Tier-1 Alpha game-breaker, then immediately backfilling the vacated roster spot with high-VORP wire talent.
            </p>

            {isLoadingTrades ? (
              <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--text-muted)' }}>
                <div style={{ fontSize: '32px', marginBottom: '12px' }}>⚡</div>
                <div style={{ fontSize: '16px', fontWeight: 700 }}>Auditing All 8 League Rosters & Simulating Consolidation Trades...</div>
                <div style={{ fontSize: '13px', marginTop: '6px' }}>Evaluating rival positional deficits and waiver backfill math</div>
              </div>
            ) : consolidationTrades && consolidationTrades.recommendations.length > 0 ? (
              <div className="trades-list">
                {consolidationTrades.recommendations.map((trade) => (
                  <div key={trade.trade_id} className="trade-card">
                    <div className="trade-card-header">
                      <div>
                        <span className={`pill ${trade.feasibility === 'HIGH' ? 'emerald' : trade.feasibility === 'MEDIUM' ? 'amber' : 'rose'}`}>
                          {trade.feasibility} Feasibility
                        </span>
                        {trade.is_championship_target && (
                          <span className="pill purple" style={{ marginLeft: '8px' }}>
                            🏆 Championship Target ({trade.target_playoff_grade} Playoff SoS)
                          </span>
                        )}
                        <h4 style={{ fontSize: '18px', fontWeight: 800, marginTop: '6px', color: 'var(--text-primary)' }}>
                          Target: {trade.target_alpha.full_name} ({trade.target_alpha.position} - {trade.target_alpha.pro_team})
                        </h4>
                        <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                          Rival Team: <strong style={{ color: 'var(--text-secondary)' }}>{trade.partner_team_name}</strong>
                          {trade.target_playoff_sos && (
                            <span style={{ marginLeft: '8px', color: 'var(--accent-cyan)' }}>
                              • Weeks 15-17 SoS: {trade.target_playoff_sos} pts ({trade.target_playoff_grade})
                            </span>
                          )}
                        </div>
                      </div>

                      <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                        <div style={{ textAlign: 'right' }}>
                          <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700 }}>Your Net Gain</span>
                          <div style={{ fontSize: '20px', fontWeight: 900, color: 'var(--accent-emerald)' }}>
                            +{trade.user_net_projected_delta} pts/wk
                          </div>
                          {trade.user_playoff_leverage_delta !== undefined && trade.user_playoff_leverage_delta !== 0 && (
                            <div style={{ fontSize: '11px', color: trade.user_playoff_leverage_delta > 0 ? 'var(--accent-emerald)' : 'var(--text-muted)', marginTop: '2px', fontWeight: 600 }}>
                              {trade.user_playoff_leverage_delta > 0 ? `+${trade.user_playoff_leverage_delta}` : trade.user_playoff_leverage_delta} Playoff SoS
                            </div>
                          )}
                        </div>
                        <div style={{ textAlign: 'right', borderLeft: '1px solid var(--border-subtle)', paddingLeft: '12px' }}>
                          <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700 }}>Rival Net Gain</span>
                          <div style={{ fontSize: '20px', fontWeight: 900, color: '#38bdf8' }}>
                            +{trade.partner_net_projected_delta} pts/wk
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Trade Exchange Grid */}
                    <div className="trade-exchange-grid">
                      {/* You Send */}
                      <div className="trade-column">
                        <div className="trade-column-title">
                          <span>You Send (2 Players)</span>
                          <span className="pill cyan" style={{ fontSize: '9px', padding: '1px 5px' }}>Package</span>
                        </div>
                        {trade.send_players.map((p) => (
                          <div key={p.player_id} className="trade-player-pill">
                            <div>
                              <strong style={{ fontSize: '13px' }}>{p.full_name}</strong>
                              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{p.position} • {p.pro_team}</div>
                            </div>
                            <div style={{ textAlign: 'right' }}>
                              <span style={{ fontSize: '12px', fontWeight: 700 }}>{p.projected_points} pts</span>
                              <div style={{ fontSize: '10px', color: 'var(--accent-cyan)' }}>Score {p.start_score}</div>
                            </div>
                          </div>
                        ))}
                      </div>

                      {/* Divider */}
                      <div className="trade-arrow-divider">⇄</div>

                      {/* You Receive */}
                      <div className="trade-column">
                        <div className="trade-column-title">
                          <span>You Receive (Tier-1 Alpha)</span>
                          <span className="pill purple" style={{ fontSize: '9px', padding: '1px 5px' }}>👑 Alpha</span>
                        </div>
                        <div className="trade-player-pill alpha">
                          <div>
                            <strong style={{ fontSize: '14px', color: '#c084fc' }}>{trade.target_alpha.full_name}</strong>
                            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{trade.target_alpha.position} • {trade.target_alpha.pro_team}</div>
                          </div>
                          <div style={{ textAlign: 'right' }}>
                            <span style={{ fontSize: '14px', fontWeight: 800, color: '#c084fc' }}>{trade.target_alpha.projected_points} pts</span>
                            <div style={{ fontSize: '10px', color: '#a855f7' }}>StartScore {trade.target_alpha.start_score}</div>
                          </div>
                        </div>
                      </div>

                      {/* Plus Wire Backfill */}
                      <div className="trade-arrow-divider">+</div>

                      {/* Waiver Backfill */}
                      <div className="trade-column">
                        <div className="trade-column-title">
                          <span>Free Wire Backfill</span>
                          <span className="pill emerald" style={{ fontSize: '9px', padding: '1px 5px' }}>Free Pickup</span>
                        </div>
                        {trade.waiver_backfill ? (
                          <div className="trade-player-pill backfill">
                            <div>
                              <strong style={{ fontSize: '13px', color: '#34d399' }}>{trade.waiver_backfill.full_name}</strong>
                              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{trade.waiver_backfill.position} • {trade.waiver_backfill.pro_team}</div>
                            </div>
                            <div style={{ textAlign: 'right' }}>
                              <span style={{ fontSize: '12px', fontWeight: 700, color: '#34d399' }}>{trade.waiver_backfill.projected_points} pts</span>
                              <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Free Agent</div>
                            </div>
                          </div>
                        ) : (
                          <div style={{ fontSize: '12px', color: 'var(--text-muted)', padding: '8px' }}>
                            Top waiver replacement player at position
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Trade Rationale */}
                    <div className="trade-rationale-box">
                      <strong>Tactical Audit:</strong> {trade.rationale}
                    </div>

                    {/* 1-Click ESPN Chat Pitch */}
                    <div className="trade-pitch-container">
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '16px' }}>💬</span>
                        <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-primary)' }}>
                          ESPN League Chat / SMS Pitch:
                        </span>
                      </div>
                      <div className="trade-pitch-text">
                        "{trade.pitch_message}"
                      </div>
                      <button
                        className="btn btn-secondary btn-sm"
                        style={{ whiteSpace: 'nowrap', borderColor: copiedPitchId === trade.trade_id ? '#10b981' : undefined }}
                        onClick={() => {
                          navigator.clipboard.writeText(trade.pitch_message)
                          setCopiedPitchId(trade.trade_id)
                          setTimeout(() => setCopiedPitchId(null), 2500)
                        }}
                      >
                        {copiedPitchId === trade.trade_id ? '✓ Copied to Clipboard!' : '📋 Copy Pitch'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '40px 20px', background: 'rgba(255, 255, 255, 0.02)', borderRadius: '8px', border: '1px dashed var(--border-subtle)' }}>
                <div style={{ fontSize: '32px', marginBottom: '8px' }}>🛡️</div>
                <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)' }}>No 2-for-1 Trades Currently Necessary</div>
                <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px', maxWidth: '500px', margin: '4px auto 0' }}>
                  Your roster already possesses dominant Tier-1 alphas, or rival teams do not currently have matching positional deficits where a 2-for-1 package creates mutual value.
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 4: LEAGUE ROSTERS & STANDINGS */}
      {activeTab === 'league' && (
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
                              onClick={() => {
                                if (lineup && lineup.starters.length > 0) {
                                  const matchingStarter = lineup.starters.find(
                                    (s) => s.recommended_player.position === p.position || ['RB', 'WR', 'TE'].includes(p.position)
                                  ) || lineup.starters[0]
                                  setCompareScope('all')
                                  const ids = [matchingStarter.recommended_player.player_id, p.player_id]
                                  setCompareIds(ids)
                                  runComparison(ids)
                                  setActiveTab('compare')
                                }
                              }}
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
      )}

      {/* TAB 5: INJURY WIRE */}
      {activeTab === 'injuries' && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">🩺 Live 2026 NFL Injury Wire</h3>
            <span className="pill rose">
              {injuriesFeed ? `${injuriesFeed.total_count} Official Reports` : 'Live Reports'}
            </span>
          </div>

          <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '20px' }}>
            Official NFL injury designations and practice progression. Questionable players receive automated availability
            discounts in the Start/Sit scoring engine based on Friday practice participation.
          </p>

          {/* Search & Filter Controls */}
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginBottom: '14px', alignItems: 'center' }}>
            <input
              type="text"
              placeholder="🔍 Search player name or team..."
              value={injurySearch}
              onChange={(e) => setInjurySearch(e.target.value)}
              className="select-dropdown"
              style={{ flex: '1', minWidth: '220px', cursor: 'text' }}
            />

            <select
              className="select-dropdown"
              value={injuryPosFilter}
              onChange={(e) => setInjuryPosFilter(e.target.value)}
            >
              <option value="ALL">All Positions</option>
              <option value="QB">QB</option>
              <option value="RB">RB</option>
              <option value="WR">WR</option>
              <option value="TE">TE</option>
              <option value="K">K</option>
              <option value="D/ST">D/ST</option>
            </select>

            <select
              className="select-dropdown"
              value={injuryStatusFilter}
              onChange={(e) => setInjuryStatusFilter(e.target.value)}
            >
              <option value="ALL">All Statuses</option>
              <option value="OUT">Out / IR / Doubtful</option>
              <option value="QUESTIONABLE">Questionable</option>
              <option value="ACTIVE">Active</option>
            </select>

            <button
              className="btn btn-secondary btn-sm"
              onClick={loadInjuries}
              disabled={isLoadingInjuries}
            >
              {isLoadingInjuries ? '⏳ Refreshing...' : '🔄 Refresh Live Feed'}
            </button>
          </div>

          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '16px' }}>
            Showing {filteredInjuries.length} of {injuriesFeed?.total_count || 800} verified NFL reports
          </div>

          <div className="table-responsive">
            <table className="custom-table">
              <thead>
                <tr>
                  <th>Player</th>
                  <th>Team & Pos</th>
                  <th>Status</th>
                  <th>Practice Participation</th>
                  <th>Beat Reporter Detail / Practice Notes</th>
                </tr>
              </thead>
              <tbody>
                {filteredInjuries.map((inj) => (
                  <tr key={inj.athlete_id}>
                    <td style={{ fontWeight: 700 }}>{inj.name}</td>
                    <td>{inj.team} ({inj.position})</td>
                    <td>
                      <InjuryStatusPill
                        status={inj.status}
                        fullName={inj.name}
                        position={inj.position}
                        injuryNote={inj.headline ? `${inj.headline}${inj.notes ? ` - ${inj.notes}` : ''}` : inj.notes}
                      />
                    </td>
                    <td>
                      {inj.practice_status ? (
                        <span className={`pill ${
                          inj.practice_status === 'FULL' ? 'emerald' : inj.practice_status === 'LIMITED' ? 'amber' : 'rose'
                        }`}>
                          {inj.practice_status}
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>Standard</span>
                      )}
                    </td>
                    <td style={{ fontSize: '13px', maxWidth: '440px', lineHeight: '1.4' }}>
                      {inj.headline && (
                        <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>
                          {inj.headline}
                        </div>
                      )}
                      <div style={{ color: 'var(--text-secondary)' }}>
                        {inj.notes || 'No beat notes available.'}
                      </div>
                    </td>
                  </tr>
                ))}
                {filteredInjuries.length === 0 && (
                  <tr>
                    <td colSpan={5} style={{ textAlign: 'center', padding: '36px', color: 'var(--text-muted)' }}>
                      No matching injury reports found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 6: SETTINGS & TUNING */}
      {activeTab === 'settings' && (
        <div className="dashboard-grid">
          {/* League Size Calibration Card */}
          <div className="card" style={{ gridColumn: '1 / -1' }}>
            <div className="card-header">
              <h3 className="card-title">🏆 League Size Calibration & Environment Baselines</h3>
              <span className={`pill ${leagueSizeSetting === 8 ? 'emerald' : 'cyan'}`}>
                {leagueSizeSetting}-Team Mode Active
              </span>
            </div>

            <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '16px' }}>
              8-man leagues present an &quot;All-Star&quot; dynamic where every roster has high baseline talent. The algorithm recalibrates replacement-level baselines, Konami Code QB rushing value, and waiver thresholds accordingly.
            </p>

            <div className="league-size-grid">
              <div
                className={`league-size-card ${leagueSizeSetting === 8 ? 'active' : ''}`}
                onClick={() => setLeagueSizeSetting(8)}
              >
                <div className="league-size-title">
                  <span>⚡ 8-Team Small Field</span>
                  {leagueSizeSetting === 8 && <span className="pill cyan" style={{ fontSize: '10px' }}>Active</span>}
                </div>
                <div className="league-size-desc">
                  Elevated replacement thresholds (RB/WR 15.5 pts, QB 20.5 pts, TE 11.2 pts). Maximizes 90th percentile boom ceiling. Punishes roster-clogging backup QBs/TEs.
                </div>
              </div>

              <div
                className={`league-size-card ${leagueSizeSetting === 10 ? 'active' : ''}`}
                onClick={() => setLeagueSizeSetting(10)}
              >
                <div className="league-size-title">
                  <span>🎯 10-Team Standard</span>
                  {leagueSizeSetting === 10 && <span className="pill cyan" style={{ fontSize: '10px' }}>Active</span>}
                </div>
                <div className="league-size-desc">
                  Balanced baselines (RB/WR 13.0 pts, QB 18.0 pts, TE 9.5 pts). Moderate bench depth tolerance.
                </div>
              </div>

              <div
                className={`league-size-card ${leagueSizeSetting === 12 ? 'active' : ''}`}
                onClick={() => setLeagueSizeSetting(12)}
              >
                <div className="league-size-title">
                  <span>🛡️ 12-Team Deep Field</span>
                  {leagueSizeSetting === 12 && <span className="pill cyan" style={{ fontSize: '10px' }}>Active</span>}
                </div>
                <div className="league-size-desc">
                  Scarcity baselines (RB/WR 11.5 pts, QB 16.5 pts, TE 8.0 pts). High premium on floor and volume reliability.
                </div>
              </div>
            </div>

            {leagueSizeSetting === 8 && (
              <div className="league-rule-callout">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '16px' }}>💡</span>
                  <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)' }}>
                    Active 8-Man PPR Game-Theory Rules (2026–2027 Season)
                  </span>
                </div>
                <div className="league-rule-grid">
                  <div className="league-rule-item">
                    <span className="league-rule-label">Konami Code QB Priority</span>
                    <span className="league-rule-text">
                      QB rushing attempts are weighted at 3.5x pass attempts. 1 rush yd = 2.5 pass yds in standard ESPN PPR. Dual-threat QBs dominate.
                    </span>
                  </div>
                  <div className="league-rule-item">
                    <span className="league-rule-label">Zero Backup QB/TE Rule</span>
                    <span className="league-rule-text">
                      Streaming elite matchups beats holding low-end QB2s/TE2s. Benches are reserved for high-upside backup RBs and breakout WRs.
                    </span>
                  </div>
                  <div className="league-rule-item">
                    <span className="league-rule-label">High Drop Protection</span>
                    <span className="league-rule-text">
                      Waiver drop protection is calibrated to 15.5 proj pts / 78.0 StartScore to ensure borderline studs are never accidentally cut.
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Factor Weights Card */}
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">⚙️ Start/Sit Factor Weights</h3>
              <span className="pill cyan">Normalized</span>
            </div>

            <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '16px' }}>
              Adjust heuristic weights to tune the StartScore formula. Weights normalize automatically to 100%.
            </p>

            <div className="weight-slider-group">
              <label>
                <span>Projection Weight: {Math.round(weights.projection_weight * 100)}%</span>
                <input
                  type="range"
                  min="10"
                  max="60"
                  value={Math.round(weights.projection_weight * 100)}
                  onChange={(e) => handleWeightChange('projection_weight', Number(e.target.value) / 100)}
                />
              </label>

              <label>
                <span>Opportunity / Volume Weight: {Math.round(weights.opportunity_weight * 100)}%</span>
                <input
                  type="range"
                  min="5"
                  max="40"
                  value={Math.round(weights.opportunity_weight * 100)}
                  onChange={(e) => handleWeightChange('opportunity_weight', Number(e.target.value) / 100)}
                />
              </label>

              <label>
                <span>Defensive Matchup Weight: {Math.round(weights.matchup_weight * 100)}%</span>
                <input
                  type="range"
                  min="5"
                  max="40"
                  value={Math.round(weights.matchup_weight * 100)}
                  onChange={(e) => handleWeightChange('matchup_weight', Number(e.target.value) / 100)}
                />
              </label>

              <label>
                <span>Game Environment / Implied Total: {Math.round(weights.environment_weight * 100)}%</span>
                <input
                  type="range"
                  min="0"
                  max="25"
                  value={Math.round(weights.environment_weight * 100)}
                  onChange={(e) => handleWeightChange('environment_weight', Number(e.target.value) / 100)}
                />
              </label>

              <label>
                <span>Health / Availability Discount: {Math.round(weights.health_weight * 100)}%</span>
                <input
                  type="range"
                  min="0"
                  max="25"
                  value={Math.round(weights.health_weight * 100)}
                  onChange={(e) => handleWeightChange('health_weight', Number(e.target.value) / 100)}
                />
              </label>

              <label>
                <span>Weather Conditions Weight: {Math.round(weights.weather_weight * 100)}%</span>
                <input
                  type="range"
                  min="0"
                  max="15"
                  value={Math.round(weights.weather_weight * 100)}
                  onChange={(e) => handleWeightChange('weather_weight', Number(e.target.value) / 100)}
                />
              </label>
            </div>

            <div style={{ marginTop: '20px', display: 'flex', gap: '12px' }}>
              <button className="btn btn-primary" onClick={saveWeights}>
                Save Weights & Re-calculate
              </button>
            </div>
          </div>

          {/* Backtesting & Auto-Tuning Card */}
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">🔬 Automated Backtesting & Tuning</h3>
              <span className="pill emerald">Empirical Calibration</span>
            </div>

            <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '16px' }}>
              Replays previous games against actual fantasy points scored to optimize factor weights.
            </p>

            <button className="btn btn-secondary" onClick={runBacktesting}>
              ⚡ Run Weight Tuning Optimizer
            </button>

            {tuningMessage && (
              <div className="diag-box success" style={{ marginTop: '16px' }}>
                {tuningMessage}
              </div>
            )}

            {backtest && (
              <div style={{ marginTop: '16px' }}>
                <div className="config-list">
                  <div className="config-item">
                    <span className="config-label">Retrospective Accuracy</span>
                    <span className="config-value configured">{backtest.overall_accuracy_pct}%</span>
                  </div>
                  <div className="config-item">
                    <span className="config-label">Lineup Efficiency</span>
                    <span className="config-value configured">{backtest.overall_efficiency_pct}%</span>
                  </div>
                  <div className="config-item">
                    <span className="config-label">Audited Weeks</span>
                    <span className="config-value">{backtest.total_weeks_audited} Week(s)</span>
                  </div>
                </div>
              </div>
            )}

            {/* League Connection Info */}
            <div style={{ marginTop: '24px', paddingTop: '20px', borderTop: '1px solid var(--border-subtle)' }}>
              <h4 style={{ fontSize: '15px', fontWeight: 700, marginBottom: '8px' }}>ESPN League Connection</h4>
              <div className="config-list">
                <div className="config-item">
                  <span className="config-label">League ID</span>
                  <span className="config-value configured">{league?.id || 1841917737}</span>
                </div>
                <div className="config-item">
                  <span className="config-label">Scoring Format</span>
                  <span className="config-value configured">Full PPR (1.0)</span>
                </div>
                <div className="config-item">
                  <span className="config-label">Last SQLite Sync</span>
                  <span className="config-value">{league?.last_synced_at ? new Date(league.last_synced_at).toLocaleTimeString() : 'Active'}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 8: FANTASYPROS ECR & STREAMERS */}

      {activeTab === 'fantasypros' && (
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
                        Week {w} {w === (league?.current_week || 1) ? '(Current)' : ''}
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
                        <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                          {s.pro_team} • {s.opponent || 'TBD'}
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
                              <th>Opponent</th>
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
                                  <td>{p.player_opponent || '—'}</td>
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
                          <th>Opponent</th>
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
                              <td>{p.player_opponent || '—'}</td>
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
                                  <td>{p.team || 'FA'}</td>
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
        </div>
      )}

      {/* PRE-FLIGHT LINEUP PUSH TO ESPN MODAL */}

      {showPushModal && pushPreview && (
        <div className="modal-overlay" onClick={() => setShowPushModal(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <div className="modal-title">🚀 Push Lineup to ESPN</div>
                <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                  {pushPreview.team_name} • Week {league?.current_week || 1}
                </div>
              </div>
              <button className="modal-close-btn" onClick={() => setShowPushModal(false)}>
                ✕
              </button>
            </div>

            <div className="modal-body">
              {pushResult && (
                <div className={`diag-box ${pushResult.success ? 'success' : 'error'}`}>
                  <strong>{pushResult.success ? '✅ Success!' : '⚠️ Result:'}</strong> {pushResult.message}
                </div>
              )}

              {pushPreview.moves_count === 0 ? (
                <div style={{ textAlign: 'center', padding: '24px 0' }}>
                  <div style={{ fontSize: '36px', marginBottom: '8px' }}>🎉</div>
                  <h4 style={{ fontWeight: 700, fontSize: '16px', color: 'var(--accent-emerald)' }}>
                    Your ESPN Lineup is Already 100% Optimal!
                  </h4>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginTop: '6px' }}>
                    All recommended starters currently occupy their highest-scoring active slots on ESPN. No roster changes needed.
                  </p>
                </div>
              ) : (
                <>
                  <div style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>
                    Review the starter and bench movements below. Uncheck any individual swap you wish to exclude before committing to ESPN:
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {pushPreview.moves.map((move) => {
                      const isChecked = selectedMoveIds.includes(move.player_id)
                      const isStarterPromotion = move.to_slot_id !== 20
                      return (
                        <div
                          key={`${move.player_id}_${move.from_slot_id}_${move.to_slot_id}`}
                          className="push-move-card"
                          style={{
                            borderLeft: isStarterPromotion
                              ? '4px solid var(--accent-emerald)'
                              : '4px solid var(--text-muted)',
                          }}
                        >
                          <div className="push-move-left">
                            <input
                              type="checkbox"
                              checked={isChecked}
                              onChange={() => toggleMoveSelection(move.player_id)}
                              style={{ width: '16px', height: '16px', cursor: 'pointer' }}
                            />
                            <div>
                              <div className="push-move-title">
                                {move.player_name}{' '}
                                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                                  ({move.position})
                                </span>
                              </div>
                              <div className="push-move-detail">
                                <span className="slot-badge" style={{ fontSize: '10px' }}>{move.from_slot_name}</span>
                                <span className="push-arrow">➔</span>
                                <span className="slot-badge" style={{ fontSize: '10px', background: isStarterPromotion ? 'rgba(16,185,129,0.2)' : 'rgba(255,255,255,0.08)' }}>
                                  {move.to_slot_name}
                                </span>
                              </div>
                            </div>
                          </div>

                          <div style={{ textAlign: 'right' }}>
                            <div style={{ fontSize: '13px', fontWeight: 700, color: move.net_gain >= 0 ? 'var(--accent-emerald)' : 'var(--text-muted)' }}>
                              {move.net_gain >= 0 ? `+${move.net_gain.toFixed(1)} pts` : `${move.net_gain.toFixed(1)} pts`}
                            </div>
                            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                              StartScore: {move.start_score}
                            </div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </>
              )}
            </div>

            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setShowPushModal(false)}>
                Cancel
              </button>
              {pushPreview.moves_count > 0 && (
                <button
                  className="btn btn-primary"
                  style={{
                    backgroundColor: '#10b981',
                    borderColor: '#10b981',
                    color: '#022c22',
                    fontWeight: 800,
                  }}
                  onClick={handleExecutePush}
                  disabled={isPushing || selectedMoveIds.length === 0}
                >
                  {isPushing ? '⏳ Submitting to ESPN...' : `Confirm & Push (${selectedMoveIds.length} Moves)`}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
