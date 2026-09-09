import React, { useState, useMemo } from 'react'
import type {
  DFSLineupResponse,
  DFSSlateDataResponse,
  DFSPlayerPoolItem,
} from '../../types'
import './DfsRosterBoard.css'

export interface SlotPlayer {
  player_id: string
  name: string
  shortName: string
  position: string
  team: string
  opponent: string
  salary: number
  proj: number
  value_ratio: number
  ceiling?: number
  opp_soft_rank?: number
  opp_tier?: string
  opp_tier_label?: string
  opp_fd_fpa?: number
  proj_ownership?: number
  isLocked: boolean
}

export interface RosterSlotState {
  slotId: number
  slotType: 'QB' | 'RB' | 'WR' | 'TE' | 'FLX' | 'DST'
  label: string
  player: SlotPlayer | null
}

interface DfsRosterBoardProps {
  currentDisplayedLineup: DFSLineupResponse | null
  lineup: DFSLineupResponse | null
  activeLineupIndex: number
  setActiveLineupIndex: (idx: number) => void
  slateData: DFSSlateDataResponse | null
  lockPlayers: string[]
  toggleLock: (playerName: string) => void
  clearAllLocks: () => void
  customProjections: Record<string, number>
  solveLineup: () => Promise<void>
  isLoadingLineup: boolean
  exportLineupsToFanDuel: () => Promise<void>
  isExporting: boolean
  onSelectPoolPosition: (pos: string) => void
  onResetLineup: () => void
  viewMode: 'card' | 'table'
  setViewMode: (mode: 'card' | 'table') => void
  setSelectedDvpPlayer?: (player: any) => void
  stackQb?: string
  setStackQb?: (qb: string) => void
}

import { NFLTeamLogo } from '../shared/NFLTeamLogo'
export { NFLTeamLogo }


/**
 * Format full name to standard DFS short name: "Jahmyr Gibbs" -> "J. Gibbs"
 */
export const formatShortName = (fullName: string): string => {
  if (!fullName) return ''
  const parts = fullName.trim().split(/\s+/)
  if (parts.length === 1) return parts[0]
  return `${parts[0][0]}. ${parts.slice(1).join(' ')}`
}

