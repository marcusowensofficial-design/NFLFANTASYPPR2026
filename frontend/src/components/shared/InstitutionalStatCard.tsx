import React, { useMemo } from 'react'
import type { StartSitEvaluation } from '../../types'
import { MatchupStarRating } from './MatchupStarRating'

export const InstitutionalStatCard: React.FC<{ player: StartSitEvaluation; activeSource?: string }> = ({ player: p, activeSource = 'MODEL' }) => {
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
