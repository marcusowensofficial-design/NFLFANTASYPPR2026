import React, { useState } from 'react'
import type { WaiverAnalysisResult } from '../../types'
import { NFLTeamLogo } from '../shared/NFLTeamLogo'

export interface WaiversTabProps {
  waivers: WaiverAnalysisResult | null
}

type TacticalCategory = 'ALL' | 'PRIORITY' | 'HANDCUFFS' | 'BREAKOUTS' | 'STREAMERS' | 'LEDGER'

export const WaiversTab: React.FC<WaiversTabProps> = ({ waivers }) => {
  const [activeCategory, setActiveCategory] = useState<TacticalCategory>('ALL')

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

      {/* Tactical Category Filter Navigation */}
      <div className="waiver-nav-tabs">
        <button
          className={`waiver-nav-btn ${activeCategory === 'ALL' ? 'active' : ''}`}
          onClick={() => setActiveCategory('ALL')}
        >
          🔥 All Upgrades ({waivers.top_upgrades.length})
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

      {/* Primary Waiver Upgrades Feed (Shown for ALL, PRIORITY, HANDCUFFS, BREAKOUTS) */}
      {activeCategory !== 'STREAMERS' && activeCategory !== 'LEDGER' && (
        <div className="card" style={{ marginBottom: '24px' }}>
          <div className="card-header">
            <div>
              <h3 className="card-title">🎯 Human-Pro Lineup Upgrades & Tactical Wire Claims</h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginTop: '4px' }}>
                Every recommendation is cross-referenced with team depth charts, target volumes, and rest-of-season consensus value.
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
                  className={`pro-upgrade-card ${isMustAdd ? 'must-add-card' : ''}`}
                >
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
                        <h4 className="trans-name">
                          {upg.pickup_player.full_name}{' '}
                          <span className="trans-pos">
                            ({upg.pickup_player.position} - {upg.pickup_player.pro_team})
                          </span>
                        </h4>
                        <div className="trans-stats">
                          <span>Proj: <strong>{upg.pickup_player.projected_points} pts</strong></span>
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
                        +{upg.net_projected_delta} pts net
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
                            <h4 className="trans-name">
                              {upg.drop_player.full_name}{' '}
                              <span className="trans-pos">
                                ({upg.drop_player.position} - {upg.drop_player.pro_team})
                              </span>
                            </h4>
                            <div className="trans-stats">
                              <span>Proj: <strong>{upg.drop_player.projected_points} pts</strong></span>
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
                      <strong style={{ fontSize: '14px', color: 'var(--text-primary)' }}>
                        {b.full_name} ({b.position})
                      </strong>
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
                        {item.matchup_grade} ({item.matchup_score} pts)
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
                        {item.matchup_grade} ({item.matchup_score} pts)
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