export const DfsRosterBoard: React.FC<DfsRosterBoardProps> = ({
  currentDisplayedLineup,
  lineup,
  activeLineupIndex,
  setActiveLineupIndex,
  slateData,
  lockPlayers,
  toggleLock,
  clearAllLocks,
  customProjections,
  solveLineup,
  isLoadingLineup,
  exportLineupsToFanDuel,
  isExporting,
  onSelectPoolPosition,
  onResetLineup,
  viewMode,
  setViewMode,
  stackQb,
  setStackQb,
}) => {
  // Quick Picker Modal state for empty slots
  const [quickPickerSlot, setQuickPickerSlot] = useState<{
    slotId: number
    slotType: 'QB' | 'RB' | 'WR' | 'TE' | 'FLX' | 'DST'
    label: string
  } | null>(null)
  const [quickPickerSearch, setQuickPickerSearch] = useState('')

  // Quick Stacking Modal state
  const [showStackModal, setShowStackModal] = useState(false)

  // Compute 9 Roster Slots
  const rosterSlots: RosterSlotState[] = useMemo(() => {
    // 1. If we have a solved lineup, populate directly from its 9 items
    if (currentDisplayedLineup?.roster && currentDisplayedLineup.roster.length > 0) {
      const defaultSlots: RosterSlotState[] = [
        { slotId: 0, slotType: 'QB', label: 'QB', player: null },
        { slotId: 1, slotType: 'RB', label: 'RB', player: null },
        { slotId: 2, slotType: 'RB', label: 'RB', player: null },
        { slotId: 3, slotType: 'WR', label: 'WR', player: null },
        { slotId: 4, slotType: 'WR', label: 'WR', player: null },
        { slotId: 5, slotType: 'WR', label: 'WR', player: null },
        { slotId: 6, slotType: 'TE', label: 'TE', player: null },
        { slotId: 7, slotType: 'FLX', label: 'FLX', player: null },
        { slotId: 8, slotType: 'DST', label: 'DST', player: null },
      ]

      let rbCount = 0
      let wrCount = 0
      let teCount = 0

      for (const item of currentDisplayedLineup.roster) {
        const pos = (item.position || '').toUpperCase()
        const isLocked = lockPlayers.includes(item.name)
        const slotPlayer: SlotPlayer = {
          player_id: item.player_id,
          name: item.name,
          shortName: formatShortName(item.name),
          position: item.position,
          team: item.team,
          opponent: item.opponent,
          salary: item.salary,
          proj: item.proj,
          value_ratio: item.value_ratio,
          ceiling: item.ceiling,
          opp_soft_rank: item.opp_soft_rank,
          opp_tier: item.opp_tier,
          opp_tier_label: item.opp_tier_label,
          opp_fd_fpa: item.opp_fd_fpa,
          proj_ownership: item.proj_ownership,
          isLocked,
        }

        if (pos === 'QB' && !defaultSlots[0].player) {
          defaultSlots[0].player = slotPlayer
        } else if (pos === 'RB') {
          if (rbCount === 0) {
            defaultSlots[1].player = slotPlayer
            rbCount++
          } else if (rbCount === 1) {
            defaultSlots[2].player = slotPlayer
            rbCount++
          } else if (!defaultSlots[7].player) {
            defaultSlots[7].player = slotPlayer
          }
        } else if (pos === 'WR') {
          if (wrCount === 0) {
            defaultSlots[3].player = slotPlayer
            wrCount++
          } else if (wrCount === 1) {
            defaultSlots[4].player = slotPlayer
            wrCount++
          } else if (wrCount === 2) {
            defaultSlots[5].player = slotPlayer
            wrCount++
          } else if (!defaultSlots[7].player) {
            defaultSlots[7].player = slotPlayer
          }
        } else if (pos === 'TE') {
          if (teCount === 0) {
            defaultSlots[6].player = slotPlayer
            teCount++
          } else if (!defaultSlots[7].player) {
            defaultSlots[7].player = slotPlayer
          }
        } else if ((pos === 'D' || pos === 'DST' || pos === 'DEF') && !defaultSlots[8].player) {
          defaultSlots[8].player = slotPlayer
        } else {
          // Fallback to first available empty slot
          const emptySlot = defaultSlots.find((s) => !s.player)
          if (emptySlot) emptySlot.player = slotPlayer
        }
      }

      return defaultSlots
    }

    // 2. Otherwise: Interactive builder mode from lockPlayers + slateData.players
    const slots: RosterSlotState[] = [
      { slotId: 0, slotType: 'QB', label: 'QB', player: null },
      { slotId: 1, slotType: 'RB', label: 'RB', player: null },
      { slotId: 2, slotType: 'RB', label: 'RB', player: null },
      { slotId: 3, slotType: 'WR', label: 'WR', player: null },
      { slotId: 4, slotType: 'WR', label: 'WR', player: null },
      { slotId: 5, slotType: 'WR', label: 'WR', player: null },
      { slotId: 6, slotType: 'TE', label: 'TE', player: null },
      { slotId: 7, slotType: 'FLX', label: 'FLX', player: null },
      { slotId: 8, slotType: 'DST', label: 'DST', player: null },
    ]

    if (!slateData?.players) return slots

    const playerMap = new Map<string, DFSPlayerPoolItem>()
    for (const p of slateData.players) {
      playerMap.set(p.name.toLowerCase(), p)
      playerMap.set(p.player_id.toLowerCase(), p)
    }

    // Slot in each locked player into their eligible positions
    for (const name of lockPlayers) {
      const p = playerMap.get(name.toLowerCase())
      if (!p) continue

      const pos = (p.position || '').toUpperCase()
      const slotPlayer: SlotPlayer = {
        player_id: p.player_id,
        name: p.name,
        shortName: formatShortName(p.name),
        position: p.position,
        team: p.team,
        opponent: p.opponent,
        salary: p.salary,
        proj: customProjections[p.name] ?? p.proj,
        value_ratio: p.value_ratio,
        ceiling: p.ceiling_proj,
        opp_soft_rank: p.opp_soft_rank,
        opp_tier: p.opp_tier,
        opp_tier_label: p.opp_tier_label,
        opp_fd_fpa: p.opp_fd_fpa,
        proj_ownership: p.proj_ownership,
        isLocked: true,
      }

      if (pos === 'QB') {
        if (!slots[0].player) slots[0].player = slotPlayer
      } else if (pos === 'RB') {
        if (!slots[1].player) {
          slots[1].player = slotPlayer
        } else if (!slots[2].player) {
          slots[2].player = slotPlayer
        } else if (!slots[7].player) {
          slots[7].player = slotPlayer
        }
      } else if (pos === 'WR') {
        if (!slots[3].player) {
          slots[3].player = slotPlayer
        } else if (!slots[4].player) {
          slots[4].player = slotPlayer
        } else if (!slots[5].player) {
          slots[5].player = slotPlayer
        } else if (!slots[7].player) {
          slots[7].player = slotPlayer
        }
      } else if (pos === 'TE') {
        if (!slots[6].player) {
          slots[6].player = slotPlayer
        } else if (!slots[7].player) {
          slots[7].player = slotPlayer
        }
      } else if (pos === 'D' || pos === 'DST' || pos === 'DEF') {
        if (!slots[8].player) slots[8].player = slotPlayer
      }
    }

    return slots
  }, [currentDisplayedLineup, slateData, lockPlayers, customProjections])

  // Live Metrics calculations (Salary Rem, FP Proj, Value, pOwn)
  const metrics = useMemo(() => {
    const salaryCap = 60000

    if (currentDisplayedLineup) {
      return {
        salaryRem: currentDisplayedLineup.salary_remaining,
        totalSalary: currentDisplayedLineup.total_salary,
        avgRemPerSlot: 0,
        emptySlotsCount: 0,
        fpProj: currentDisplayedLineup.total_projected_points,
        valueMultiplier: currentDisplayedLineup.value_multiplier,
        pOwn: currentDisplayedLineup.cumulative_ownership,
        isComplete: true,
      }
    }

    // Builder mode metrics
    const filledSlots = rosterSlots.filter((s) => s.player !== null)
    const emptySlots = rosterSlots.filter((s) => s.player === null)
    const totalSalary = filledSlots.reduce((sum, s) => sum + (s.player?.salary || 0), 0)
    const salaryRem = Math.max(0, salaryCap - totalSalary)
    const avgRemPerSlot = emptySlots.length > 0 ? Math.round(salaryRem / emptySlots.length) : 0
    const fpProj = filledSlots.reduce((sum, s) => sum + (s.player?.proj || 0), 0)
    const valueMultiplier = totalSalary > 0 ? fpProj / (totalSalary / 1000) : 0
    const pOwn = filledSlots.reduce((sum, s) => sum + (s.player?.proj_ownership || 0), 0)

    return {
      salaryRem,
      totalSalary,
      avgRemPerSlot,
      emptySlotsCount: emptySlots.length,
      fpProj: Math.round(fpProj * 10) / 10,
      valueMultiplier: Math.round(valueMultiplier * 10) / 10,
      pOwn: Math.round(pOwn * 10) / 10,
      isComplete: emptySlots.length === 0,
    }
  }, [currentDisplayedLineup, rosterSlots])

  // Multi-lineup tabs count
  const portfolioTabs = useMemo(() => {
    if (lineup?.lineups && lineup.lineups.length > 1) {
      return lineup.lineups.map((_, idx) => `Line ${idx + 1}`)
    }
    return ['Line 1', 'Line 2', 'Line 3', 'Line 4', 'Line 5']
  }, [lineup])

  // Filtered players for Quick Picker Modal
  const quickPickerCandidates = useMemo(() => {
    if (!quickPickerSlot || !slateData?.players) return []
    const slotType = quickPickerSlot.slotType

    let eligible = slateData.players.filter((p) => {
      const pos = (p.position || '').toUpperCase()
      if (slotType === 'QB') return pos === 'QB'
      if (slotType === 'RB') return pos === 'RB'
      if (slotType === 'WR') return pos === 'WR'
      if (slotType === 'TE') return pos === 'TE'
      if (slotType === 'FLX') return ['RB', 'WR', 'TE'].includes(pos)
      if (slotType === 'DST') return ['D', 'DST', 'DEF'].includes(pos)
      return true
    })

    if (quickPickerSearch) {
      const q = quickPickerSearch.toLowerCase()
      eligible = eligible.filter(
        (p) =>
          p.name.toLowerCase().includes(q) ||
          p.team.toLowerCase().includes(q) ||
          p.opponent.toLowerCase().includes(q)
      )
    }

    // Sort by projected points descending
    return eligible.sort((a, b) => b.proj - a.proj).slice(0, 10)
  }, [quickPickerSlot, slateData, quickPickerSearch])

  return (
    <div className="dfs-roster-board-container">
      {/* Visual Controls / View Toggle Bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 4px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '13px', fontWeight: 800, color: '#ffffff' }}>
            🎯 DFS Optimal Lineup Builder
          </span>
          {lockPlayers.length > 0 && (
            <span className="dfs-badge dfs-badge-emerald" style={{ fontSize: '10px' }}>
              🔒 {lockPlayers.length} Player{lockPlayers.length > 1 ? 's' : ''} Locked
            </span>
          )}
          {metrics.isComplete && (
            <span className="dfs-badge dfs-badge-cyan" style={{ fontSize: '10px' }}>
              ✓ Full 9-Man Roster
            </span>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {currentDisplayedLineup && (
            <div style={{ display: 'inline-flex', background: 'rgba(15, 23, 42, 0.8)', border: '1px solid rgba(255, 255, 255, 0.1)', borderRadius: '6px', padding: '2px' }}>
              <button
                onClick={() => setViewMode('card')}
                style={{
                  padding: '4px 10px',
                  borderRadius: '4px',
                  fontSize: '11px',
                  fontWeight: 700,
                  border: 'none',
                  cursor: 'pointer',
                  background: viewMode === 'card' ? '#06b6d4' : 'transparent',
                  color: viewMode === 'card' ? '#080c14' : '#94a3b8',
                }}
              >
                📱 Lineup Card
              </button>
              <button
                onClick={() => setViewMode('table')}
                style={{
                  padding: '4px 10px',
                  borderRadius: '4px',
                  fontSize: '11px',
                  fontWeight: 700,
                  border: 'none',
                  cursor: 'pointer',
                  background: viewMode === 'table' ? '#06b6d4' : 'transparent',
                  color: viewMode === 'table' ? '#080c14' : '#94a3b8',
                }}
              >
                📊 Forensic Table
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Main Visual Roster Board Card */}
      <div className="dfs-roster-board-card">
        {/* 1. Top Live Metrics Ribbon */}
        <div className="dfs-roster-metric-bar">
          <div className="dfs-roster-metric-group">
            {/* Salary Remaining */}
            <div className="dfs-roster-metric-item">
              <div className="dfs-roster-metric-label">Salary Rem.</div>
              <div className="dfs-roster-metric-val">
                ${metrics.salaryRem.toLocaleString()}
              </div>
              {metrics.emptySlotsCount > 0 && (
                <div className="dfs-roster-metric-sub">
                  ${metrics.avgRemPerSlot.toLocaleString()}/slot avg
                </div>
              )}
            </div>

            {/* Projected FP */}
            <div className="dfs-roster-metric-item">
              <div className="dfs-roster-metric-label">FP Proj.</div>
              <div className="dfs-roster-metric-val" style={{ color: 'var(--accent-cyan, #06b6d4)' }}>
                {metrics.fpProj.toFixed(1)}
              </div>
            </div>

            {/* Value Multiplier */}
            <div className="dfs-roster-metric-item">
              <div className="dfs-roster-metric-label">Value</div>
              <div className="dfs-roster-metric-val" style={{ color: 'var(--accent-emerald, #10b981)' }}>
                {metrics.valueMultiplier > 0 ? `${metrics.valueMultiplier.toFixed(1)}x` : '—'}
              </div>
            </div>

            {/* Projected Ownership */}
            <div className="dfs-roster-metric-item">
              <div className="dfs-roster-metric-label">
                <span>pOwn</span>
                <span style={{ color: 'var(--accent-amber, #f59e0b)' }}>⚡</span>
              </div>
              <div className="dfs-roster-metric-val" style={{ color: '#c084fc' }}>
                {metrics.pOwn > 0 ? `${metrics.pOwn.toFixed(1)}%` : '—'}
              </div>
            </div>
          </div>

          <button
            className="dfs-roster-save-btn"
            title="Favorite / Save this Lineup Configuration"
            onClick={() => alert('Lineup saved to favorites!')}
          >
            🤍
          </button>
        </div>

        {/* 2. Portfolio Line Tabs (Line 1, Line 2, Line 3...) */}
        <div className="dfs-roster-tabs-row">
          {portfolioTabs.map((lineLabel, idx) => (
            <button
              key={idx}
              onClick={() => setActiveLineupIndex(idx)}
              className={`dfs-roster-line-tab ${activeLineupIndex === idx ? 'active' : ''}`}
            >
              <span>{lineLabel}</span>
              {lineup?.lineups && lineup.lineups[idx] && (
                <span className="dfs-roster-line-tag">
                  {lineup.lineups[idx].total_projected_points.toFixed(1)}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* 3. The 9 Roster Slot Rows */}
        <div className="dfs-roster-slots-list">
          {rosterSlots.map((slot) => {
            const player = slot.player
            const posClass = slot.slotType.toLowerCase()

            return (
              <div key={slot.slotId} className="dfs-roster-slot-row">
                {/* Position Code (QB, RB, WR, TE, FLX, DST) */}
                <div className={`dfs-roster-pos-col ${posClass}`}>
                  {slot.label}
                </div>

                {/* If Slot is Empty -> MAKE A PICK placeholder */}
                {!player ? (
                  <button
                    type="button"
                    className="dfs-roster-empty-btn"
                    onClick={() => {
                      setQuickPickerSlot({
                        slotId: slot.slotId,
                        slotType: slot.slotType,
                        label: slot.label,
                      })
                      setQuickPickerSearch('')
                    }}
                    title={`Click to pick a player for ${slot.label}`}
                  >
                    <div className="dfs-roster-make-pick">
                      <span>+</span>
                      <span>MAKE A PICK</span>
                    </div>
                    <span className="dfs-roster-empty-hint">Auto-fills on Optimize →</span>
                  </button>
                ) : (
                  /* If Slot is Filled (e.g. Jahmyr Gibbs locked in) */
                  <div className="dfs-roster-filled-body">
                    <div className="dfs-roster-player-main">
                      {/* NFL Team Logo */}
                      <NFLTeamLogo team={player.team} size={28} />

                      {/* Player Name & Sub-meta */}
                      <div className="dfs-roster-player-info">
                        <div className="dfs-roster-player-name-row">
                          <span className="dfs-roster-player-name" title={player.name}>
                            {player.shortName}
                          </span>
                        </div>
                        <div className="dfs-roster-player-sub">
                          <span>{player.position}</span>
                          <span>•</span>
                          <span className="dfs-roster-player-salary">
                            ${(player.salary / 1000).toFixed(1)}K
                          </span>
                          {player.opponent && (
                            <>
                              <span>•</span>
                              <span style={{ color: '#64748b' }}>vs {player.opponent}</span>
                            </>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Stats (FP & Value Multiplier) */}
                    <div className="dfs-roster-player-stats">
                      <div className="dfs-roster-stat-fp">
                        {player.proj.toFixed(1)}
                        <span style={{ fontSize: '11px', marginLeft: '2px' }}>FP</span>
                      </div>

                      <div className="dfs-roster-stat-val">
                        {player.value_ratio.toFixed(1)}x
                      </div>

                      {/* Action buttons: Remove 'X' & Green Lock Icon */}
                      <div className="dfs-roster-player-actions">
                        <button
                          type="button"
                          className="dfs-roster-unlock-btn"
                          onClick={() => toggleLock(player.name)}
                          title={player.isLocked ? 'Unlock / Remove from lineup' : 'Remove player'}
                        >
                          ✕
                        </button>

                        {player.isLocked && (
                          <div className="dfs-roster-lock-icon" title="Player Locked into Roster">
                            🔒
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* 4. Bottom Action Bar */}
        <div className="dfs-roster-actions-bar">
          <div className="dfs-roster-primary-actions">
            {/* Primary OPTIMIZE Button */}
            <button
              className="dfs-roster-optimize-btn"
              onClick={solveLineup}
              disabled={isLoadingLineup}
            >
              {isLoadingLineup ? (
                <>
                  <span className="status-dot"></span>
                  <span>OPTIMIZING...</span>
                </>
              ) : (
                <>
                  <span>⚡</span>
                  <span>OPTIMIZE</span>
                </>
              )}
            </button>

            {/* RESET Button */}
            <button
              className="dfs-roster-sub-btn"
              onClick={() => {
                if (window.confirm('Reset all locked players and clear the draft board?')) {
                  clearAllLocks()
                  onResetLineup()
                }
              }}
              title="Clear all locked picks and reset board"
            >
              <span>⊘</span>
              <span>RESET</span>
            </button>

            {/* STACK Button */}
            <button
              className="dfs-roster-sub-btn"
              onClick={() => setShowStackModal(true)}
              title="Open QB Correlation Game Stacks builder"
            >
              <span>🥞</span>
              <span>STACK</span>
            </button>
          </div>

          <div className="dfs-roster-secondary-actions">
            {lineup && (
              <button
                className="dfs-roster-sub-btn"
                onClick={exportLineupsToFanDuel}
                disabled={isExporting}
                title="Download FanDuel CSV for direct upload to contest"
                style={{ borderColor: 'rgba(6, 182, 212, 0.4)', color: '#38bdf8' }}
              >
                <span>📥</span>
                <span>{isExporting ? 'Exporting...' : 'EXPORT CSV'}</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Quick Picker Modal (Opens when clicking "MAKE A PICK") */}
      {quickPickerSlot && (
        <div
          className="dfs-picker-modal-overlay"
          onClick={() => setQuickPickerSlot(null)}
        >
          <div
            className="dfs-picker-modal"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="dfs-picker-header">
              <div className="dfs-picker-title">
                <span>➕</span>
                <span>Draft a {quickPickerSlot.label}</span>
              </div>
              <button
                className="dfs-picker-close-btn"
                onClick={() => setQuickPickerSlot(null)}
              >
                ✕
              </button>
            </div>

            <div className="dfs-picker-search-bar">
              <input
                type="text"
                className="dfs-picker-input"
                placeholder={`Search ${quickPickerSlot.label} by player or team...`}
                value={quickPickerSearch}
                onChange={(e) => setQuickPickerSearch(e.target.value)}
                autoFocus
              />
            </div>

            <div className="dfs-picker-list">
              {quickPickerCandidates.length === 0 ? (
                <div style={{ padding: '24px', textAlign: 'center', color: '#64748b', fontSize: '13px' }}>
                  No available players found matching criteria.
                </div>
              ) : (
                quickPickerCandidates.map((p) => {
                  const isLocked = lockPlayers.includes(p.name)
                  return (
                    <div key={p.player_id} className="dfs-picker-player-item">
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <NFLTeamLogo team={p.team} size={26} />
                        <div>
                          <div style={{ fontWeight: 800, color: '#ffffff', fontSize: '13px' }}>
                            {p.name}
                          </div>
                          <div style={{ fontSize: '11px', color: '#8da2b5', display: 'flex', gap: '6px' }}>
                            <span>{p.position}</span>
                            <span>•</span>
                            <span style={{ color: '#38bdf8' }}>${p.salary.toLocaleString()}</span>
                            <span>•</span>
                            <span>vs {p.opponent}</span>
                          </div>
                        </div>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <div style={{ textAlign: 'right' }}>
                          <div style={{ fontWeight: 800, color: '#06b6d4', fontSize: '13px' }}>
                            {p.proj.toFixed(1)} FP
                          </div>
                          <div style={{ fontSize: '10px', color: '#10b981', fontWeight: 700 }}>
                            {p.value_ratio.toFixed(1)}x val
                          </div>
                        </div>

                        <button
                          type="button"
                          className="dfs-picker-lock-btn"
                          onClick={() => {
                            toggleLock(p.name)
                            setQuickPickerSlot(null)
                          }}
                          style={{
                            background: isLocked
                              ? 'rgba(239, 68, 68, 0.2)'
                              : 'linear-gradient(135deg, #0d9488, #06b6d4)',
                            color: isLocked ? '#fca5a5' : '#ffffff',
                            border: isLocked ? '1px solid rgba(239, 68, 68, 0.4)' : 'none',
                          }}
                        >
                          {isLocked ? 'Unlock' : '🔒 Lock In'}
                        </button>
                      </div>
                    </div>
                  )
                })
              )}
            </div>

            <div className="dfs-picker-footer">
              <span style={{ fontSize: '11px', color: '#8da2b5' }}>
                Showing top projected {quickPickerSlot.label}s
              </span>
              <button
                type="button"
                onClick={() => {
                  onSelectPoolPosition(quickPickerSlot.slotType === 'DST' ? 'D' : quickPickerSlot.slotType)
                  setQuickPickerSlot(null)
                }}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#06b6d4',
                  fontSize: '12px',
                  fontWeight: 700,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                }}
              >
                <span>🔍 Open Full Player Pool</span>
                <span>→</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Quick Stacking Modal */}
      {showStackModal && (
        <div
          className="dfs-picker-modal-overlay"
          onClick={() => setShowStackModal(false)}
        >
          <div
            className="dfs-picker-modal"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: '580px' }}
          >
            <div className="dfs-picker-header">
              <div className="dfs-picker-title">
                <span>🥞</span>
                <span>Primary QB Correlation Game Stacks</span>
              </div>
              <button
                className="dfs-picker-close-btn"
                onClick={() => setShowStackModal(false)}
              >
                ✕
              </button>
            </div>

            <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <p style={{ fontSize: '12px', color: '#94a3b8', margin: 0 }}>
                Enforce a high-upside QB + Pass Catcher + Opposing Bring-Back stack for tournament GPP equity.
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <label style={{ fontSize: '11px', fontWeight: 700, color: '#8da2b5', textTransform: 'uppercase' }}>
                  Select Primary QB:
                </label>
                <select
                  value={stackQb || ''}
                  onChange={(e) => {
                    if (setStackQb) setStackQb(e.target.value)
                  }}
                  className="dfs-select-input"
                  style={{ width: '100%', background: 'rgba(15, 23, 42, 0.9)', color: '#ffffff' }}
                >
                  <option value="">🤖 Auto-Detect Optimal Game Stack</option>
                  {slateData?.players
                    ?.filter((p) => p.position === 'QB')
                    .sort((a, b) => b.proj - a.proj)
                    .map((qb) => (
                      <option key={qb.player_id} value={qb.name}>
                        {qb.name} ({qb.team} vs {qb.opponent}) - ${qb.salary.toLocaleString()}
                      </option>
                    ))}
                </select>
              </div>

              {/* Top detected stacks */}
              {slateData?.top_stacks && slateData.top_stacks.length > 0 && (
                <div>
                  <div style={{ fontSize: '11px', fontWeight: 700, color: '#8da2b5', textTransform: 'uppercase', marginBottom: '8px' }}>
                    🔥 Top Algorithm Game Stacks:
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {slateData.top_stacks.slice(0, 3).map((st, i) => (
                      <div
                        key={i}
                        style={{
                          padding: '10px 14px',
                          background: 'rgba(255, 255, 255, 0.03)',
                          border: '1px solid rgba(255, 255, 255, 0.08)',
                          borderRadius: '8px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                        }}
                      >
                        <div>
                          <strong style={{ color: '#ffffff', fontSize: '13px' }}>{st.qb}</strong>
                          <div style={{ fontSize: '11px', color: '#94a3b8' }}>
                            {st.game} • O/U {st.game_ou}
                          </div>
                          <div style={{ fontSize: '10px', color: '#06b6d4', marginTop: '2px' }}>
                            Pass Catcher: {st.target} | Bring-Back: {st.bring_back}
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => {
                            const qbName = st.qb.split(' (')[0]
                            if (setStackQb) setStackQb(qbName)
                            setShowStackModal(false)
                          }}
                          style={{
                            background: 'rgba(6, 182, 212, 0.15)',
                            border: '1px solid rgba(6, 182, 212, 0.4)',
                            color: '#38bdf8',
                            borderRadius: '6px',
                            padding: '6px 12px',
                            fontSize: '11px',
                            fontWeight: 700,
                            cursor: 'pointer',
                          }}
                        >
                          Use Stack
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="dfs-picker-footer">
              <span style={{ fontSize: '11px', color: '#8da2b5' }}>
                Applied during optimization
              </span>
              <button
                type="button"
                className="dfs-picker-lock-btn"
                onClick={() => setShowStackModal(false)}
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
