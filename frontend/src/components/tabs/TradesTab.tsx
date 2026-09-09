import React, { useState } from 'react'
import type { ConsolidationTradeAnalysisResult } from '../../types'
import { NFLTeamLogo } from '../shared/NFLTeamLogo'

export interface TradesTabProps {
  consolidationTrades: ConsolidationTradeAnalysisResult | null
  isLoadingTrades: boolean
  selectedTeamId: number
  onScanTrades: (teamId: number) => void
}

export const TradesTab: React.FC<TradesTabProps> = ({
  consolidationTrades,
  isLoadingTrades,
  selectedTeamId,
  onScanTrades,
}) => {
  const [copiedPitchId, setCopiedPitchId] = useState<string | null>(null)

  return (
    <div>
      <div className="card" style={{ marginBottom: '24px' }}>
        <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <h3 className="card-title">🤝 2-for-1 Consolidation Trade Engine (8-Team Alpha Acquirer)</h3>
            <span className="pill amber">Championship Equity</span>
          </div>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => selectedTeamId && onScanTrades(selectedTeamId)}
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
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '6px' }}>
                      <NFLTeamLogo team={trade.target_alpha.pro_team} size={28} />
                      <h4 style={{ fontSize: '18px', fontWeight: 800, margin: 0, color: 'var(--text-primary)' }}>
                        Target: {trade.target_alpha.full_name} ({trade.target_alpha.position} - {trade.target_alpha.pro_team})
                      </h4>
                    </div>
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
                      <div key={p.player_id} className="trade-player-pill" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <NFLTeamLogo team={p.pro_team} size={22} />
                        <div style={{ flex: 1, minWidth: 0 }}>
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
                    <div className="trade-player-pill alpha" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <NFLTeamLogo team={trade.target_alpha.pro_team} size={24} />
                      <div style={{ flex: 1, minWidth: 0 }}>
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
                      <div className="trade-player-pill backfill" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <NFLTeamLogo team={trade.waiver_backfill.pro_team} size={22} />
                        <div style={{ flex: 1, minWidth: 0 }}>
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
  )
}
