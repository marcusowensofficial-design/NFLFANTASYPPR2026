import React, { useMemo, useState, useEffect } from 'react'
import type {
  OptimizedLineupResult,
  LeagueSummaryResponse,
  StartSitEvaluation,
  SlotAssignment,
  InactiveAlertItem,
  PlayerMarketSentimentItem,
} from '../../types'
import { isPlayerDoubtfulOrInjured } from '../../types'
import { MatchupStarRating } from '../shared/MatchupStarRating'
import { InjuryStatusPill } from '../shared/InjuryStatusPill'
import { MatchupRatingKey } from '../shared/MatchupRatingKey'
import { InstitutionalStatCard } from '../shared/InstitutionalStatCard'
import { renderWhyFactorItem } from '../shared/WhyHelpers'
import { Tooltip } from '../shared/Tooltip'
import { renderLineupVegasProps } from '../shared/VegasPropsHelper'
import { getScoreColorClass } from './CompareTab'
import { NFLTeamLogo } from '../shared/NFLTeamLogo'
import { formatToMDT } from '../../utils/dateUtils'

interface LineupTabProps {
  projectionSource: 'MODEL' | 'CONSENSUS' | 'FANTASYPROS' | 'SLEEPER' | 'ESPN'
  onProjectionSourceChange: (source: 'MODEL' | 'CONSENSUS' | 'FANTASYPROS' | 'SLEEPER' | 'ESPN') => void
  strategyMode: 'BALANCED' | 'CEILING' | 'FLOOR' | 'AUTO'
  onStrategyChange: (mode: 'BALANCED' | 'CEILING' | 'FLOOR' | 'AUTO') => void
  lineup: OptimizedLineupResult | null
  league: LeagueSummaryResponse | null
  lineupViewMode: 'split' | 'unified'
  setLineupViewMode: (mode: 'split' | 'unified') => void
  showMatchupKey: boolean
  setShowMatchupKey: (show: boolean) => void
  expandedWhy: number | null
  setExpandedWhy: (id: number | null) => void
  expandedStatsPlayerId: number | null
  setExpandedStatsPlayerId: (id: number | null) => void
  customSubstitutions: { [slotIdx: number]: StartSitEvaluation }
  setCustomSubstitutions: React.Dispatch<React.SetStateAction<{ [slotIdx: number]: StartSitEvaluation }>>
  activeSwapSlotIndex: number | null
  setActiveSwapSlotIndex: (idx: number | null) => void
  onOpenPushModal: () => void
  onOpenShareModal?: () => void
  isPushing: boolean
  onCompareStarterWithBench: (p: StartSitEvaluation) => void
  onCompareBenchWithStarter: (b: StartSitEvaluation) => void
  onReviewCloseCall: (starterId: number, benchId: number) => void
  inactivesAlerts?: InactiveAlertItem[]
}

