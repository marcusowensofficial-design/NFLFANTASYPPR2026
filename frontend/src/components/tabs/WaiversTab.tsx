import React from 'react'
import type { WaiverAnalysisResult } from '../../types'

export interface WaiversTabProps {
  waivers: WaiverAnalysisResult | null
}

export const WaiversTab: React.FC<WaiversTabProps> = ({ waivers }) => {
  return (
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
  )
}
