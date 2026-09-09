import React, { useMemo } from 'react'
import type { StartSitEvaluation } from '../../types'
import { MatchupStarRating } from './MatchupStarRating'
import { Tooltip } from './Tooltip'
import { NFLTeamLogo } from './NFLTeamLogo'

export const InstitutionalStatCard: React.FC<{ player: StartSitEvaluation; activeSource?: string }> = ({ player: p, activeSource = 'MODEL' }) => {
  const prov = p.model_provenance
  const currentActive = p.active_projection_source || activeSource || 'MODEL'

  // Resilient source resolution avoiding nullish coalescing traps on 0.0
  const modelPts: number = [
    p.proj_model,
    p.projected_points_model,
    prov?.raw_model_ppr,
    prov?.sources?.quant_model,
    p.projected_points,
  ].find((v): v is number => typeof v === 'number' && v > 0) ?? p.projected_points

  const fpPts: number | undefined = [
    p.proj_fantasypros,
    p.projected_points_fp,
    p.fp_r2p_pts,
    prov?.fantasypros_ppr,
    prov?.sources?.fantasypros,
    p.fp_itemized_stats?.points_ppr,
    p.fp_itemized_stats?.r2p_pts,
    p.fp_itemized_stats?.calculated_ppr,
  ].find((v): v is number => typeof v === 'number' && v > 0)

  const sleeperPts: number | undefined = [
    p.proj_sleeper,
    p.projected_points_sleeper,
    prov?.sleeper_ppr,
    prov?.sources?.sleeper,
    p.sleeper_itemized_stats?.points_ppr,
    p.sleeper_itemized_stats?.pts_ppr,
    p.sleeper_itemized_stats?.calculated_ppr,
  ].find((v): v is number => typeof v === 'number' && v > 0)

  const espnPts: number | undefined = [
    p.proj_espn,
    p.projected_points_espn,
    prov?.espn_ppr,
    prov?.sources?.espn,
  ].find((v): v is number => typeof v === 'number' && v > 0)

  const consensusPts: number = [
    p.proj_consensus,
    p.projected_points_consensus,
    prov?.consensus_ppr,
    prov?.sources?.consensus,
    p.projected_points,
  ].find((v): v is number => typeof v === 'number' && v > 0) ?? p.projected_points
  
  // Real itemized stats from Sleeper, FantasyPros, or Quant Model
  const stats: Record<string, any> = useMemo(() => {
    if (currentActive === 'SLEEPER' && p.sleeper_itemized_stats && Object.keys(p.sleeper_itemized_stats).length > 0) {
      const hasSleeperVolume = Object.entries(p.sleeper_itemized_stats).some(([k, v]) =>
        ['rush_att', 'rush_yds', 'rec_rec', 'receptions', 'rec', 'pass_att', 'fg', 'fgm', 'def_sack', 'sack'].includes(k) && Number(v) > 0
      )
      if (hasSleeperVolume) return p.sleeper_itemized_stats
    }
    if (currentActive === 'FANTASYPROS' && p.fp_itemized_stats && Object.keys(p.fp_itemized_stats).length > 0) {
      const hasFpVolume = Object.entries(p.fp_itemized_stats).some(([k, v]) =>
        ['rush_att', 'rush_yds', 'rec_rec', 'receptions', 'pass_att', 'fg', 'def_sack'].includes(k) && Number(v) > 0
      )
      if (hasFpVolume) return p.fp_itemized_stats
    }
    return p.itemized_stats || p.sleeper_itemized_stats || p.fp_itemized_stats || {}
  }, [currentActive, p.sleeper_itemized_stats, p.fp_itemized_stats, p.itemized_stats])

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

  // Agreement indicator across all active independent sources
  const validSources = [modelPts, fpPts, sleeperPts, espnPts].filter((v): v is number => typeof v === 'number' && v > 0)
  const spread = validSources.length > 1
    ? Math.round((Math.max(...validSources) - Math.min(...validSources)) * 10) / 10
    : (p.consensus_spread ?? 0)
  const agreement = spread <= 2.2 ? 'HIGH_AGREEMENT' : spread <= 4.5 ? 'MODERATE' : 'SHARP_DIVERGENCE'

  return (
    <div className="institutional-stat-card">
      {/* Header Bar */}
      <div className="statcard-header">
        <div className="statcard-title-group">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            <NFLTeamLogo team={p.pro_team} size={24} />
            <span className="statcard-player-title">
              {p.full_name} ({p.position} • {p.pro_team})
            </span>
            <span className="matchup-tag" style={{ fontSize: '11px', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
              <span>{p.is_home ? 'vs' : '@'}</span>
              <NFLTeamLogo team={p.opponent} size={15} />
              <span>{p.opponent}</span>
            </span>
          </div>
          {p.game_date && (
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              ⏰ {new Date(p.game_date).toLocaleDateString(undefined, { weekday: 'short', hour: 'numeric', minute: '2-digit' })}
            </span>
          )}
        </div>
        <div className="statcard-pills-row">
          {p.dvp_fpa ? (
            <Tooltip term="DVP_FPA">
              <span
                className={`pill ${p.dvp_fpa.tier === 'SMASH' ? 'emerald' : p.dvp_fpa.tier === 'FAVORABLE' ? 'cyan' : p.dvp_fpa.tier === 'TOUGH' ? 'amber' : p.dvp_fpa.tier === 'LOCKDOWN' ? 'rose' : 'zinc'}`}
                style={{ fontSize: '11px', fontWeight: 700, cursor: 'pointer' }}
              >
                🛡️ {p.dvp_fpa.dk_fpa.toFixed(1)} DK FPA ({p.dvp_fpa.vs_avg > 0 ? '+' : ''}{p.dvp_fpa.vs_avg.toFixed(1)}) • #{p.dvp_fpa.rank_softness} Softest
              </span>
            </Tooltip>
          ) : p.opp_dvp_rank ? (
            <Tooltip term="DVP" title={`FantasyPros Consensus: Defense DvP #${p.opp_dvp_rank} vs ${p.position}`}>
              <span
                className={`pill ${p.opp_dvp_rank <= 10 ? 'rose' : p.opp_dvp_rank >= 21 ? 'emerald' : 'amber'}`}
                style={{ fontSize: '11px', fontWeight: 700, cursor: 'pointer' }}
              >
                🛡️ DvP #{p.opp_dvp_rank}
              </span>
            </Tooltip>
          ) : null}
          {p.opp_dvp_rank && (
            <Tooltip term="MATCHUP_STARS" title={`${p.matchup_stars || 3}-Star Matchup Rating vs ${p.opponent}`}>
              <MatchupStarRating stars={p.matchup_stars} oppDvpRank={p.opp_dvp_rank} position={p.position} />
            </Tooltip>
          )}
          {(p.fp_pos_rank || p.fp_rank_ecr) && (
            <Tooltip term="FP_RANK" title={`FantasyPros Consensus: ${p.fp_pos_rank || '#' + p.fp_rank_ecr} PPR`}>
              <span
                className="consensus-pill"
                style={{ cursor: 'pointer' }}
              >
                ⭐ FP {p.fp_pos_rank || `#${p.fp_rank_ecr}`}
              </span>
            </Tooltip>
          )}
          {p.fp_tier && (
            <span className="pill zinc" style={{ fontSize: '11px' }}>
              Tier {p.fp_tier}
            </span>
          )}
        </div>
      </div>

      {/* 5-Way Multi-Source Projections Matrix */}
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

        {/* Source 3: Sleeper / RotoWire */}
        <div className={`source-matrix-card ${currentActive === 'SLEEPER' ? 'active' : ''}`}>
          {currentActive === 'SLEEPER' && <span className="source-card-badge">ACTIVE CHOICE</span>}
          <div className="source-card-header">
            <span>📱</span> Sleeper (RotoWire)
          </div>
          <div className="source-card-pts" style={{ color: currentActive === 'SLEEPER' ? '#38bdf8' : undefined }}>
            {sleeperPts ? `${sleeperPts.toFixed(1)}` : '—'} <span style={{ fontSize: '13px', fontWeight: 600 }}>pts</span>
          </div>
          <div className="source-card-sub">
            RotoWire Official PPR
          </div>
        </div>

        {/* Source 4: ESPN Official */}
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

        {/* Source 5: Multi-Source Consensus */}
        <div className={`source-matrix-card ${currentActive === 'CONSENSUS' ? 'active' : ''}`}>
          {currentActive === 'CONSENSUS' && <span className="source-card-badge">ACTIVE CHOICE</span>}
          <div className="source-card-header">
            <span>⭐</span> Multi-Source Blend
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

      {/* Position-Specific Defensive Matchup Strength (DraftEdge DvP / FPA) */}
      {p.dvp_fpa && (
        <div
          className="dvp-matchup-panel"
          style={{
            marginTop: '12px',
            background: 'rgba(15, 23, 42, 0.65)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: '10px',
            padding: '12px 14px',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '8px',
              flexWrap: 'wrap',
              gap: '6px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '13px' }}>🛡️</span>
              <strong style={{ fontSize: '12px', color: '#f8fafc' }}>
                Defensive Matchup vs {p.position}: {p.opponent}
              </strong>
              <span
                className={`pill ${
                  p.dvp_fpa.tier === 'SMASH'
                    ? 'emerald'
                    : p.dvp_fpa.tier === 'FAVORABLE'
                    ? 'cyan'
                    : p.dvp_fpa.tier === 'TOUGH'
                    ? 'amber'
                    : p.dvp_fpa.tier === 'LOCKDOWN'
                    ? 'rose'
                    : 'zinc'
                }`}
                style={{ fontSize: '10px', fontWeight: 800 }}
              >
                {p.dvp_fpa.tier_label}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ fontSize: '11px', color: '#94a3b8' }}>
                #{p.dvp_fpa.rank_softness} Softest in NFL
              </span>
              {p.dvp_fpa.is_baseline && (
                <Tooltip term="DVP_BASELINE">
                  <span
                    className="pill purple"
                    style={{ fontSize: '9.5px', padding: '1px 6px', cursor: 'help' }}
                  >
                    ℹ️ 2025-26 Weighted Baseline
                  </span>
                </Tooltip>
              )}
            </div>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
              gap: '8px',
              marginTop: '6px',
            }}
          >
            <div className="statcard-box">
              <span className="statcard-box-val emerald" style={{ fontSize: '15px' }}>
                {p.dvp_fpa.dk_fpa.toFixed(1)}{' '}
                <span style={{ fontSize: '11px', fontWeight: 600 }}>DK pts/G</span>
              </span>
              <span className="statcard-box-lbl">DK Fantasy Points Allowed</span>
            </div>

            <div className="statcard-box">
              <span
                className="statcard-box-val"
                style={{
                  fontSize: '15px',
                  color:
                    p.dvp_fpa.vs_avg > 0
                      ? 'var(--accent-emerald)'
                      : p.dvp_fpa.vs_avg < 0
                      ? 'var(--accent-rose)'
                      : 'var(--text-secondary)',
                }}
              >
                {p.dvp_fpa.vs_avg > 0 ? `+${p.dvp_fpa.vs_avg.toFixed(1)}` : p.dvp_fpa.vs_avg.toFixed(1)}
              </span>
              <span className="statcard-box-lbl">vs Positional League Avg</span>
            </div>

            <div className="statcard-box">
              <span className="statcard-box-val" style={{ fontSize: '12.5px', color: '#38bdf8' }}>
                {p.dvp_fpa.trend}
              </span>
              <span className="statcard-box-lbl">Recent Trajectory (L4)</span>
            </div>

            {/* Position-Specific Key Allowed Stats */}
            {p.position === 'QB' && (
              <>
                <div className="statcard-box">
                  <span className="statcard-box-val" style={{ fontSize: '13px' }}>
                    {p.dvp_fpa.supporting_stats.pass_yds
                      ? `${p.dvp_fpa.supporting_stats.pass_yds.toFixed(1)} yds / ${
                          p.dvp_fpa.supporting_stats.pass_td
                            ? p.dvp_fpa.supporting_stats.pass_td.toFixed(2)
                            : 0
                        } TD`
                      : '—'}
                  </span>
                  <span className="statcard-box-lbl">Pass Allowed / G</span>
                </div>
                <div className="statcard-box">
                  <span className="statcard-box-val" style={{ fontSize: '13px' }}>
                    {p.dvp_fpa.supporting_stats.sacks
                      ? `${p.dvp_fpa.supporting_stats.sacks.toFixed(1)} sacks / ${
                          p.dvp_fpa.supporting_stats.int
                            ? p.dvp_fpa.supporting_stats.int.toFixed(2)
                            : 0
                        } INT`
                      : '—'}
                  </span>
                  <span className="statcard-box-lbl">Pressure / Takeaways</span>
                </div>
              </>
            )}

            {['RB', 'FB'].includes(p.position) && (
              <>
                <div className="statcard-box">
                  <span className="statcard-box-val" style={{ fontSize: '13px' }}>
                    {p.dvp_fpa.supporting_stats.rush_yds
                      ? `${p.dvp_fpa.supporting_stats.rush_yds.toFixed(1)} rush yds / ${
                          p.dvp_fpa.supporting_stats.rush_td
                            ? p.dvp_fpa.supporting_stats.rush_td.toFixed(2)
                            : 0
                        } TD`
                      : '—'}
                  </span>
                  <span className="statcard-box-lbl">Ground Allowed / G</span>
                </div>
                <div className="statcard-box">
                  <span className="statcard-box-val" style={{ fontSize: '13px' }}>
                    {p.dvp_fpa.supporting_stats.targets
                      ? `${p.dvp_fpa.supporting_stats.targets.toFixed(1)} tgt / ${
                          p.dvp_fpa.supporting_stats.rec_yds
                            ? p.dvp_fpa.supporting_stats.rec_yds.toFixed(1)
                            : 0
                        } rec yds`
                      : '—'}
                  </span>
                  <span className="statcard-box-lbl">RB Receiving Conceded</span>
                </div>
              </>
            )}

            {p.position === 'WR' && (
              <>
                <div className="statcard-box">
                  <span className="statcard-box-val" style={{ fontSize: '13px' }}>
                    {p.dvp_fpa.supporting_stats.rec_yds
                      ? `${p.dvp_fpa.supporting_stats.rec_yds.toFixed(1)} rec yds / ${
                          p.dvp_fpa.supporting_stats.rec_td
                            ? p.dvp_fpa.supporting_stats.rec_td.toFixed(2)
                            : 0
                        } TD`
                      : '—'}
                  </span>
                  <span className="statcard-box-lbl">WR Conceded / G</span>
                </div>
                <div className="statcard-box">
                  <span className="statcard-box-val" style={{ fontSize: '13px' }}>
                    {p.dvp_fpa.supporting_stats.targets
                      ? `${p.dvp_fpa.supporting_stats.targets.toFixed(1)} targets (${
                          p.dvp_fpa.supporting_stats.rec ? p.dvp_fpa.supporting_stats.rec.toFixed(1) : 0
                        } rec)`
                      : '—'}
                  </span>
                  <span className="statcard-box-lbl">WR Target Funnel</span>
                </div>
              </>
            )}

            {p.position === 'TE' && (
              <>
                <div className="statcard-box">
                  <span className="statcard-box-val" style={{ fontSize: '13px' }}>
                    {p.dvp_fpa.supporting_stats.rec_yds
                      ? `${p.dvp_fpa.supporting_stats.rec_yds.toFixed(1)} yds (${
                          p.dvp_fpa.supporting_stats.targets
                            ? p.dvp_fpa.supporting_stats.targets.toFixed(1)
                            : 0
                        } tgt)`
                      : '—'}
                  </span>
                  <span className="statcard-box-lbl">TE Conceded / G</span>
                </div>
                <div className="statcard-box">
                  <span className="statcard-box-val" style={{ fontSize: '13px' }}>
                    {p.dvp_fpa.supporting_stats.rec_td
                      ? `${p.dvp_fpa.supporting_stats.rec_td.toFixed(2)} TDs / G`
                      : '0.00 TDs'}
                  </span>
                  <span className="statcard-box-lbl">TE Endzone Allowance</span>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