export const LineupTab: React.FC<LineupTabProps> = ({
  projectionSource,
  onProjectionSourceChange,
  strategyMode,
  onStrategyChange,
  lineup,
  league,
  lineupViewMode,
  setLineupViewMode,
  showMatchupKey,
  setShowMatchupKey,
  expandedWhy,
  setExpandedWhy,
  expandedStatsPlayerId,
  setExpandedStatsPlayerId,
  customSubstitutions,
  setCustomSubstitutions,
  activeSwapSlotIndex,
  setActiveSwapSlotIndex,
  onOpenPushModal,
  onOpenShareModal,
  isPushing,
  onCompareStarterWithBench,
  onCompareBenchWithStarter,
  onReviewCloseCall,
  inactivesAlerts = [],
}) => {
  // Calculate effective starters and bench considering manual user substitutions
  const {
    effectiveStarters,
    effectiveBench,
    customGainVsOptimal,
    hasCustomSwaps,
    hasRevertibleSwaps,
    currentLineupProjectedTotal,
  } = useMemo(() => {
    if (!lineup) {
      return {
        effectiveStarters: [],
        effectiveBench: [],
        customGainVsOptimal: 0,
        hasCustomSwaps: false,
        hasRevertibleSwaps: false,
        currentLineupProjectedTotal: 0,
      }
    }

    const substitutedStarterOriginals: StartSitEvaluation[] = []
    const substitutedBenchPlayerIds: number[] = []

    const getPlayerScore = (p: StartSitEvaluation) => {
      if (p.effective_points !== undefined && (p.effective_points > 0 || p.is_final)) {
        return p.effective_points
      }
      if (p.actual_points !== undefined && p.actual_points > 0) {
        return p.actual_points
      }
      return p.projected_points
    }

    const starters = lineup.starters.map((slot: SlotAssignment, idx: number) => {
      if (customSubstitutions[idx]) {
        const benchReplacement = customSubstitutions[idx]
        substitutedStarterOriginals.push(slot.recommended_player)
        substitutedBenchPlayerIds.push(benchReplacement.player_id)
        const starterPts = getPlayerScore(slot.recommended_player)
        const benchPts = getPlayerScore(benchReplacement)
        return {
          ...slot,
          is_custom_swap: true,
          original_recommended: slot.recommended_player,
          recommended_player: benchReplacement,
          net_projected_delta:
            Math.round((benchPts - (slot.current_starter ? getPlayerScore(slot.current_starter) : starterPts)) * 10) / 10,
        }
      }
      return {
        ...slot,
        is_custom_swap: false,
        original_recommended: slot.recommended_player,
      }
    })

    let bench = lineup.bench.filter((b: StartSitEvaluation) => !substitutedBenchPlayerIds.includes(b.player_id))
    bench = [...bench, ...substitutedStarterOriginals]

    const optimalTotal = lineup.starters.reduce(
      (sum: number, s: SlotAssignment) => sum + getPlayerScore(s.recommended_player),
      0
    )
    const currentTotal = starters.reduce(
      (sum: number, s: any) => sum + getPlayerScore(s.recommended_player),
      0
    )
    const actualTotal = starters.reduce(
      (sum: number, s: any) => sum + (s.recommended_player.actual_points || 0),
      0
    )
    const customGain = Math.round((currentTotal - optimalTotal) * 10) / 10

    const hasRevertible = starters.some(
      (s: any) => s.is_custom_swap && !isPlayerDoubtfulOrInjured(s.original_recommended)
    )

    return {
      effectiveStarters: starters,
      effectiveBench: bench,
      customGainVsOptimal: customGain,
      hasCustomSwaps: Object.keys(customSubstitutions).length > 0,
      hasRevertibleSwaps: hasRevertible,
      currentLineupProjectedTotal: Math.round(currentTotal * 10) / 10,
      currentLineupActualTotal: Math.round(actualTotal * 10) / 10,
      currentLineupEffectiveTotal: Math.round(currentTotal * 10) / 10,
    }
  }, [lineup, customSubstitutions])

  const [marketBuzz, setMarketBuzz] = useState<PlayerMarketSentimentItem[]>([])

  useEffect(() => {
    const fetchMarketBuzz = async () => {
      try {
        const week = league?.current_week || 1
        const res = await fetch(`/api/analysis/market-sentiment/buzz?week=${week}`)
        if (res.ok) {
          setMarketBuzz(await res.json())
        }
      } catch (err) {
        // Ignore fetch error
      }
    }
    fetchMarketBuzz()
  }, [league?.current_week])

  const marketSentimentMap = useMemo(() => {
    const map = new Map<number, PlayerMarketSentimentItem>()
    for (const item of marketBuzz) {
      map.set(item.player_id, item)
    }
    return map
  }, [marketBuzz])

  // Identify starters with critical market warnings (TNF Flex trap, low starter confidence, high decoy risk)
  const marketAlerts = useMemo(() => {
    if (!effectiveStarters.length) return []
    const alerts: Array<{
      player: StartSitEvaluation
      slotName: string
      isFlexTrap: boolean
      isControversy: boolean
      isHighDecoy: boolean
      headline: string
      advice: string
    }> = []

    for (const s of effectiveStarters) {
      const p = s.recommended_player
      const sent = marketSentimentMap.get(p.player_id)
      if (!sent) continue

      const isFlexTrap = s.slot_name === 'FLEX' && sent.is_thursday_kickoff
      const isControversy = sent.has_starter_controversy && sent.starter_confidence < 0.75
      const isHighDecoy = sent.decoy_risk === 'HIGH'

      if (isFlexTrap || isControversy || isHighDecoy) {
        alerts.push({
          player: p,
          slotName: s.slot_name,
          isFlexTrap,
          isControversy,
          isHighDecoy,
          headline: sent.market_headline,
          advice: sent.tactical_advice,
        })
      }
    }
    return alerts
  }, [effectiveStarters, marketSentimentMap])

  const getEligibleBenchForSlot = (slotName: string, benchList: StartSitEvaluation[]) => {
    // Exclude doubtful or injured players so managers aren't offered unplayable assets
    const playableBench = benchList.filter((b) => !isPlayerDoubtfulOrInjured(b))
    if (slotName === 'QB') return playableBench.filter((b) => b.position === 'QB')
    if (slotName === 'RB') return playableBench.filter((b) => b.position === 'RB')
    if (slotName === 'WR') return playableBench.filter((b) => b.position === 'WR')
    if (slotName === 'TE') return playableBench.filter((b) => b.position === 'TE')
    if (slotName === 'FLEX') return playableBench.filter((b) => ['RB', 'WR', 'TE'].includes(b.position))
    if (slotName === 'KICKER' || slotName === 'K') return playableBench.filter((b) => ['K', 'PK'].includes(b.position))
    if (slotName === 'DEFENSE' || slotName === 'DST' || slotName === 'D/ST')
      return playableBench.filter((b) => ['DST', 'D/ST', 'DEF'].includes(b.position))
    return playableBench
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
    // Only reset substitutions where the original recommended player is NOT doubtful or injured
    setCustomSubstitutions((prev) => {
      const next: Record<number, StartSitEvaluation> = {}
      for (const [slotIdxStr, benchPlayer] of Object.entries(prev)) {
        const slotIdx = Number(slotIdxStr)
        const original = lineup?.starters[slotIdx]?.recommended_player
        if (original && isPlayerDoubtfulOrInjured(original)) {
          // Preserve injury substitution
          next[slotIdx] = benchPlayer
        }
      }
      return next
    })
    setActiveSwapSlotIndex(null)
  }

  const renderMatchupGradePill = (grade: string) => {
    switch (grade) {
      case 'ELITE':
        return (
          <span
            className="pill emerald"
            style={{
              fontWeight: 800,
              fontSize: '10.5px',
              padding: '2px 8px',
              background: 'rgba(16, 185, 129, 0.25)',
              border: '1px solid rgba(16, 185, 129, 0.7)',
              boxShadow: '0 0 10px rgba(16, 185, 129, 0.3)',
              color: '#34d399',
            }}
          >
            🚀 ELITE
          </span>
        )
      case 'FAVORABLE':
        return (
          <span className="pill emerald" style={{ fontWeight: 700, fontSize: '10.5px' }}>
            FAVORABLE
          </span>
        )
      case 'NEUTRAL':
        return (
          <span className="pill cyan" style={{ fontWeight: 600, fontSize: '10.5px' }}>
            NEUTRAL
          </span>
        )
      case 'TOUGH':
        return (
          <span className="pill amber" style={{ fontWeight: 700, fontSize: '10.5px' }}>
            TOUGH
          </span>
        )
      case 'BRUTAL':
        return (
          <span
            className="pill rose"
            style={{
              fontWeight: 800,
              fontSize: '10.5px',
              padding: '2px 8px',
              background: 'rgba(244, 63, 94, 0.25)',
              border: '1px solid rgba(244, 63, 94, 0.7)',
              color: '#fb7185',
            }}
          >
            🛑 BRUTAL
          </span>
        )
      default:
        return <span className="pill cyan" style={{ fontSize: '10.5px' }}>{grade}</span>
    }
  }

  const renderPlayerPointsBadge = (p: StartSitEvaluation) => {
    const isFinal = p.is_final || p.game_status === 'FINAL'
    const isLive = p.game_status === 'LIVE' || (p.lineup_locked && !isFinal)
    const hasActual = (p.actual_points !== undefined && p.actual_points > 0) || isFinal

    if (isFinal || (hasActual && !isLive)) {
      return (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontWeight: 800, fontSize: '13.5px', color: '#34d399', fontFamily: 'var(--font-mono)' }}>
              {(p.actual_points ?? 0).toFixed(1)} pts
            </span>
            <span
              className="pill emerald"
              style={{ fontSize: '9.5px', padding: '1px 5px', fontWeight: 800, letterSpacing: '0.5px' }}
              title="Official Final Score: Game is completed"
            >
              FINAL
            </span>
          </div>
          <div style={{ fontSize: '10.5px', color: 'var(--text-muted)', marginTop: '2px' }}>
            Proj: {p.projected_points.toFixed(1)}
          </div>
        </div>
      )
    }

    if (isLive) {
      return (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontWeight: 800, fontSize: '13.5px', color: '#fbbf24', fontFamily: 'var(--font-mono)' }}>
              {(p.actual_points ?? 0).toFixed(1)} pts
            </span>
            <span
              className="pill amber"
              style={{ fontSize: '9.5px', padding: '1px 5px', fontWeight: 800, letterSpacing: '0.5px' }}
              title="Game In-Progress: Live actual fantasy points"
            >
              ⚡ LIVE
            </span>
          </div>
          <div style={{ fontSize: '10.5px', color: 'var(--text-muted)', marginTop: '2px' }}>
            Proj: {p.projected_points.toFixed(1)}
          </div>
        </div>
      )
    }

    return (
      <div>
        <span style={{ fontWeight: 600, fontSize: '13px' }}>
          {p.projected_points.toFixed(1)} pts
        </span>
        <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
          Proj
        </div>
      </div>
    )
  }

  return (
    <div>
      {/* Game-Day Pre-Kickoff Inactive Sweeper Banner */}
      {inactivesAlerts.length > 0 && (
        <div
          style={{
            background: 'rgba(239, 68, 68, 0.15)',
            border: '2px solid rgba(239, 68, 68, 0.6)',
            borderRadius: '12px',
            padding: '16px 20px',
            marginBottom: '20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '24px' }}>🚨</span>
            <div>
              <strong style={{ color: '#f87171', fontSize: '15px' }}>
                Game-Day Inactive Alert ({inactivesAlerts.length} starter{inactivesAlerts.length > 1 ? 's' : ''} ruled OUT/Questionable):
              </strong>
              <div style={{ fontSize: '12.5px', color: '#fca5a5', marginTop: '2px' }}>
                Immediate swap required before kickoff to prevent taking a zero.
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '4px' }}>
            {inactivesAlerts.map((alert, idx) => (
              <span
                key={idx}
                className="pill rose"
                style={{ fontSize: '12px', padding: '4px 10px', fontWeight: 700 }}
              >
                ⚠️ {alert.full_name} ({alert.slot_name}) - {alert.injury_status}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Week 1 Kickoff & Prediction Market Advisory Banner */}
      {marketAlerts.length > 0 && (
        <div
          style={{
            background: 'rgba(139, 92, 246, 0.12)',
            border: '2px solid rgba(139, 92, 246, 0.6)',
            borderRadius: '12px',
            padding: '16px 20px',
            marginBottom: '20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '24px' }}>🏈</span>
            <div>
              <strong style={{ color: '#c084fc', fontSize: '15px' }}>
                Week 1 Kickoff & Market Volatility Alert ({marketAlerts.length} Starter{marketAlerts.length > 1 ? 's' : ''} Flagged):
              </strong>
              <div style={{ fontSize: '12.5px', color: '#e9d5ff', marginTop: '2px' }}>
                Polymarket prediction crowd odds detect volatile starting roles, decoy risks, or Thursday FLEX positioning.
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '4px' }}>
            {marketAlerts.map((alt, idx) => (
              <div
                key={idx}
                style={{
                  background: 'rgba(0, 0, 0, 0.25)',
                  borderRadius: '8px',
                  padding: '8px 12px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: '8px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span
                    className={`pill ${alt.isFlexTrap ? 'rose' : alt.isHighDecoy ? 'rose' : 'amber'}`}
                    style={{ fontSize: '11px', fontWeight: 800 }}
                  >
                    {alt.isFlexTrap ? '🚨 TNF FLEX TRAP' : alt.isHighDecoy ? '🚨 HIGH DECOY' : '⚠️ STARTER VOLATILITY'}
                  </span>
                  <strong style={{ color: '#fff', fontSize: '13px' }}>
                    {alt.player.full_name} ({alt.slotName} • {alt.player.pro_team})
                  </strong>
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                  {alt.advice}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Multi-Source Projection Selector Card */}
      <div className="projection-source-card">
        <div className="projection-source-header">
          <div className="projection-source-title-group">
            <span style={{ fontSize: '18px' }}>📊</span>
            <div>
              <div className="projection-source-label">
                Projection Source Engine:
                <span style={{ color: '#38bdf8', marginLeft: '6px' }}>
                  {projectionSource === 'MODEL'
                    ? 'Our Quant Model (Default)'
                    : projectionSource === 'CONSENSUS'
                    ? 'Multi-Source Consensus (Model + FP + Sleeper + ESPN)'
                    : projectionSource === 'FANTASYPROS'
                    ? 'FantasyPros (PPR)'
                    : projectionSource === 'SLEEPER'
                    ? 'Sleeper / RotoWire (PPR)'
                    : 'ESPN Official'}
                </span>
              </div>
              <div className="projection-source-desc">
                Re-solves optimal lineup & displays individual source stats for Week {league?.current_week || 1} (PPR scoring)
              </div>
            </div>
          </div>
          <div className="source-selector-pills">
            <button
              className={`source-pill-btn ${projectionSource === 'MODEL' ? 'active' : ''}`}
              onClick={() => onProjectionSourceChange('MODEL')}
              title="Our Quantitative Vegas micro-volume script projection engine"
            >
              ⚡ Quant Model {lineup?.total_model_projected ? `(${lineup.total_model_projected.toFixed(1)})` : ''}
            </button>
            <button
              className={`source-pill-btn ${projectionSource === 'CONSENSUS' ? 'active' : ''}`}
              onClick={() => onProjectionSourceChange('CONSENSUS')}
              title="Outlier-Protected Bayesian Consensus (Model + FP + Sleeper + ESPN)"
            >
              ⭐ Consensus {lineup?.total_consensus_projected ? `(${lineup.total_consensus_projected.toFixed(1)})` : ''}
            </button>
            <button
              className={`source-pill-btn ${projectionSource === 'FANTASYPROS' ? 'active' : ''}`}
              onClick={() => onProjectionSourceChange('FANTASYPROS')}
              title="FantasyPros Multi-Expert ECR Consensus PPR Projections"
            >
              🌐 FantasyPros {lineup?.total_fp_projected ? `(${lineup.total_fp_projected.toFixed(1)})` : ''}
            </button>
            <button
              className={`source-pill-btn ${projectionSource === 'SLEEPER' ? 'active' : ''}`}
              onClick={() => onProjectionSourceChange('SLEEPER')}
              title="Sleeper / RotoWire Official Weekly PPR Projections"
            >
              📱 Sleeper {lineup?.total_sleeper_projected ? `(${lineup.total_sleeper_projected.toFixed(1)})` : ''}
            </button>
            <button
              className={`source-pill-btn ${projectionSource === 'ESPN' ? 'active' : ''}`}
              onClick={() => onProjectionSourceChange('ESPN')}
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
            onClick={() => onStrategyChange('AUTO')}
            title="Automatically calculates matchup spread against your weekly opponent and selects Ceiling (underdog) or Floor (favorite)"
          >
            🤖 Auto-Spread (AI Game Theory)
          </button>
          <button
            className={`strategy-pill-btn balanced ${strategyMode === 'BALANCED' ? 'active' : ''}`}
            onClick={() => onStrategyChange('BALANCED')}
          >
            🎯 Balanced (Standard)
          </button>
          <button
            className={`strategy-pill-btn ceiling ${strategyMode === 'CEILING' ? 'active' : ''}`}
            onClick={() => onStrategyChange('CEILING')}
            title="Weights 90th percentile boom ceiling (air yards, shootout environments, goal line work) for underdog matchups"
          >
            🚀 Ceiling Mode (Underdog Boom)
          </button>
          <button
            className={`strategy-pill-btn floor ${strategyMode === 'FLOOR' ? 'active' : ''}`}
            onClick={() => onStrategyChange('FLOOR')}
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
            {hasRevertibleSwaps && (
              <button
                className="btn btn-secondary btn-sm"
                onClick={handleResetToOptimal}
                title="Revert custom substitutions back to the algorithmic optimal starters (injury replacements are preserved)"
              >
                🔄 Reset to Optimal Lineup
              </button>
            )}
            <button
              className="btn btn-primary btn-sm"
              style={{ backgroundColor: '#10b981', borderColor: '#10b981', color: '#022c22', fontWeight: 700 }}
              onClick={onOpenPushModal}
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
                    {lineup.opponent_projected_points ? ` vs ${lineup.opponent_team_name || 'Opponent'} (${lineup.opponent_projected_points} pts)` : ''}
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
              onClick={() => onStrategyChange('AUTO')}
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
            <span className="metric-val">{hasCustomSwaps ? currentLineupProjectedTotal : (lineup.total_effective_points || lineup.total_projected_points)} pts</span>
            <span className="metric-sub">
              Engine: {projectionSource === 'MODEL' ? 'Quant Model' : projectionSource === 'CONSENSUS' ? 'Multi-Source Consensus' : projectionSource === 'FANTASYPROS' ? 'FantasyPros PPR' : projectionSource === 'SLEEPER' ? 'Sleeper (RotoWire)' : 'ESPN Official'}
            </span>
          </div>

          {(lineup.total_actual_points !== undefined && lineup.total_actual_points > 0) && (
            <div className="banner-metric">
              <span className="metric-label">Live Fantasy Score</span>
              <span className="metric-val emerald">{lineup.total_actual_points.toFixed(1)} pts</span>
              <span className="metric-sub">
                Live Projected: {(lineup.total_effective_points || lineup.total_projected_points).toFixed(1)} pts
              </span>
            </div>
          )}

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
              onReviewCloseCall(first.starter.player_id, first.bench_player.player_id)
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
            {onOpenShareModal && (
              <button
                className="btn btn-secondary"
                style={{
                  fontWeight: 700,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
                onClick={onOpenShareModal}
                title="Export and share lineup card for Discord or Sleeper"
              >
                <span>📤</span>
                <span>Share Card</span>
              </button>
            )}
            <button
              className="btn btn-primary"
              style={{
                backgroundColor: '#10b981',
                borderColor: '#10b981',
                color: '#022c22',
                fontWeight: 800,
                boxShadow: '0 4px 14px rgba(16, 185, 129, 0.4)',
              }}
              onClick={onOpenPushModal}
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
                <th>
                  <Tooltip term="POINTS_PROJ" title="Actual Fantasy Points (Final/Live) or Pre-Game Projection (PPR)">
                    <span style={{ cursor: 'pointer' }}>Fantasy Pts</span>
                  </Tooltip>
                </th>
                <th>Matchup</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {effectiveStarters.map((slot: any, slotIdx: number) => {
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
                            <Tooltip term="FLEX_RISK" title={slot.flex_timing_note || (slot.is_flex_timing_optimal ? 'Optimal late kickoff slotting' : 'Early kickoff in FLEX warning')}>
                              <span
                                className={`pill ${slot.is_flex_timing_optimal ? 'emerald' : 'rose'}`}
                                style={{ fontSize: '10px', padding: '2px 6px', display: 'inline-block', cursor: 'pointer' }}
                              >
                                {slot.is_flex_timing_optimal ? '⏰ Late Lock' : '⚠️ Early Flex'}
                              </span>
                            </Tooltip>
                          </div>
                        )}
                      </td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                          <NFLTeamLogo team={p.pro_team} size={24} />
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
                              <Tooltip term="FP_RANK" title={`FantasyPros PPR Consensus: ${p.fp_pos_rank || '#' + p.fp_rank_ecr} (Avg: #${p.fp_rank_ave?.toFixed(1) || p.fp_rank_ecr})`}>
                                <span
                                  style={{
                                    color: '#38bdf8',
                                    fontWeight: 700,
                                    background: 'rgba(56, 189, 248, 0.15)',
                                    padding: '1px 6px',
                                    borderRadius: '4px',
                                    border: '1px solid rgba(56, 189, 248, 0.3)',
                                    cursor: 'pointer',
                                  }}
                                >
                                  ⭐ FP {p.fp_pos_rank || `#${p.fp_rank_ecr}`} (PPR)
                                </span>
                              </Tooltip>
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
                            <Tooltip term="VORP" title={`Live VORP: ${p.live_vorp > 0 ? '+' : ''}${p.live_vorp}`}>
                              <span
                                className="vorp-badge"
                              >
                                VORP: {p.live_vorp > 0 ? `+${p.live_vorp}` : p.live_vorp}
                              </span>
                            </Tooltip>
                          )}
                          {p.boris_chen_tier && (
                            <Tooltip term="BORIS_TIER" title={`Boris Chen GMM Tier ${p.boris_chen_tier}`}>
                              <span className={`boris-tier-badge tier-${p.boris_chen_tier}`}>
                                <span>💎</span> {p.boris_chen_tier_label || `T${p.boris_chen_tier}`}
                              </span>
                            </Tooltip>
                          )}
                          {slot.is_diff && (
                            <span className="diff-pill">DIFF vs ESPN</span>
                          )}
                        </div>
                        {renderLineupVegasProps(p)}
                      </td>
                      <td>
                        <span className="matchup-tag" style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
                          <span>{p.is_home ? 'vs' : '@'}</span>
                          <NFLTeamLogo team={p.opponent} size={16} />
                          <span>{p.opponent}</span>
                        </span>
                        {p.game_date && (
                          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                            {formatToMDT(p.game_date)}
                          </div>
                        )}
                        {p.opponent && p.opponent !== 'BYE' && (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', marginTop: '4px' }}>
                            {p.opp_dvp_rank !== undefined && p.opp_dvp_rank !== null && (
                              <div>
                                <Tooltip term="DVP" title={`DvP #${p.opp_dvp_rank} vs ${p.position}`}>
                                  <span
                                    className={`pill ${p.opp_dvp_rank <= 10 ? 'rose' : p.opp_dvp_rank >= 21 ? 'emerald' : 'amber'}`}
                                    style={{ fontSize: '10.5px', padding: '1px 6px', fontWeight: 700 }}
                                  >
                                    🛡️ DvP #{p.opp_dvp_rank}
                                  </span>
                                </Tooltip>
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
                              {p.wrcb_is_shadow && (
                                <span
                                  className="pill rose"
                                  style={{ fontSize: '10px', padding: '1px 5px', fontWeight: 800 }}
                                  title={`PFF Shadow Alert: Shadowed by ${p.wrcb_primary_cb || 'CB1'}`}
                                >
                                  🚨 Shadow ({p.wrcb_primary_cb})
                                </span>
                              )}
                              {p.wrcb_primary_cb && !p.wrcb_is_shadow && p.wrcb_advantage_rating !== 'SLOT_MISMATCH' && (
                                <span
                                  className={`pill ${((p.wrcb_advantage_score ?? 0) >= 15) ? 'emerald' : ((p.wrcb_advantage_score ?? 0) <= -15) ? 'rose' : 'cyan'}`}
                                  style={{ fontSize: '10px', padding: '1px 5px', fontWeight: 700 }}
                                  title={`PFF Opposing Primary CB: ${p.wrcb_primary_cb} (${p.wrcb_advantage_rating || 'NEUTRAL'})`}
                                >
                                  🎯 vs {p.wrcb_primary_cb} {p.wrcb_advantage_score != null ? `(${p.wrcb_advantage_score > 0 ? '+' : ''}${p.wrcb_advantage_score}%)` : ''}
                                </span>
                              )}
                              {p.wrcb_advantage_rating === 'SLOT_MISMATCH' && (
                                <Tooltip term="SLOT_MISMATCH" title={`PFF Slot Mismatch Advantage vs ${p.wrcb_primary_cb || 'Slot CB'}`}>
                                  <span
                                    className="pill emerald"
                                    style={{ fontSize: '10px', padding: '1px 5px', fontWeight: 800, cursor: 'pointer' }}
                                  >
                                    🔥 Slot Adv ({p.wrcb_primary_cb || 'Slot'})
                                  </span>
                                </Tooltip>
                              )}
                              {p.game_script === 'SHOOTOUT' && (
                                <Tooltip term="SHOOTOUT" title="Vegas Game Script: High-Ceiling Shootout (O/U ≥ 47.5)">
                                  <span
                                    className="pill amber"
                                    style={{ fontSize: '10px', padding: '1px 5px', fontWeight: 800, cursor: 'pointer' }}
                                  >
                                    ⚡ Shootout
                                  </span>
                                </Tooltip>
                              )}
                            </div>
                          </div>
                        )}
                      </td>
                      <td>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                          <Tooltip term="STARTSCORE" title={`StartScore: ${p.start_score}`}>
                            <span className={`score-badge ${getScoreColorClass(p.start_score)}`} style={{ cursor: 'pointer' }}>
                              {p.start_score}
                            </span>
                          </Tooltip>
                          <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                            {p.ceiling_score !== undefined && p.ceiling_score > 0 && (
                              <Tooltip term="CEILING_FLOOR" title={`90th Percentile Ceiling: ${p.ceiling_score}`}>
                                <span className="ceiling-floor-tag ceiling" style={{ cursor: 'pointer' }}>
                                  🚀 {p.ceiling_score}
                                </span>
                              </Tooltip>
                            )}
                            {p.floor_score !== undefined && p.floor_score > 0 && (
                              <Tooltip term="CEILING_FLOOR" title={`20th Percentile Floor: ${p.floor_score}`}>
                                <span className="ceiling-floor-tag floor" style={{ cursor: 'pointer' }}>
                                  🛡️ {p.floor_score}
                                </span>
                              </Tooltip>
                            )}
                          </div>
                        </div>
                      </td>
                      <td>{renderPlayerPointsBadge(p)}</td>
                      <td>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', alignItems: 'flex-start' }}>
                          {renderMatchupGradePill(p.matchup_grade)}
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
                            onClick={() => onCompareStarterWithBench(p)}
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
                            !isPlayerDoubtfulOrInjured(slot.original_recommended) ? (
                              <button
                                className="btn-link"
                                style={{ fontSize: '11px', color: 'var(--accent-rose)' }}
                                onClick={() => handleRevertSlot(slotIdx)}
                                title="Revert back to optimal starter"
                              >
                                ↺ Revert
                              </button>
                            ) : (
                              <span
                                className="pill amber"
                                style={{
                                  fontSize: '10px',
                                  padding: '1px 6px',
                                  fontWeight: 700,
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '3px',
                                }}
                                title={`Revert disabled: ${slot.original_recommended?.full_name || 'Original starter'} is ${slot.original_recommended?.injury_status || 'Injured'}. There's no point reverting to an unplayable asset.`}
                              >
                                🔒 Injury Swap
                              </span>
                            )
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
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                          <NFLTeamLogo team={cand.pro_team} size={22} />
                                          <div>
                                            <div className="swap-cand-name">{cand.full_name}</div>
                                            <div className="swap-cand-sub" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                                              <span>{cand.position} • {cand.pro_team} ({cand.is_home ? 'vs' : '@'}</span>
                                              <NFLTeamLogo team={cand.opponent} size={14} />
                                              <span>{cand.opponent})</span>
                                            </div>
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
                                  {p.reasons_positive.map((r: string, i: number) => renderWhyFactorItem(r, true, i))}
                                </ul>
                              </div>
                              <div>
                                <div style={{ color: 'var(--accent-rose)', fontWeight: 600, marginBottom: '6px' }}>
                                  Risk & Negative Factors:
                                </div>
                                <ul className="factor-list">
                                  {p.reasons_negative.length > 0 ? (
                                    p.reasons_negative.map((r: string, i: number) => renderWhyFactorItem(r, false, i))
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
                  {lineup?.bench.map((b: StartSitEvaluation) => (
                    <tr key={`unified-bench-${b.player_id}`}>
                      <td>
                        <span className="slot-badge" style={{ background: 'rgba(148, 163, 184, 0.15)', borderColor: 'rgba(148, 163, 184, 0.3)', color: '#cbd5e1' }}>
                          BENCH
                        </span>
                      </td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                          <NFLTeamLogo team={b.pro_team} size={22} />
                          <span style={{ fontWeight: 600 }}>{b.full_name}</span>
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                          <span>{b.position} • {b.pro_team}</span>
                          {b.fp_pos_rank && <span style={{ marginLeft: '6px', color: '#38bdf8', fontWeight: 600 }}>⭐ FP {b.fp_pos_rank}</span>}
                        </div>
                      </td>
                      <td>
                        <span className="matchup-tag" style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
                          <span>{b.is_home ? 'vs' : '@'}</span>
                          <NFLTeamLogo team={b.opponent} size={16} />
                          <span>{b.opponent}</span>
                        </span>
                        {b.opp_dvp_rank && <div style={{ fontSize: '10.5px', color: 'var(--text-muted)', marginTop: '2px' }}>DvP #{b.opp_dvp_rank}</div>}
                      </td>
                      <td>
                        <span className={`score-badge ${getScoreColorClass(b.start_score)}`}>{b.start_score}</span>
                      </td>
                      <td>{renderPlayerPointsBadge(b)}</td>
                      <td>
                        {renderMatchupGradePill(b.matchup_grade)}
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
                          onClick={() => onCompareBenchWithStarter(b)}
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
                    lineup.ir.map((p: StartSitEvaluation) => (
                      <tr key={`unified-ir-${p.player_id}`}>
                        <td><span className="slot-badge rose">IR</span></td>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <NFLTeamLogo team={p.pro_team} size={22} />
                            <strong style={{ color: '#f87171' }}>{p.full_name}</strong>
                          </div>
                        </td>
                        <td>{p.position} • {p.pro_team}</td>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                            <NFLTeamLogo team={p.opponent} size={16} />
                            <span>{p.opponent}</span>
                          </div>
                        </td>
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
                    <th>
                      <Tooltip term="POINTS_PROJ" title="Actual Fantasy Points (Final/Live) or Pre-Game Projection (PPR)">
                        <span style={{ cursor: 'pointer' }}>Fantasy Pts</span>
                      </Tooltip>
                    </th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {effectiveBench.map((b: StartSitEvaluation) => {
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
                                  <Tooltip term="FP_RANK" title={`FantasyPros PPR Consensus: ${b.fp_pos_rank || '#' + b.fp_rank_ecr} (Avg: #${b.fp_rank_ave?.toFixed(1) || b.fp_rank_ecr})`}>
                                    <span
                                      style={{
                                        color: '#38bdf8',
                                        fontWeight: 700,
                                        background: 'rgba(56, 189, 248, 0.15)',
                                        padding: '1px 5px',
                                        borderRadius: '4px',
                                        border: '1px solid rgba(56, 189, 248, 0.3)',
                                        cursor: 'pointer',
                                      }}
                                    >
                                      ⭐ FP {b.fp_pos_rank || `#${b.fp_rank_ecr}`} (PPR)
                                    </span>
                                  </Tooltip>
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
                              {b.boris_chen_tier && (
                                <Tooltip term="BORIS_TIER" title={`Boris Chen GMM Tier ${b.boris_chen_tier}`}>
                                  <span className={`boris-tier-badge tier-${b.boris_chen_tier}`} style={{ fontSize: '9.5px', padding: '1px 5px' }}>
                                    <span>💎</span> {b.boris_chen_tier_label || `T${b.boris_chen_tier}`}
                                  </span>
                                </Tooltip>
                              )}
                            </div>
                            {renderLineupVegasProps(b, true)}
                          </td>
                          <td>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <NFLTeamLogo team={b.pro_team} size={18} />
                              <span>{b.position} • {b.pro_team}</span>
                            </div>
                          </td>
                          <td>
                            <span className="matchup-tag" style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
                              <span>{b.is_home ? 'vs' : '@'}</span>
                              <NFLTeamLogo team={b.opponent} size={16} />
                              <span>{b.opponent}</span>
                            </span>
                            {b.opponent && b.opponent !== 'BYE' && (
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', marginTop: '4px' }}>
                                {b.opp_dvp_rank !== undefined && b.opp_dvp_rank !== null && (
                                  <div>
                                    <Tooltip term="DVP" title={`DvP #${b.opp_dvp_rank} vs ${b.position}`}>
                                      <span
                                        className={`pill ${b.opp_dvp_rank <= 10 ? 'rose' : b.opp_dvp_rank >= 21 ? 'emerald' : 'amber'}`}
                                        style={{ fontSize: '10px', padding: '1px 5px', fontWeight: 700 }}
                                      >
                                        🛡️ DvP #{b.opp_dvp_rank}
                                      </span>
                                    </Tooltip>
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
                                  {b.wrcb_is_shadow && (
                                    <Tooltip term="SHADOW_CB" title={`PFF Shadow Alert: Shadowed by ${b.wrcb_primary_cb || 'CB1'}`}>
                                      <span
                                        className="pill rose"
                                        style={{ fontSize: '10px', padding: '1px 5px', fontWeight: 800, cursor: 'pointer' }}
                                      >
                                        🚨 Shadow ({b.wrcb_primary_cb})
                                      </span>
                                    </Tooltip>
                                  )}
                                  {b.wrcb_primary_cb && !b.wrcb_is_shadow && b.wrcb_advantage_rating !== 'SLOT_MISMATCH' && (
                                    <span
                                      className={`pill ${((b.wrcb_advantage_score ?? 0) >= 15) ? 'emerald' : ((b.wrcb_advantage_score ?? 0) <= -15) ? 'rose' : 'cyan'}`}
                                      style={{ fontSize: '10px', padding: '1px 5px', fontWeight: 700 }}
                                      title={`PFF Opposing Primary CB: ${b.wrcb_primary_cb} (${b.wrcb_advantage_rating || 'NEUTRAL'})`}
                                    >
                                      🎯 vs {b.wrcb_primary_cb} {b.wrcb_advantage_score != null ? `(${b.wrcb_advantage_score > 0 ? '+' : ''}${b.wrcb_advantage_score}%)` : ''}
                                    </span>
                                  )}
                                  {b.wrcb_advantage_rating === 'SLOT_MISMATCH' && (
                                    <Tooltip term="SLOT_MISMATCH" title={`PFF Slot Mismatch Advantage vs ${b.wrcb_primary_cb || 'Slot CB'}`}>
                                      <span
                                        className="pill emerald"
                                        style={{ fontSize: '10px', padding: '1px 5px', fontWeight: 800, cursor: 'pointer' }}
                                      >
                                        🔥 Slot Adv ({b.wrcb_primary_cb || 'Slot'})
                                      </span>
                                    </Tooltip>
                                  )}
                                  {b.game_script === 'SHOOTOUT' && (
                                    <Tooltip term="SHOOTOUT" title="Vegas Game Script: High-Ceiling Shootout (O/U ≥ 47.5)">
                                      <span
                                        className="pill amber"
                                        style={{ fontSize: '10px', padding: '1px 5px', fontWeight: 800, cursor: 'pointer' }}
                                      >
                                        ⚡ Shootout
                                      </span>
                                    </Tooltip>
                                  )}
                                </div>
                              </div>
                            )}
                          </td>
                          <td>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                              <Tooltip term="STARTSCORE" title={`StartScore: ${b.start_score}`}>
                                <span className={`score-badge ${getScoreColorClass(b.start_score)}`} style={{ cursor: 'pointer' }}>
                                  {b.start_score}
                                </span>
                              </Tooltip>
                              <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                                {b.ceiling_score !== undefined && b.ceiling_score > 0 && (
                                  <Tooltip term="CEILING_FLOOR" title={`90th Percentile Ceiling: ${b.ceiling_score}`}>
                                    <span className="ceiling-floor-tag ceiling" style={{ cursor: 'pointer' }}>
                                      🚀 {b.ceiling_score}
                                    </span>
                                  </Tooltip>
                                )}
                                {b.floor_score !== undefined && b.floor_score > 0 && (
                                  <Tooltip term="CEILING_FLOOR" title={`20th Percentile Floor: ${b.floor_score}`}>
                                    <span className="ceiling-floor-tag floor" style={{ cursor: 'pointer' }}>
                                      🛡️ {b.floor_score}
                                    </span>
                                  </Tooltip>
                                )}
                                {b.contingency_score !== undefined && b.contingency_score > 0 && (
                                  <Tooltip term="BELLCOW" title={`Contingent Workhorse Upside: ${b.contingency_score}`}>
                                    <span className="ceiling-floor-tag contingent" style={{ cursor: 'pointer' }}>
                                      ⚡ {b.contingency_score}
                                    </span>
                                  </Tooltip>
                                )}
                              </div>
                            </div>
                          </td>
                          <td>{renderPlayerPointsBadge(b)}</td>
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
                                style={{ padding: '2px 8px', fontSize: '11px' }}
                                onClick={() => onCompareBenchWithStarter(b)}
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
                                      {b.reasons_positive.map((r: string, i: number) => renderWhyFactorItem(r, true, i))}
                                    </ul>
                                  </div>
                                  <div>
                                    <div style={{ color: 'var(--accent-rose)', fontWeight: 600, marginBottom: '6px' }}>
                                      Risk & Negative Factors:
                                    </div>
                                    <ul className="factor-list">
                                      {b.reasons_negative.length > 0 ? (
                                        b.reasons_negative.map((r: string, i: number) => renderWhyFactorItem(r, false, i))
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
                    lineup.ir.map((p: StartSitEvaluation) => (
                      <tr key={p.player_id}>
                        <td>
                          <span className="slot-badge rose">IR</span>
                        </td>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <NFLTeamLogo team={p.pro_team} size={22} />
                            <strong style={{ color: '#f87171' }}>{p.full_name}</strong>
                          </div>
                        </td>
                        <td>{p.position} • {p.pro_team}</td>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                            <NFLTeamLogo team={p.opponent} size={16} />
                            <span>{p.opponent}</span>
                          </div>
                        </td>
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
  )
}
