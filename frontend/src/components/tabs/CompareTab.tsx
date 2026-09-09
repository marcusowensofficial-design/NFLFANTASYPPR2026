import { useState, useMemo, useEffect } from 'react'
import type {
  PlayerDirectoryItem,
  LeagueSummaryResponse,
  OptimizedLineupResult,
  ComparisonResult,
  FactorScoreDetail,
  CloseCallPair,
  SlotAssignment,
  StartSitEvaluation,
  TeamSummary,
  PlayerMarketSentimentItem,
} from '../../types'
import { MatchupStarRating } from '../shared/MatchupStarRating'
import { renderWhyFactorItem } from '../shared/WhyHelpers'
import { Tooltip } from '../shared/Tooltip'
import { renderLineupVegasProps } from '../shared/VegasPropsHelper'
import { NFLTeamLogo } from '../shared/NFLTeamLogo'

export const getScoreColorClass = (score: number) => {
  if (score >= 80) return 'emerald'
  if (score >= 65) return 'cyan'
  if (score >= 50) return 'amber'
  return 'rose'
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

interface CompareTabProps {
  strategyMode: 'BALANCED' | 'CEILING' | 'FLOOR' | 'AUTO'
  onStrategyChange: (mode: 'BALANCED' | 'CEILING' | 'FLOOR' | 'AUTO') => void
  projectionSource: 'MODEL' | 'CONSENSUS' | 'FANTASYPROS' | 'SLEEPER' | 'ESPN'
  selectedTeamId: number
  league: LeagueSummaryResponse | null
  allPlayers: PlayerDirectoryItem[]
  lineup: OptimizedLineupResult | null
  compareIds: number[]
  setCompareIds: React.Dispatch<React.SetStateAction<number[]>>
  comparisonResult: ComparisonResult | null
  runComparison: (ids: number[], mode?: string, source?: string) => Promise<void>
  onClearComparison?: () => void
  onAutoLoadDilemma?: () => void
}

export const CompareTab: React.FC<CompareTabProps> = ({
  strategyMode,
  onStrategyChange,
  projectionSource,
  selectedTeamId,
  league,
  allPlayers,
  lineup,
  compareIds,
  setCompareIds,
  comparisonResult,
  runComparison,
  onClearComparison,
  onAutoLoadDilemma,
}) => {
  const [comparePosFilter, setComparePosFilter] = useState<string>('ALL')
  const [compareScope, setCompareScope] = useState<'roster' | 'all'>('roster')
  const [expandedCardFormula, setExpandedCardFormula] = useState<{
    [playerId: number]: 'projection' | 'opportunity' | 'matchup' | 'environment' | 'all' | null
  }>({})
  const [marketSentiments, setMarketSentiments] = useState<Record<number, PlayerMarketSentimentItem>>({})

  useEffect(() => {
    if (!comparisonResult?.players?.length) return
    const fetchSentiments = async () => {
      const results: Record<number, PlayerMarketSentimentItem> = {}
      await Promise.all(
        comparisonResult.players.map(async (p) => {
          try {
            const res = await fetch(`/api/analysis/market-sentiment/player/${p.player_id}`)
            if (res.ok) {
              results[p.player_id] = await res.json()
            }
          } catch (err) {
            // Ignore fetch error
          }
        })
      )
      setMarketSentiments(results)
    }
    fetchSentiments()
  }, [comparisonResult])

  const toggleFactorFormula = (
    playerId: number,
    factor: 'projection' | 'opportunity' | 'matchup' | 'environment' | 'all'
  ) => {
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

  // Focused team metadata
  const focusedTeamName = league?.teams.find((t: TeamSummary) => t.id === selectedTeamId)?.name || 'My Team'

  // Filter players for comparator dropdowns based on position filter
  const filteredPlayersForDropdown = allPlayers.filter((p: PlayerDirectoryItem) => {
    if (comparePosFilter === 'ALL') return true
    if (comparePosFilter === 'FLEX') return ['RB', 'WR', 'TE'].includes(p.position)
    return p.position === comparePosFilter
  })

  // Selected team's roster
  const currentTeamPlayers = filteredPlayersForDropdown.filter((p: PlayerDirectoryItem) => p.team_id === selectedTeamId)
  const myStarters = currentTeamPlayers.filter((p: PlayerDirectoryItem) => p.is_starter)
  const myBench = currentTeamPlayers.filter((p: PlayerDirectoryItem) => !p.is_starter)
  const freeAgents = filteredPlayersForDropdown.filter((p: PlayerDirectoryItem) => p.is_free_agent)
  const otherTeams = filteredPlayersForDropdown.filter(
    (p: PlayerDirectoryItem) => p.team_id !== selectedTeamId && !p.is_free_agent
  )

  // Candidate Player Lookups
  const cand1 = compareIds[0] ? allPlayers.find((p) => p.id === compareIds[0]) : null
  const cand2 = compareIds[1] ? allPlayers.find((p) => p.id === compareIds[1]) : null

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
    lineup.close_calls.forEach((cc: CloseCallPair, idx: number) => {
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
    const starterPlayers = lineup.starters.map((s: SlotAssignment) => s.recommended_player)
    lineup.bench.forEach((b: StartSitEvaluation) => {
      const match = starterPlayers.find((s: StartSitEvaluation) => s.position === b.position)
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
    runComparison(ids, strategyMode, projectionSource)
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
          runComparison(newIds, strategyMode, projectionSource)
        }
      }
    }
  }

  const handlePlayerSelect = (index: number, newId: number) => {
    if (!newId) return
    const next = [...compareIds]
    next[index] = newId
    setCompareIds(next)
    const valid = next.filter(Boolean)
    if (valid.length >= 2) {
      runComparison(valid, strategyMode, projectionSource)
    }
  }

  const handleClearSlot = (index: number) => {
    const next = compareIds.filter((_, i) => i !== index)
    setCompareIds(next)
    if (next.length >= 2) {
      runComparison(next, strategyMode, projectionSource)
    }
  }

  const handleResetMatchup = () => {
    if (onClearComparison) {
      onClearComparison()
    } else {
      setCompareIds([])
    }
  }

  const handleAutoLoad = () => {
    if (onAutoLoadDilemma) {
      onAutoLoadDilemma()
    } else if (rosterDilemmas.length > 0) {
      handleSelectDilemma(rosterDilemmas[0].starterId, rosterDilemmas[0].benchId)
    }
  }

  const handleSwapPlayers = () => {
    if (compareIds.length >= 2) {
      const next = [compareIds[1], compareIds[0], ...compareIds.slice(2)]
      setCompareIds(next)
      runComparison(next, strategyMode, projectionSource)
    }
  }

  const handleAddComparePlayer = () => {
    if (compareIds.length >= 4) return
    const pool = compareScope === 'roster' ? currentTeamPlayers : allPlayers
    const candidate = pool.find((p) => !compareIds.includes(p.id))
    if (candidate) {
      const next = [...compareIds, candidate.id]
      setCompareIds(next)
      runComparison(next, strategyMode, projectionSource)
    }
  }

  const handleRemoveComparePlayer = (index: number) => {
    if (compareIds.length <= 2) return
    const next = compareIds.filter((_, i) => i !== index)
    setCompareIds(next)
    runComparison(next, strategyMode, projectionSource)
  }

  return (
    <div className="card">
      <div className="card-header">
        <h3 className="card-title">⚖️ Head-to-Head Start/Sit Comparator (2-4 Players)</h3>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span className="pill cyan">Transparent Formula</span>
          <span className="pill emerald" style={{ fontSize: '11px' }}>
            {projectionSource === 'MODEL' ? '🤖 Model Projections' : projectionSource === 'CONSENSUS' ? '⭐ Consensus' : projectionSource === 'FANTASYPROS' ? '🌐 FP Consensus' : projectionSource === 'SLEEPER' ? '📱 Sleeper (RotoWire)' : '🏈 ESPN Direct'}
          </span>
        </div>
      </div>

      {/* Strategy Mode Switcher Bar in Comparator */}
      <div className="strategy-selector-bar" style={{ marginBottom: '16px' }}>
        <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)' }}>
          Evaluate Under Strategy:
        </span>
        <div className="strategy-selector">
          <button
            className={`strategy-pill-btn balanced ${strategyMode === 'BALANCED' ? 'active' : ''}`}
            onClick={() => onStrategyChange('BALANCED')}
          >
            🎯 Balanced
          </button>
          <button
            className={`strategy-pill-btn ceiling ${strategyMode === 'CEILING' ? 'active' : ''}`}
            onClick={() => onStrategyChange('CEILING')}
          >
            🚀 Ceiling (Boom)
          </button>
          <button
            className={`strategy-pill-btn floor ${strategyMode === 'FLOOR' ? 'active' : ''}`}
            onClick={() => onStrategyChange('FLOOR')}
          >
            🛡️ Floor (Safe)
          </button>
        </div>
      </div>

      <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '16px' }}>
        Select two candidates from your roster to inspect deep statistical calibrations, sportsbook prop markets, Boris Chen tiers, and factor-by-factor score drivers.
      </p>

      {/* Top Action & Control Bar */}
      <div className="duel-action-bar">
        <div className="duel-action-group">
          <button
            className="btn btn-sm btn-primary"
            onClick={handleAutoLoad}
            title="Auto-load your team's closest starter vs bench battle"
          >
            ⚡ Auto-Load Closest Dilemma
          </button>
          <button
            className="btn btn-sm btn-secondary"
            onClick={handleResetMatchup}
            title="Clear current selection and choose fresh players"
          >
            ↺ Reset / Pick New Matchup
          </button>
        </div>

        {/* Scope Mode Toggle Bar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <div className="scope-toggle-group">
            <button
              className={`scope-toggle-btn ${compareScope === 'roster' ? 'active' : ''}`}
              onClick={() => handleScopeChange('roster')}
            >
              🏠 Team Roster
            </button>
            <button
              className={`scope-toggle-btn ${compareScope === 'all' ? 'active' : ''}`}
              onClick={() => handleScopeChange('all')}
            >
              🌐 League Pool
            </button>
          </div>

          <div className="scope-team-indicator">
            <span style={{ color: 'var(--text-muted)' }}>Focus:</span>
            <strong style={{ color: 'var(--text-primary)' }}>{focusedTeamName}</strong>
            <span className="pill cyan" style={{ padding: '2px 8px', fontSize: '11px' }}>
              {compareScope === 'roster' ? `${currentTeamPlayers.length} Roster` : `${allPlayers.length} Pool`}
            </span>
          </div>
        </div>
      </div>

      {/* Position Filter Tabs */}
      <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
        <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Filter Position:
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

      {/* Head-to-Head Duel Arena */}
      <div className="duel-arena">
        {/* Candidate #1 Card */}
        <div className={`duel-card candidate-1 ${!cand1 ? 'empty' : ''}`}>
          <div className="duel-card-header">
            <span className="duel-candidate-label">
              👤 Candidate #1 {cand1?.is_starter ? '(Starter)' : '(Primary)'}
            </span>
            {cand1 && (
              <button
                className="duel-change-btn"
                onClick={() => handleClearSlot(0)}
                title="Clear Candidate #1"
              >
                ✕ Clear
              </button>
            )}
          </div>

          {cand1 ? (
            <div className="duel-player-info">
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <NFLTeamLogo team={cand1.pro_team} size={34} />
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div className="duel-player-name">{cand1.full_name}</div>
                  <div className="duel-meta-row" style={{ marginTop: '3px' }}>
                    <span className="pill cyan" style={{ fontSize: '11px', padding: '2px 7px' }}>
                      {cand1.position}
                    </span>
                    <span className="pill zinc" style={{ fontSize: '11px', padding: '2px 7px' }}>
                      {cand1.pro_team}
                    </span>
                    <span className={`pill ${cand1.is_starter ? 'emerald' : 'amber'}`} style={{ fontSize: '11px', padding: '2px 7px' }}>
                      {cand1.is_starter ? '⭐ Starter' : '🔄 Bench'}
                    </span>
                    <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)', marginLeft: 'auto' }}>
                      {cand1.projected_points} pts
                    </span>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '16px 8px' }}>
              <div style={{ fontSize: '28px', marginBottom: '6px' }}>👤</div>
              <div style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '4px' }}>
                Select Player 1
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '14px' }}>
                Pick a starter or key candidate from {focusedTeamName}
              </div>
            </div>
          )}

          {/* Candidate 1 Select Dropdown */}
          <select
            className="select-dropdown"
            style={{ width: '100%', padding: '9px 12px', fontSize: '13px' }}
            value={compareIds[0] || ''}
            onChange={(e) => handlePlayerSelect(0, Number(e.target.value))}
          >
            <option value="">{cand1 ? '⇄ Switch Player 1...' : '👉 Pick Player 1 to Compare...'}</option>
            {myStarters.length > 0 && (
              <optgroup label={`⭐ ${focusedTeamName} Starters (${myStarters.length})`}>
                {myStarters.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.full_name} ({p.position} - {p.pro_team}) • {p.projected_points} pts [Starter]
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
              <optgroup label={`🟢 Available Free Agents (${freeAgents.length})`}>
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

        {/* Center VS Column */}
        <div className="duel-vs-col">
          <div className="duel-vs-circle">VS</div>
          <button
            className="duel-swap-btn"
            onClick={handleSwapPlayers}
            disabled={compareIds.length < 2}
            title="Swap Player 1 and Player 2"
          >
            ⇄ Swap
          </button>
        </div>

        {/* Candidate #2 Card */}
        <div className={`duel-card candidate-2 ${!cand2 ? 'empty' : ''}`}>
          <div className="duel-card-header">
            <span className="duel-candidate-label">
              ⚔️ Candidate #2 {cand2?.is_starter ? '(Starter)' : '(Challenger)'}
            </span>
            {cand2 && (
              <button
                className="duel-change-btn"
                onClick={() => handleClearSlot(1)}
                title="Clear Candidate #2"
              >
                ✕ Clear
              </button>
            )}
          </div>

          {cand2 ? (
            <div className="duel-player-info">
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <NFLTeamLogo team={cand2.pro_team} size={34} />
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div className="duel-player-name">{cand2.full_name}</div>
                  <div className="duel-meta-row" style={{ marginTop: '3px' }}>
                    <span className="pill purple" style={{ fontSize: '11px', padding: '2px 7px' }}>
                      {cand2.position}
                    </span>
                    <span className="pill zinc" style={{ fontSize: '11px', padding: '2px 7px' }}>
                      {cand2.pro_team}
                    </span>
                    <span className={`pill ${cand2.is_starter ? 'emerald' : 'amber'}`} style={{ fontSize: '11px', padding: '2px 7px' }}>
                      {cand2.is_starter ? '⭐ Starter' : '🔄 Bench'}
                    </span>
                    <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)', marginLeft: 'auto' }}>
                      {cand2.projected_points} pts
                    </span>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '16px 8px' }}>
              <div style={{ fontSize: '28px', marginBottom: '6px' }}>⚔️</div>
              <div style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '4px' }}>
                Select Player 2
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '14px' }}>
                {cand1 ? `Pick a challenger to compare against ${cand1.full_name}` : 'Pick a bench player or challenger'}
              </div>
            </div>
          )}

          {/* Candidate 2 Select Dropdown */}
          <select
            className="select-dropdown"
            style={{ width: '100%', padding: '9px 12px', fontSize: '13px' }}
            value={compareIds[1] || ''}
            onChange={(e) => handlePlayerSelect(1, Number(e.target.value))}
          >
            <option value="">{cand2 ? '⇄ Switch Player 2...' : '👉 Pick Player 2 to Compare...'}</option>
            {/* Smart Prioritization: matching position or flex challengers from bench */}
            {cand1 && myBench.filter((p) => p.id !== cand1.id && (p.position === cand1.position || (['RB', 'WR', 'TE'].includes(cand1.position) && ['RB', 'WR', 'TE'].includes(p.position)))).length > 0 && (
              <optgroup label={`🎯 Recommended Bench Challengers (${myBench.filter((p) => p.id !== cand1.id && (p.position === cand1.position || (['RB', 'WR', 'TE'].includes(cand1.position) && ['RB', 'WR', 'TE'].includes(p.position)))).length})`}>
                {myBench.filter((p) => p.id !== cand1.id && (p.position === cand1.position || (['RB', 'WR', 'TE'].includes(cand1.position) && ['RB', 'WR', 'TE'].includes(p.position)))).map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.full_name} ({p.position} - {p.pro_team}) • {p.projected_points} pts [Bench]
                  </option>
                ))}
              </optgroup>
            )}
            {myStarters.filter((p) => p.id !== cand1?.id).length > 0 && (
              <optgroup label={`⭐ ${focusedTeamName} Starters`}>
                {myStarters.filter((p) => p.id !== cand1?.id).map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.full_name} ({p.position} - {p.pro_team}) • {p.projected_points} pts [Starter]
                  </option>
                ))}
              </optgroup>
            )}
            {myBench.filter((p) => p.id !== cand1?.id).length > 0 && (
              <optgroup label={`🔄 ${focusedTeamName} Bench`}>
                {myBench.filter((p) => p.id !== cand1?.id).map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.full_name} ({p.position} - {p.pro_team}) • {p.projected_points} pts [Bench]
                  </option>
                ))}
              </optgroup>
            )}
            {compareScope === 'all' && freeAgents.length > 0 && (
              <optgroup label={`🟢 Available Free Agents (${freeAgents.length})`}>
                {freeAgents.filter((p) => p.id !== cand1?.id).map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.full_name} ({p.position} - {p.pro_team}) • {p.projected_points} pts [Free Agent]
                  </option>
                ))}
              </optgroup>
            )}
            {compareScope === 'all' && otherTeams.length > 0 && (
              <optgroup label={`👥 Other League Rosters (${otherTeams.length})`}>
                {otherTeams.filter((p) => p.id !== cand1?.id).map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.full_name} ({p.position} - {p.pro_team}) • {p.projected_points} pts ({p.team_abbrev || 'League'})
                  </option>
                ))}
              </optgroup>
            )}
          </select>
        </div>
      </div>

      {/* 3rd/4th Candidate Expanders if active */}
      {compareIds.length >= 3 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', marginBottom: '20px' }}>
          {compareIds.slice(2).map((pid, offsetIdx) => {
            const idx = offsetIdx + 2
            const p = allPlayers.find((item) => item.id === pid)
            return (
              <div key={idx} className="duel-card" style={{ borderColor: 'rgba(255, 255, 255, 0.12)' }}>
                <div className="duel-card-header">
                  <span className="duel-candidate-label" style={{ color: 'var(--accent-amber)' }}>
                    Candidate #{idx + 1}
                  </span>
                  <button className="duel-change-btn" onClick={() => handleRemoveComparePlayer(idx)}>
                    ✕ Remove
                  </button>
                </div>
                {p && (
                  <div className="duel-player-info">
                    <div className="duel-player-name" style={{ fontSize: '16px' }}>{p.full_name}</div>
                    <div className="duel-meta-row">
                      <span className="pill cyan" style={{ fontSize: '10px', padding: '1px 6px' }}>{p.position}</span>
                      <span className="pill zinc" style={{ fontSize: '10px', padding: '1px 6px' }}>{p.pro_team}</span>
                      <span style={{ fontSize: '12px', fontWeight: 700, marginLeft: 'auto' }}>{p.projected_points} pts</span>
                    </div>
                  </div>
                )}
                <select
                  className="select-dropdown"
                  style={{ width: '100%', padding: '7px 10px', fontSize: '12px' }}
                  value={pid}
                  onChange={(e) => handlePlayerSelect(idx, Number(e.target.value))}
                >
                  {currentTeamPlayers.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.full_name} ({item.position}) • {item.projected_points} pts
                    </option>
                  ))}
                </select>
              </div>
            )
          })}
        </div>
      )}

      {/* Multi-Candidate Expand Button */}
      {compareIds.length >= 2 && compareIds.length < 4 && (
        <div style={{ marginBottom: '18px' }}>
          <button
            className="btn btn-secondary btn-sm"
            onClick={handleAddComparePlayer}
            style={{ borderColor: 'var(--accent-purple)' }}
          >
            ➕ Add Another Candidate to Compare ({compareIds.length + 1} of 4)
          </button>
        </div>
      )}

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

      {/* Guidance Box when fewer than 2 players are selected */}
      {compareIds.length < 2 && (
        <div className="duel-guide-box">
          <div className="duel-guide-icon">⚖️</div>
          <div className="duel-guide-title">
            {compareIds.length === 0
              ? 'Start/Sit Algorithmic Comparison Arena'
              : `Candidate #1 (${cand1?.full_name || 'Player 1'}) Ready!`}
          </div>
          <div className="duel-guide-desc">
            {compareIds.length === 0
              ? `Select two players from ${focusedTeamName} above, or click any 1-Click Roster Dilemma to run a full institutional comparison.`
              : `Now pick Candidate #2 (Challenger) above or click one of the 1-Click Roster Dilemmas to compare against ${cand1?.full_name}.`}
          </div>

          <div className="duel-guide-features">
            <div className="duel-guide-feature-item">
              <div className="duel-guide-feature-title">🎯 Algorithmic Projections</div>
              <div className="duel-guide-feature-text">Model calibrations blended with FantasyPros, Sleeper, and ESPN consensus.</div>
            </div>
            <div className="duel-guide-feature-item">
              <div className="duel-guide-feature-title">🚜 Opportunity Volume</div>
              <div className="duel-guide-feature-text">Snap share, target shares, red-zone touches, and route participation indexes.</div>
            </div>
            <div className="duel-guide-feature-item">
              <div className="duel-guide-feature-title">🛡️ Defense-vs-Position</div>
              <div className="duel-guide-feature-text">Full DvP star ratings & positional defensive rankings for Week 1.</div>
            </div>
            <div className="duel-guide-feature-item">
              <div className="duel-guide-feature-title">🎲 Vegas Sharp Props</div>
              <div className="duel-guide-feature-text">Sportsbook reception lines, anytime touchdown probabilities, and implied team totals.</div>
            </div>
          </div>
        </div>
      )}


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
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <NFLTeamLogo team={p.pro_team} size={32} />
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div className="comp-player-name">{p.full_name}</div>
                  <div className="comp-player-meta" style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap', marginTop: '3px' }}>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                      <span>{p.position} • {p.pro_team} • {p.is_home ? 'vs' : '@'}</span>
                      <NFLTeamLogo team={p.opponent} size={16} />
                      <span>{p.opponent}</span>
                    </span>
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
            </div>
          </div>

              <div className="comp-score-row">
                <div>
                  <Tooltip term="CEILING_FLOOR" title="StartScore (Composite)">
                    <div className="metric-label">StartScore</div>
                  </Tooltip>
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

              {/* Vegas Props & Boris Chen Tier Section */}
              <div style={{
                margin: '10px 0 14px 0',
                padding: '9px 12px',
                background: 'rgba(15, 23, 42, 0.75)',
                border: '1px solid rgba(245, 158, 11, 0.25)',
                borderRadius: '8px',
                display: 'flex',
                flexDirection: 'column',
                gap: '6px',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Tooltip term="VEGAS_PROPS" title="Vegas Sportsbook Consensus">
                    <span style={{ fontSize: '11px', fontWeight: 700, color: '#fbbf24', textTransform: 'uppercase', letterSpacing: '0.04em', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      🎲 Vegas Sharp Lines
                    </span>
                  </Tooltip>
                  {p.boris_chen_tier && (
                    <Tooltip term="BORIS_TIER" title={`Boris Chen GMM Tier ${p.boris_chen_tier}`}>
                      <span className={`boris-tier-badge tier-${p.boris_chen_tier}`} style={{ fontSize: '10px' }}>
                        <span>💎</span> {p.boris_chen_tier_label || `Tier ${p.boris_chen_tier}`}
                      </span>
                    </Tooltip>
                  )}
                </div>
                {renderLineupVegasProps(p)}
              </div>

              {/* Prediction Market Intelligence Strip (Polymarket) */}
              {marketSentiments[p.player_id] && (
                <div
                  style={{
                    margin: '10px 0 14px 0',
                    padding: '10px 12px',
                    background: 'rgba(139, 92, 246, 0.08)',
                    border: '1px solid rgba(139, 92, 246, 0.3)',
                    borderRadius: '8px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '6px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span
                      style={{
                        fontSize: '11px',
                        fontWeight: 800,
                        color: 'var(--accent-purple, #a855f7)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                        textTransform: 'uppercase',
                        letterSpacing: '0.04em',
                      }}
                    >
                      <span>📊</span> Polymarket Prediction Odds
                    </span>
                    <span
                      className={`pill ${
                        marketSentiments[p.player_id].starter_confidence >= 0.75
                          ? 'emerald'
                          : marketSentiments[p.player_id].starter_confidence >= 0.5
                          ? 'amber'
                          : 'rose'
                      }`}
                      style={{ fontSize: '10px', fontWeight: 800 }}
                    >
                      {Math.round(marketSentiments[p.player_id].starter_confidence * 100)}% Starter Confidence
                    </span>
                  </div>

                  <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {marketSentiments[p.player_id].market_headline}
                  </div>

                  {marketSentiments[p.player_id].tactical_advice && (
                    <div
                      style={{
                        fontSize: '11.5px',
                        color: 'var(--text-secondary)',
                        borderTop: '1px solid rgba(255, 255, 255, 0.06)',
                        paddingTop: '6px',
                      }}
                    >
                      💡 <strong>PPR Tactical Tip:</strong> {marketSentiments[p.player_id].tactical_advice}
                    </div>
                  )}
                </div>
              )}

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
  )
}
