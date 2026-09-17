import React, { useState, useMemo } from 'react'
import type { WaiverAnalysisResult, PositionalNeedItem } from '../../types'
import { NFLTeamLogo } from '../shared/NFLTeamLogo'

export interface WaiversTabProps {
  waivers: WaiverAnalysisResult | null
  onOpenGameLog?: (playerId: number | string, name?: string, pos?: string, team?: string) => void
}

type TacticalCategory = 'ALL' | 'PRIORITY' | 'CONSENSUS_RADAR' | 'HANDCUFFS' | 'BREAKOUTS' | 'STREAMERS' | 'LEDGER'

export const WaiversTab: React.FC<WaiversTabProps> = ({ waivers, onOpenGameLog }) => {
  const [activeCategory, setActiveCategory] = useState<TacticalCategory>('ALL')
  const [consensusPosFilter, setConsensusPosFilter] = useState<string>('ALL')
  const [consensusAvailOnly, setConsensusAvailOnly] = useState<boolean>(false)
  const [consensusSearch, setConsensusSearch] = useState<string>('')

  // Flatten consensus players across all positions
  const allConsensusPlayers = useMemo(() => {
    if (!waivers?.consensus_board) return []
    return Object.entries(waivers.consensus_board).flatMap(([pos, players]) =>
      players.map((p) => ({ ...p, ui_pos: pos }))
    )
  }, [waivers?.consensus_board])

  const totalAvailableConsensus = useMemo(() => {
    return allConsensusPlayers.filter((p) => p.availability_status === 'AVAILABLE').length
  }, [allConsensusPlayers])

  const filteredConsensusPlayers = useMemo(() => {
    return allConsensusPlayers.filter((p) => {
      if (consensusPosFilter !== 'ALL') {
        const pPos = p.position.toUpperCase()
        const filterPos = consensusPosFilter.toUpperCase()
        if (filterPos === 'D/ST' || filterPos === 'DST') {
          if (pPos !== 'D/ST' && pPos !== 'DST') return false
        } else if (pPos !== filterPos) {
          return false
        }
      }
      if (consensusAvailOnly && p.availability_status !== 'AVAILABLE') {
        return false
      }
      if (consensusSearch.trim()) {
        const q = consensusSearch.toLowerCase().trim()
        const matchesName = p.full_name.toLowerCase().includes(q)
        const matchesTeam = p.pro_team.toLowerCase().includes(q)
        const matchesPos = p.position.toLowerCase().includes(q)
        const matchesSource = p.expert_sources.some((s) => s.toLowerCase().includes(q))
        if (!matchesName && !matchesTeam && !matchesPos && !matchesSource) {
          return false
        }
      }
      return true
    })
  }, [allConsensusPlayers, consensusPosFilter, consensusAvailOnly, consensusSearch])

  if (!waivers) {
    return (
      <div className="card" style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)' }}>
        <p>No waiver analysis available. Sync your ESPN league to scan available free agents.</p>
      </div>
    )
  }

  const irRec = waivers.ir_recommendations?.[0]

  // Filter upgrades based on tactical category
  const filteredUpgrades = waivers.top_upgrades.filter((u) => {
    if (activeCategory === 'ALL') return true
    if (activeCategory === 'PRIORITY') {
      return u.tactical_bucket === 'PRIORITY_STARTER' || u.urgency_tier === 'MUST_ADD'
    }
    if (activeCategory === 'HANDCUFFS') {
      return u.tactical_bucket === 'CONTINGENT_HANDCUFF' || u.upgrade_type === 'CONTINGENT_UPSIDE_STASH'
    }
    if (activeCategory === 'BREAKOUTS') {
      return u.tactical_bucket === 'VOLUME_BREAKOUT' || u.upgrade_type === 'BENCH_STASH'
    }
    return true
  })

  const getNeedLevelBadge = (level: PositionalNeedItem['need_level']) => {
    switch (level) {
      case 'CRITICAL_NEED':
        return <span className="pill rose" style={{ fontSize: '10.5px', fontWeight: 800 }}>🚨 CRITICAL NEED</span>
      case 'HIGH_NEED':
        return <span className="pill amber" style={{ fontSize: '10.5px', fontWeight: 800 }}>⚠️ HIGH NEED</span>
      case 'MODERATE_NEED':
        return <span className="pill cyan" style={{ fontSize: '10.5px', fontWeight: 800 }}>⚡ MODERATE NEED</span>
      case 'LOW_NEED':
      case 'STABLE':
      default:
        return <span className="pill emerald" style={{ fontSize: '10.5px', fontWeight: 800 }}>✅ STABLE</span>
    }
  }

  const handleSelectNeedPosition = (pos: string) => {
    setActiveCategory('CONSENSUS_RADAR')
    setConsensusPosFilter(pos)
  }

  return (
    <div className="waiver-tab-container">
      {/* Executive Waiver Directive Banner */}
      {waivers.executive_summary && (
        <div className="waiver-executive-banner">
          <div className="banner-icon">⚡</div>
          <div className="banner-content">
            <div className="banner-title">Executive Waiver Directive</div>
            <div className="banner-text">{waivers.executive_summary}</div>
          </div>
        </div>
      )}

      {/* Emergency IR Triage Protocol Card */}
      {irRec && (
        <div className="ir-triage-card">
          <div className="ir-triage-header">
            <div className="ir-badge">🚨 IR TRIAGE ACTION REQUIRED</div>
            <div className="ir-free-tag">✨ $0 DROP PENALTY</div>
          </div>
          <h3 className="ir-triage-title">
            Action: Move {irRec.full_name} ({irRec.position} - {irRec.injury_status}) into Designated IR Slot
          </h3>
          <p className="ir-triage-desc">
            <strong>Do NOT drop {irRec.full_name}!</strong> As an elite consensus asset currently marked{' '}
            <span style={{ color: 'var(--accent-rose)', fontWeight: 700 }}>{irRec.injury_status}</span>, moving him to your
            designated IR slot vacates an active roster spot immediately. This unlocks a free waiver claim on{' '}
            <strong style={{ color: 'var(--accent-emerald)' }}>{irRec.suggested_wire_add}</strong> without dropping any active player.
          </p>
          <div className="ir-steps-grid">
            {irRec.tactical_steps.map((step, idx) => (
              <div key={idx} className="ir-step-pill">
                <span>{step}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Positional Needs Status Diagnostic Banner */}
      {waivers.positional_needs && waivers.positional_needs.length > 0 && (
        <div className="positional-needs-card">
          <div className="positional-needs-header">
            <div>
              <div className="positional-needs-title-row">
                <span style={{ fontSize: '18px' }}>🎯</span>
                <h3 className="positional-needs-title">Roster Positional Needs Diagnostic</h3>
                <span className="pill purple" style={{ fontSize: '11px', fontWeight: 700 }}>
                  Week 2 2026 Intelligence
                </span>
              </div>
              <p className="positional-needs-desc">
                Cross-references starter health, depth vulnerabilities, and cut candidates to target consensus pickups where your lineup needs them most.
              </p>
            </div>
            <button
              className="btn btn-secondary btn-sm browse-consensus-btn"
              onClick={() => {
                setActiveCategory('CONSENSUS_RADAR')
                setConsensusPosFilter('ALL')
              }}
            >
              🏆 View All 47 Consensus Plays ➔
            </button>
          </div>

          <div className="positional-needs-grid">
            {waivers.positional_needs.map((n) => {
              const isCritical = n.need_level === 'CRITICAL_NEED'
              const isHigh = n.need_level === 'HIGH_NEED'
              const isMod = n.need_level === 'MODERATE_NEED'

              return (
                <div
                  key={n.position}
                  className={`positional-need-tile ${
                    isCritical ? 'tile-critical' : isHigh ? 'tile-high' : isMod ? 'tile-moderate' : 'tile-stable'
                  }`}
                  onClick={() => handleSelectNeedPosition(n.position)}
                  title={`Click to view expert consensus ${n.position} targets`}
                >
                  <div className="need-tile-top">
                    <span className="need-tile-pos">{n.position}</span>
                    {getNeedLevelBadge(n.need_level)}
                  </div>
                  <div className="need-tile-starter">{n.starter_summary}</div>
                  <div className="need-tile-driver">{n.primary_driver}</div>
                  {n.recommended_consensus_targets && n.recommended_consensus_targets.length > 0 && (
                    <div className="need-tile-targets">
                      <span className="target-label">Top Wire Targets:</span>
                      <span className="target-names">{n.recommended_consensus_targets.slice(0, 2).join(', ')}</span>
                    </div>
                  )}
                  <div className="need-tile-action">
                    Explore Consensus {n.position}s ➔
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Tactical Category Filter Navigation */}
      <div className="waiver-nav-tabs">
        <button
          className={`waiver-nav-btn ${activeCategory === 'ALL' ? 'active' : ''}`}
          onClick={() => setActiveCategory('ALL')}
        >
          🔥 All Upgrades ({waivers.top_upgrades.length})
        </button>
        <button
          className={`waiver-nav-btn consensus-tab-highlight ${activeCategory === 'CONSENSUS_RADAR' ? 'active' : ''}`}
          onClick={() => setActiveCategory('CONSENSUS_RADAR')}
        >
          🏆 2026 Consensus Radar ({allConsensusPlayers.length || 47})
          {totalAvailableConsensus > 0 && (
            <span className="consensus-avail-badge">
              {totalAvailableConsensus} on Wire
            </span>
          )}
        </button>
        <button
          className={`waiver-nav-btn ${activeCategory === 'PRIORITY' ? 'active' : ''}`}
          onClick={() => setActiveCategory('PRIORITY')}
        >
          ⭐ Priority Starters (
          {waivers.top_upgrades.filter((u) => u.tactical_bucket === 'PRIORITY_STARTER' || u.urgency_tier === 'MUST_ADD').length})
        </button>
        <button
          className={`waiver-nav-btn ${activeCategory === 'HANDCUFFS' ? 'active' : ''}`}
          onClick={() => setActiveCategory('HANDCUFFS')}
        >
          🚀 RB Handcuffs (
          {waivers.top_upgrades.filter((u) => u.tactical_bucket === 'CONTINGENT_HANDCUFF' || u.upgrade_type === 'CONTINGENT_UPSIDE_STASH').length})
        </button>
        <button
          className={`waiver-nav-btn ${activeCategory === 'BREAKOUTS' ? 'active' : ''}`}
          onClick={() => setActiveCategory('BREAKOUTS')}
        >
          📈 Volume Breakouts (
          {waivers.top_upgrades.filter((u) => u.tactical_bucket === 'VOLUME_BREAKOUT' || u.upgrade_type === 'BENCH_STASH').length})
        </button>
        <button
          className={`waiver-nav-btn ${activeCategory === 'STREAMERS' ? 'active' : ''}`}
          onClick={() => setActiveCategory('STREAMERS')}
        >
          🛡️ Streaming Radar
        </button>
        <button
          className={`waiver-nav-btn ${activeCategory === 'LEDGER' ? 'active' : ''}`}
          onClick={() => setActiveCategory('LEDGER')}
        >
          ✂️ Bench Security Ledger ({waivers.bench_security_ledger?.length ?? 0})
        </button>
      </div>

      {/* 2026 EXPERT CONSENSUS RADAR BOARD (Dedicated View) */}
      {activeCategory === 'CONSENSUS_RADAR' && (
        <div className="card consensus-radar-card" style={{ marginBottom: '24px' }}>
          <div className="card-header consensus-board-header">
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '22px' }}>🏆</span>
                <h3 className="card-title" style={{ color: '#38bdf8' }}>
                  2026 Week 2 Expert Consensus Wire Board
                </h3>
              </div>
              <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginTop: '4px' }}>
                Synthesizes national consensus rankings from <strong>FantasyPros, CBS Sports, NFL.com, RotoBaller, FTN, PFF, SI, and Athlon Sports</strong> — cross-referenced live with your league wire.
              </p>
            </div>
            <span className="pill emerald">Live Wire Synchronized</span>
          </div>

          {/* Controls Bar: Position Tabs, Availability Toggle, and Search */}
          <div className="consensus-controls-container">
            {/* Position Filter Buttons */}
            <div className="consensus-pos-pills">
              {['ALL', 'TE', 'WR', 'RB', 'QB', 'D/ST', 'K'].map((pos) => {
                const count = pos === 'ALL'
                  ? allConsensusPlayers.length
                  : allConsensusPlayers.filter((p) => {
                      const pPos = p.position.toUpperCase()
                      if (pos === 'D/ST') return pPos === 'D/ST' || pPos === 'DST'
                      return pPos === pos.toUpperCase()
                    }).length

                const need = waivers.positional_needs?.find((n) => {
                  if (pos === 'D/ST') return n.position === 'D/ST' || n.position === 'DST'
                  return n.position.toUpperCase() === pos.toUpperCase()
                })

                const isCrit = need?.need_level === 'CRITICAL_NEED'
                const isHigh = need?.need_level === 'HIGH_NEED'

                return (
                  <button
                    key={pos}
                    className={`consensus-pos-btn ${consensusPosFilter === pos ? 'active' : ''}`}
                    onClick={() => setConsensusPosFilter(pos)}
                  >
                    <span>{pos} ({count})</span>
                    {isCrit && <span className="pos-need-dot critical" title="Diagnosed Critical Need" />}
                    {isHigh && <span className="pos-need-dot high" title="Diagnosed High Need" />}
                  </button>
                )
              })}
            </div>

            {/* Secondary Filters: Wire Availability Toggle & Search Input */}
            <div className="consensus-filter-tools">
              <label className="consensus-avail-toggle">
                <input
                  type="checkbox"
                  checked={consensusAvailOnly}
                  onChange={(e) => setConsensusAvailOnly(e.target.checked)}
                />
                <span>🟢 Wire Available Only</span>
              </label>

              <div className="consensus-search-box">
                <span className="search-icon">🔍</span>
                <input
                  type="text"
                  placeholder="Search player, team, outlet..."
                  value={consensusSearch}
                  onChange={(e) => setConsensusSearch(e.target.value)}
                  className="consensus-search-input"
                />
                {consensusSearch && (
                  <button
                    type="button"
                    className="clear-search-btn"
                    onClick={() => setConsensusSearch('')}
                  >
                    ✕
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Player Grid */}
          <div className="consensus-players-grid">
            {filteredConsensusPlayers.map((item, idx) => {
              const isAvail = item.availability_status === 'AVAILABLE'
              const isUser = item.availability_status === 'ROSTERED_USER'

              return (
                <div
                  key={`${item.full_name}-${idx}`}
                  className={`consensus-player-card ${isAvail ? 'card-available' : 'card-rostered'} ${
                    item.tailored_to_need ? 'card-need-tailored' : ''
                  }`}
                >
                  {/* Top Card Header */}
                  <div className="consensus-card-header">
                    <div className="consensus-player-lead">
                      <div className="consensus-rank-badge">
                        #{item.rank} {item.position}
                      </div>
                      <NFLTeamLogo team={item.pro_team} size={36} />
                      <div>
                        <h4
                          className="consensus-player-name"
                          style={{
                            cursor: onOpenGameLog && item.player_id ? 'pointer' : 'default',
                            color: onOpenGameLog && item.player_id ? 'var(--accent-cyan)' : 'inherit',
                          }}
                          onClick={() =>
                            onOpenGameLog &&
                            item.player_id &&
                            onOpenGameLog(item.player_id, item.full_name, item.position, item.pro_team)
                          }
                          title={onOpenGameLog && item.player_id ? `View game log for ${item.full_name}` : undefined}
                        >
                          {item.full_name}
                        </h4>
                        <div className="consensus-player-team">
                          {item.position} &bull; {item.pro_team} &bull; Proj: <strong>{item.projected_points} fpts</strong>
                        </div>
                      </div>
                    </div>

                    <div className="consensus-status-badge">
                      {isAvail ? (
                        <span className="wire-status-pill available">
                          🟢 Available on Wire
                        </span>
                      ) : isUser ? (
                        <span className="wire-status-pill user">
                          👤 On Your Roster
                        </span>
                      ) : (
                        <span className="wire-status-pill opponent">
                          🔒 Rostered (Opponent)
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Need Tailored & Tier Strip */}
                  <div className="consensus-tier-strip">
                    <span className="pill purple" style={{ fontSize: '11px', fontWeight: 800 }}>
                      {item.consensus_tier}
                    </span>
                    {item.tailored_to_need && (
                      <span className="pill amber" style={{ fontSize: '11px', fontWeight: 800 }}>
                        🎯 Solves Diagnosed Need
                      </span>
                    )}
                    <span className="pill emerald" style={{ fontSize: '11px', fontWeight: 800 }}>
                      💰 FAAB: {item.faab_range} ({item.faab_recommended_pct}%)
                    </span>
                  </div>

                  {/* Realized Week 1 Metric Callout */}
                  <div className="consensus-metric-box">
                    <div className="metric-tag">📊 WEEK 1 REALIZED METRICS:</div>
                    <div className="metric-text">{item.week_1_metric}</div>
                  </div>

                  {/* Expert Rationale */}
                  <div className="consensus-rationale-box">
                    <div className="rationale-tag">🧠 EXPERT CONSENSUS RATIONALE:</div>
                    <div className="rationale-body">{item.expert_rationale}</div>
                  </div>

                  {/* Expert Outlets Citations */}
                  <div className="consensus-sources-box">
                    <span className="sources-label">📰 Industry Consensus Outlets:</span>
                    <div className="sources-list">
                      {item.expert_sources.map((src, sIdx) => (
                        <span key={sIdx} className="source-tag-pill">
                          {src}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Footer with Log Button */}
                  {onOpenGameLog && item.player_id && (
                    <div className="consensus-card-footer">
                      <button
                        type="button"
                        className="btn btn-secondary btn-xs"
                        style={{ width: '100%', justifyContent: 'center' }}
                        onClick={() =>
                          onOpenGameLog(item.player_id!, item.full_name, item.position, item.pro_team)
                        }
                      >
                        📊 View Week 1 Box & Target Log
                      </button>
                    </div>
                  )}
                </div>
              )
            })}

            {filteredConsensusPlayers.length === 0 && (
              <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)', gridColumn: '1 / -1' }}>
                <p style={{ fontSize: '16px', fontWeight: 600 }}>No consensus players match your current filter.</p>
                <button
                  className="btn btn-secondary btn-sm"
                  style={{ marginTop: '12px' }}
                  onClick={() => {
                    setConsensusPosFilter('ALL')
                    setConsensusAvailOnly(false)
                    setConsensusSearch('')
                  }}
                >
                  Reset All Filters
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Primary Waiver Upgrades Feed (Shown for ALL, PRIORITY, HANDCUFFS, BREAKOUTS) */}
      {activeCategory !== 'STREAMERS' && activeCategory !== 'LEDGER' && activeCategory !== 'CONSENSUS_RADAR' && (
        <div className="card" style={{ marginBottom: '24px' }}>
          <div className="card-header">
            <div>
              <h3 className="card-title">🎯 Human-Pro Lineup Upgrades & Tactical Wire Claims</h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginTop: '4px' }}>
                Every recommendation is tailored to diagnosed roster needs and cross-referenced with 2026 Week 2 expert consensus value.
              </p>
            </div>
            <span className="pill emerald">8-Man Depth Calibrated</span>
          </div>

          <div className="upgrades-list">
            {filteredUpgrades.map((upg, idx) => {
              const isMustAdd = upg.urgency_tier === 'MUST_ADD'
              const isHighPri = upg.urgency_tier === 'HIGH_PRIORITY'
              const isIRAdd = upg.action_type === 'MOVE_TO_IR_AND_ADD'

              return (
                <div
                  key={idx}
                  className={`pro-upgrade-card ${isMustAdd ? 'must-add-card' : ''} ${
                    upg.is_need_tailored ? 'upgrade-tailored-need' : ''
                  }`}
                >
                  {/* Need Tailored Top Banner */}
                  {upg.is_need_tailored && (
                    <div className="upgrade-need-banner">
                      <span className="need-banner-icon">🎯</span>
                      <span className="need-banner-text">
                        <strong>TAILORED TO ROSTER NEED: {upg.pickup_player.position}</strong> &bull; Directly targets diagnosed roster vulnerability
                      </span>
                    </div>
                  )}

                  <div className="pro-upgrade-top-bar">
                    <div className="badge-cluster">
                      {/* Urgency Pill */}
                      <span
                        className={`pill ${
                          isMustAdd ? 'rose' : isHighPri ? 'amber' : 'cyan'
                        }`}
                        style={{ fontWeight: 800, fontSize: '11px', letterSpacing: '0.04em' }}
                      >
                        {isMustAdd
                          ? '🔥 MUST-ADD (TIER 1 PRIORITY)'
                          : isHighPri
                          ? '⚡ HIGH-PRIORITY CLAIM'
                          : '🎯 SPECULATIVE STASH'}
                      </span>

                      {/* Consensus Rank Pill if available */}
                      {upg.consensus_rank && (
                        <span className="pill gold" style={{ fontSize: '11px', fontWeight: 800 }}>
                          🏆 #{upg.consensus_rank} Consensus {upg.pickup_player.position}
                          {upg.consensus_tier ? ` (${upg.consensus_tier})` : ''}
                        </span>
                      )}

                      {/* Tactical Bucket */}
                      <span className="pill purple" style={{ fontSize: '11px' }}>
                        {upg.tactical_bucket === 'PRIORITY_STARTER'
                          ? '⭐ Priority Starter'
                          : upg.tactical_bucket === 'CONTINGENT_HANDCUFF'
                          ? '🚀 Workhorse Handcuff'
                          : '📈 Volume Breakout'}
                      </span>

                      {/* Action Type */}
                      <span
                        className={`pill ${isIRAdd ? 'emerald' : 'slate'}`}
                        style={{ fontSize: '11px' }}
                      >
                        {isIRAdd ? '✨ IR Triage Claim ($0 Drop Penalty)' : '🔄 1-for-1 Add/Drop'}
                      </span>
                    </div>

                    {/* FAAB Guidance Box */}
                    {upg.faab_recommended_pct !== undefined && upg.faab_recommended_pct > 0 && (
                      <div className="faab-badge-box">
                        <div className="faab-label">FAAB TARGET</div>
                        <div className="faab-val">
                          ${upg.faab_recommended_amount} ({upg.faab_recommended_pct}%)
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Player Transaction Banner */}
                  <div className="pro-transaction-banner">
                    <div className="transaction-party pickup">
                      <NFLTeamLogo team={upg.pickup_player.pro_team} size={40} />
                      <div>
                        <div className="trans-sub">ADD FREE AGENT</div>
                        <h4 className="trans-name" style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                          <span
                            style={{
                              cursor: onOpenGameLog ? 'pointer' : 'default',
                              color: onOpenGameLog ? 'var(--accent-cyan)' : 'inherit',
                              textDecoration: onOpenGameLog ? 'underline dotted' : 'none',
                            }}
                            onClick={() =>
                              onOpenGameLog &&
                              onOpenGameLog(
                                upg.pickup_player.player_id,
                                upg.pickup_player.full_name,
                                upg.pickup_player.position,
                                upg.pickup_player.pro_team
                              )
                            }
                            title={onOpenGameLog ? `View previous game logs for ${upg.pickup_player.full_name}` : undefined}
                          >
                            {upg.pickup_player.full_name}
                          </span>
                          <span className="trans-pos">
                            ({upg.pickup_player.position} - {upg.pickup_player.pro_team})
                          </span>
                          {onOpenGameLog && (
                            <button
                              type="button"
                              className="btn btn-secondary btn-xs"
                              style={{ padding: '1px 6px', fontSize: '10px' }}
                              onClick={() =>
                                onOpenGameLog(
                                  upg.pickup_player.player_id,
                                  upg.pickup_player.full_name,
                                  upg.pickup_player.position,
                                  upg.pickup_player.pro_team
                                )
                              }
                              title={`View game logs for ${upg.pickup_player.full_name}`}
                            >
                              📊 Log
                            </button>
                          )}
                        </h4>
                        <div className="trans-stats">
                          <span>Proj: <strong>{upg.pickup_player.projected_points} fpts</strong></span>
                          <span>StartScore: <strong>{upg.pickup_player.start_score}</strong></span>
                          {upg.pickup_player.contingency_score !== undefined && upg.pickup_player.contingency_score > 0 && (
                            <span style={{ color: 'var(--accent-amber)' }}>
                              ⚡ Contingency: <strong>{upg.pickup_player.contingency_score}</strong>
                            </span>
                          )}
                          {upg.pickup_player.live_vorp !== undefined && upg.pickup_player.live_vorp !== null && (
                            <span style={{ color: 'var(--accent-cyan)' }}>
                              VORP: <strong>+{upg.pickup_player.live_vorp}</strong>
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="trans-arrow">
                      <span>➔</span>
                      <div className="delta-pill">
                        +{upg.net_projected_delta} fpts net
                      </div>
                    </div>

                    <div className="transaction-party drop">
                      {isIRAdd ? (
                        <div className="ir-slot-destination">
                          <div className="trans-sub" style={{ color: 'var(--accent-emerald)' }}>FREE ROSTER VACANCY</div>
                          <div style={{ fontWeight: 700, fontSize: '15px', color: 'var(--text-primary)' }}>
                            Move {irRec?.full_name} to IR
                          </div>
                          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                            Zero active players sacrificed
                          </div>
                        </div>
                      ) : upg.drop_player ? (
                        <>
                          <NFLTeamLogo team={upg.drop_player.pro_team} size={40} />
                          <div>
                            <div className="trans-sub" style={{ color: 'var(--accent-rose)' }}>RECOMMENDED DROP</div>
                            <h4 className="trans-name" style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                              <span
                                style={{
                                  cursor: onOpenGameLog ? 'pointer' : 'default',
                                  color: onOpenGameLog ? 'var(--accent-cyan)' : 'inherit',
                                  textDecoration: onOpenGameLog ? 'underline dotted' : 'none',
                                }}
                                onClick={() =>
                                  onOpenGameLog &&
                                  onOpenGameLog(
                                    upg.drop_player?.player_id || 0,
                                    upg.drop_player?.full_name,
                                    upg.drop_player?.position,
                                    upg.drop_player?.pro_team
                                  )
                                }
                                title={onOpenGameLog ? `View previous game logs for ${upg.drop_player.full_name}` : undefined}
                              >
                                {upg.drop_player.full_name}
                              </span>
                              <span className="trans-pos">
                                ({upg.drop_player.position} - {upg.drop_player.pro_team})
                              </span>
                              {onOpenGameLog && (
                                <button
                                  type="button"
                                  className="btn btn-secondary btn-xs"
                                  style={{ padding: '1px 6px', fontSize: '10px' }}
                                  onClick={() =>
                                    onOpenGameLog(
                                      upg.drop_player?.player_id || 0,
                                      upg.drop_player?.full_name,
                                      upg.drop_player?.position,
                                      upg.drop_player?.pro_team
                                    )
                                  }
                                  title={`View game logs for ${upg.drop_player.full_name}`}
                                >
                                  📊 Log
                                </button>
                              )}
                            </h4>
                            <div className="trans-stats">
                              <span>Proj: <strong>{upg.drop_player.projected_points} fpts</strong></span>
                              <span>StartScore: <strong>{upg.drop_player.start_score}</strong></span>
                              <span className="cut-pill">Safe Sacrifice</span>
                            </div>
                          </div>
                        </>
                      ) : (
                        <div>
                          <div className="trans-sub">EMPTY ROSTER SLOT</div>
                          <div style={{ fontWeight: 700, fontSize: '15px' }}>Free Claim</div>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Human-Pro Scouting Narrative Sections */}
                  <div className="pro-narrative-box">
                    {upg.catalyst && (
                      <div className="narrative-row">
                        <span className="narrative-tag catalyst">🎯 The Role & Catalyst:</span>
                        <span className="narrative-body">{upg.catalyst}</span>
                      </div>
                    )}

                    {upg.matchup_context && (
                      <div className="narrative-row">
                        <span className="narrative-tag matchup">🏟️ Matchup Advantage:</span>
                        <span className="narrative-body">{upg.matchup_context}</span>
                      </div>
                    )}

                    {upg.drop_reassurance && (
                      <div className="narrative-row">
                        <span className="narrative-tag drop">🛡️ Drop Reassurance:</span>
                        <span className="narrative-body">{upg.drop_reassurance}</span>
                      </div>
                    )}

                    {upg.expert_sources && upg.expert_sources.length > 0 && (
                      <div className="narrative-row" style={{ marginTop: '4px' }}>
                        <span className="narrative-tag" style={{ color: '#fbbf24' }}>📰 Verified Consensus:</span>
                        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                          {upg.expert_sources.map((src, sIdx) => (
                            <span key={sIdx} className="expert-source-chip">
                              {src}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )
            })}

            {filteredUpgrades.length === 0 && (
              <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)' }}>
                No players match this specific tactical bucket. Check "All Upgrades" to view all available moves.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Bench Security Ledger (The "Do Not Drop" Defense) */}
      {(activeCategory === 'ALL' || activeCategory === 'LEDGER') && (
        <div className="card" style={{ marginBottom: '24px' }}>
          <div className="card-header">
            <div>
              <h3 className="card-title">🛡️ Roster Bench Security Ledger</h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginTop: '4px' }}>
                Mathematical evaluation of your bench assets. Distinguishes untouchable studs from safe sacrifice candidates.
              </p>
            </div>
            <span className="pill cyan">Anti-Drop Protection</span>
          </div>

          <div className="bench-ledger-grid">
            {waivers.bench_security_ledger?.map((b) => {
              const isUntouchable = b.security_tier === 'UNTOUCHABLE_CORE'
              const isStrongHold = b.security_tier === 'STRONG_HOLD'

              return (
                <div
                  key={b.player_id}
                  className={`ledger-item-card ${
                    isUntouchable ? 'ledger-untouchable' : isStrongHold ? 'ledger-hold' : 'ledger-cut'
                  }`}
                >
                  <div className="ledger-header">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <NFLTeamLogo team={b.pro_team} size={24} />
                      <strong
                        style={{
                          fontSize: '14px',
                          color: onOpenGameLog ? 'var(--accent-cyan)' : 'var(--text-primary)',
                          cursor: onOpenGameLog ? 'pointer' : 'default',
                          textDecoration: onOpenGameLog ? 'underline dotted' : 'none',
                        }}
                        onClick={() => onOpenGameLog && onOpenGameLog(b.player_id, b.full_name, b.position, b.pro_team)}
                        title={onOpenGameLog ? `View previous game logs for ${b.full_name}` : undefined}
                      >
                        {b.full_name} ({b.position})
                      </strong>
                      {onOpenGameLog && (
                        <button
                          type="button"
                          className="btn btn-secondary btn-xs"
                          style={{ padding: '1px 5px', fontSize: '10px' }}
                          onClick={() => onOpenGameLog(b.player_id, b.full_name, b.position, b.pro_team)}
                          title={`View game logs for ${b.full_name}`}
                        >
                          📊 Log
                        </button>
                      )}
                    </div>

                    <span
                      className={`pill ${
                        isUntouchable ? 'emerald' : isStrongHold ? 'amber' : 'rose'
                      }`}
                      style={{ fontSize: '10.5px', fontWeight: 700 }}
                    >
                      {isUntouchable
                        ? '🛡️ UNTOUCHABLE'
                        : isStrongHold
                        ? '🔒 STRONG HOLD'
                        : '✂️ SAFE DROP CANDIDATE'}
                    </span>
                  </div>

                  <div className="ledger-meta-row">
                    <span>
                      Cut Safety: <strong style={{ color: isUntouchable ? '#34d399' : isStrongHold ? '#fbbf24' : '#f43f5e' }}>
                        {b.cut_safety_score}%
                      </strong>
                    </span>
                    {b.ros_rank && <span>Consensus ROS: <strong>#{b.ros_rank}</strong></span>}
                    {b.is_injured && (
                      <span className="pill rose" style={{ fontSize: '10px' }}>
                        INJURED (IR ELIGIBLE)
                      </span>
                    )}
                  </div>

                  <div className="ledger-reasoning">{b.reasoning}</div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Week N+1 Lookahead Streaming Radar */}
      {(activeCategory === 'ALL' || activeCategory === 'STREAMERS') && (
        <div className="card" style={{ marginBottom: '24px', borderColor: 'rgba(56, 189, 248, 0.3)', background: 'rgba(56, 189, 248, 0.04)' }}>
          <div className="card-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '20px' }}>🔭</span>
              <h3 className="card-title" style={{ color: '#38bdf8' }}>Week N+1 Lookahead Streaming Radar</h3>
            </div>
            <span className="pill cyan">Pre-Emptive $0 Stashes</span>
          </div>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
            In shallow leagues, elite managers stash next week's smash matchups on Friday/Saturday for $0 FAAB before Tuesday waivers run.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px' }}>
            {/* D/ST Lookaheads */}
            <div>
              <h4 style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                🛡️ Top Week {waivers?.lookahead_streaming_dst?.[0]?.next_week || 2} D/ST Stashes
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {waivers?.lookahead_streaming_dst?.map((item) => (
                  <div key={item.player_id} className="streamer-subcard">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <NFLTeamLogo team={item.pro_team} size={24} />
                        <strong style={{ fontSize: '14px', color: 'var(--text-primary)' }}>{item.full_name} ({item.pro_team})</strong>
                      </div>
                      <span className={`pill ${item.matchup_grade === 'FAVORABLE' ? 'emerald' : 'cyan'}`}>
                        {item.matchup_grade} ({item.matchup_score} score)
                      </span>
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '5px' }}>
                      <span>vs</span>
                      <NFLTeamLogo team={item.next_opponent} size={16} />
                      <span>{item.next_opponent} in Week {item.next_week}</span>
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
                  <div key={item.player_id} className="streamer-subcard">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <NFLTeamLogo team={item.pro_team} size={24} />
                        <strong style={{ fontSize: '14px', color: 'var(--text-primary)' }}>{item.full_name} ({item.pro_team})</strong>
                      </div>
                      <span className={`pill ${item.matchup_grade === 'FAVORABLE' ? 'emerald' : 'cyan'}`}>
                        {item.matchup_grade} ({item.matchup_score} score)
                      </span>
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '5px' }}>
                      <span>vs</span>
                      <NFLTeamLogo team={item.next_opponent} size={16} />
                      <span>{item.next_opponent} in Week {item.next_week}</span>
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

      {/* Weekly Streaming Specialists (D/ST & TE) */}
      {(activeCategory === 'ALL' || activeCategory === 'STREAMERS') && (
        <div className="dashboard-grid">
          <div className="card">
            <h4 style={{ fontSize: '16px', fontWeight: 700, marginBottom: '12px' }}>🛡️ Top D/ST Streamers</h4>
            {waivers?.streaming_dst.map((d) => (
              <div key={d.player_id} className="streamer-item">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <NFLTeamLogo team={d.pro_team || d.full_name} size={20} />
                  <span>{d.full_name}</span>
                </div>
                <span className="score-badge cyan">{d.start_score}</span>
              </div>
            ))}
          </div>

          <div className="card">
            <h4 style={{ fontSize: '16px', fontWeight: 700, marginBottom: '12px' }}>🎯 Top TE Streamers</h4>
            {waivers?.streaming_te.map((t) => (
              <div key={t.player_id} className="streamer-item">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <NFLTeamLogo team={t.pro_team} size={20} />
                  <span>{t.full_name} ({t.pro_team})</span>
                </div>
                <span className="score-badge cyan">{t.start_score}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
