import React from 'react'
import type { ScoringWeights, BacktestReport, LeagueSummaryResponse } from '../../types'

export interface SettingsTabProps {
  league: LeagueSummaryResponse | null
  leagueSizeSetting: number
  setLeagueSizeSetting: (size: number) => void
  weights: ScoringWeights
  onWeightChange: (key: keyof ScoringWeights, value: number) => void
  onSaveWeights: () => void
  onRunBacktesting: () => void
  tuningMessage: string | null
  backtest: BacktestReport | null
}

export const SettingsTab: React.FC<SettingsTabProps> = ({
  league,
  leagueSizeSetting,
  setLeagueSizeSetting,
  weights,
  onWeightChange,
  onSaveWeights,
  onRunBacktesting,
  tuningMessage,
  backtest,
}) => {
  return (
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
              onChange={(e) => onWeightChange('projection_weight', Number(e.target.value) / 100)}
            />
          </label>

          <label>
            <span>Opportunity / Volume Weight: {Math.round(weights.opportunity_weight * 100)}%</span>
            <input
              type="range"
              min="5"
              max="40"
              value={Math.round(weights.opportunity_weight * 100)}
              onChange={(e) => onWeightChange('opportunity_weight', Number(e.target.value) / 100)}
            />
          </label>

          <label>
            <span>Defensive Matchup Weight: {Math.round(weights.matchup_weight * 100)}%</span>
            <input
              type="range"
              min="5"
              max="40"
              value={Math.round(weights.matchup_weight * 100)}
              onChange={(e) => onWeightChange('matchup_weight', Number(e.target.value) / 100)}
            />
          </label>

          <label>
            <span>Game Environment / Implied Total: {Math.round(weights.environment_weight * 100)}%</span>
            <input
              type="range"
              min="0"
              max="25"
              value={Math.round(weights.environment_weight * 100)}
              onChange={(e) => onWeightChange('environment_weight', Number(e.target.value) / 100)}
            />
          </label>

          <label>
            <span>Health / Availability Discount: {Math.round(weights.health_weight * 100)}%</span>
            <input
              type="range"
              min="0"
              max="25"
              value={Math.round(weights.health_weight * 100)}
              onChange={(e) => onWeightChange('health_weight', Number(e.target.value) / 100)}
            />
          </label>

          <label>
            <span>Weather Conditions Weight: {Math.round(weights.weather_weight * 100)}%</span>
            <input
              type="range"
              min="0"
              max="15"
              value={Math.round(weights.weather_weight * 100)}
              onChange={(e) => onWeightChange('weather_weight', Number(e.target.value) / 100)}
            />
          </label>
        </div>

        <div style={{ marginTop: '20px', display: 'flex', gap: '12px' }}>
          <button className="btn btn-primary" onClick={onSaveWeights}>
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

        <button className="btn btn-secondary" onClick={onRunBacktesting}>
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
  )
}
