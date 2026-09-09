import React, { useState, useEffect, useRef, useMemo } from 'react'
import type { PlayerDirectoryItem, LeagueSummaryResponse, OptimizedLineupResult } from '../../types'
import { NFLTeamLogo } from '../shared/NFLTeamLogo'

interface CommandPaletteModalProps {
  isOpen: boolean
  onClose: () => void
  allPlayers: PlayerDirectoryItem[]
  onSelectPlayerForCompare?: (playerId: number) => void
  onNavigateTab: (tab: string) => void
  league: LeagueSummaryResponse | null
  lineup: OptimizedLineupResult | null
}

export const CommandPaletteModal: React.FC<CommandPaletteModalProps> = ({
  isOpen,
  onClose,
  allPlayers,
  onSelectPlayerForCompare,
  onNavigateTab,
  lineup,
}) => {
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const resultsRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (isOpen) {
      setQuery('')
      setSelectedIndex(0)
      setTimeout(() => {
        inputRef.current?.focus()
      }, 50)
    }
  }, [isOpen])

  // Key navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  // Navigation shortcuts
  const navShortcuts = useMemo(() => [
    { id: 'tab-lineup', title: 'Optimal Lineup', category: 'Navigation', tab: 'lineup', icon: '🏈' },
    { id: 'tab-compare', title: 'Start/Sit Comparator', category: 'Navigation', tab: 'compare', icon: '⚖️' },
    { id: 'tab-dfs', title: 'DFS Optimizer & Showdown', category: 'Navigation', tab: 'dfs', icon: '⚡' },
    { id: 'tab-vegas', title: 'Vegas Odds & Player Props', category: 'Navigation', tab: 'vegas', icon: '🎲' },
    { id: 'tab-intel', title: 'Matchup Intel & WR/CB Matrix', category: 'Navigation', tab: 'intel', icon: '🧠' },
    { id: 'tab-waivers', title: 'Waiver Wire Upgrades', category: 'Navigation', tab: 'waivers', icon: '🔄' },
    { id: 'tab-trades', title: '2-for-1 Consolidation Trades', category: 'Navigation', tab: 'trades', icon: '🤝' },
    { id: 'tab-injuries', title: 'Injury Wire Feed', category: 'Navigation', tab: 'injuries', icon: '🩺' },
    { id: 'tab-fantasypros', title: 'FantasyPros ECR Consensus', category: 'Navigation', tab: 'fantasypros', icon: '⭐' },
    { id: 'tab-settings', title: 'Settings & Model Weights', category: 'Navigation', tab: 'settings', icon: '⚙️' },
  ], [])

  // Filtered list
  const filteredItems = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) {
      return navShortcuts.slice(0, 6)
    }

    // Match tabs
    const matchedTabs = navShortcuts.filter((t) => t.title.toLowerCase().includes(q))

    // Match players
    const matchedPlayers = allPlayers
      .filter((p) => {
        const name = (p.full_name || '').toLowerCase()
        const team = (p.pro_team || '').toLowerCase()
        const pos = (p.position || '').toLowerCase()
        return name.includes(q) || team === q || pos === q
      })
      .slice(0, 15)
      .map((p) => {
        // Check if on roster
        let status = p.is_starter ? 'Starter' : p.is_free_agent ? 'Free Agent' : 'Bench'
        let proj = p.projected_points ?? 0
        if (lineup) {
          const isStarter = lineup.starters.some((s) => s.recommended_player.player_id === p.id)
          const isBench = lineup.bench.some((b) => b.player_id === p.id)
          if (isStarter) status = 'Starter'
          else if (isBench) status = 'Bench'
        }

        return {
          id: `player-${p.id}`,
          title: p.full_name,
          category: 'Player',
          player: p,
          status,
          proj,
          team: p.pro_team,
          pos: p.position,
        }
      })

    return [...matchedTabs, ...matchedPlayers]
  }, [query, navShortcuts, allPlayers, lineup])

  // Handle arrow keys
  const handleInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex((prev) => (prev + 1 < filteredItems.length ? prev + 1 : 0))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex((prev) => (prev - 1 >= 0 ? prev - 1 : filteredItems.length - 1))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      const selected = filteredItems[selectedIndex]
      if (selected) {
        handleSelectItem(selected)
      }
    }
  }

  const handleSelectItem = (item: any) => {
    if (item.category === 'Navigation') {
      onNavigateTab(item.tab)
      onClose()
    } else if (item.category === 'Player') {
      if (onSelectPlayerForCompare) {
        onSelectPlayerForCompare(item.player.id)
      }
      onNavigateTab('compare')
      onClose()
    }
  }

  if (!isOpen) return null

  return (
    <div className="palette-backdrop" onClick={onClose}>
      <div className="palette-modal" onClick={(e) => e.stopPropagation()}>
        {/* Search Header */}
        <div className="palette-header">
          <svg className="palette-search-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            ref={inputRef}
            type="text"
            className="palette-input"
            placeholder="Type player, matchup, or tab name... (e.g. Nacua, WR, Vegas)"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setSelectedIndex(0)
            }}
            onKeyDown={handleInputKeyDown}
          />
          <div className="palette-esc-badge" onClick={onClose} role="button" tabIndex={0}>
            ESC
          </div>
        </div>

        {/* Results Container */}
        <div className="palette-results" ref={resultsRef}>
          {filteredItems.length > 0 ? (
            filteredItems.map((item: any, idx) => {
              const isSelected = idx === selectedIndex
              return (
                <div
                  key={item.id}
                  className={`palette-item ${isSelected ? 'selected' : ''}`}
                  onClick={() => handleSelectItem(item)}
                  onMouseEnter={() => setSelectedIndex(idx)}
                >
                  {item.category === 'Navigation' ? (
                    <div className="palette-item-content">
                      <span className="palette-tab-icon">{item.icon}</span>
                      <div className="palette-item-text">
                        <span className="palette-item-title">{item.title}</span>
                        <span className="palette-item-sub">Jump to tab</span>
                      </div>
                      <span className="palette-action-pill">Go ↵</span>
                    </div>
                  ) : (
                    <div className="palette-item-content">
                      <NFLTeamLogo team={item.team} size={22} />
                      <div className="palette-item-text">
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span className="palette-item-title">{item.title}</span>
                          <span className="pill cyan" style={{ fontSize: '10px', padding: '1px 6px' }}>
                            {item.pos} • {item.team}
                          </span>
                          {item.status === 'Starter' && (
                            <span className="pill emerald" style={{ fontSize: '10px', padding: '1px 6px' }}>
                              ★ Starter
                            </span>
                          )}
                          {item.status === 'Bench' && (
                            <span className="pill amber" style={{ fontSize: '10px', padding: '1px 6px' }}>
                              Bench
                            </span>
                          )}
                        </div>
                        <span className="palette-item-sub">
                          {item.proj > 0 ? `Proj: ${item.proj.toFixed(1)} pts` : 'Player Directory'}
                        </span>
                      </div>
                      <span className="palette-action-pill">Compare ↵</span>
                    </div>
                  )}
                </div>
              )
            })
          ) : (
            <div className="palette-empty">
              <span>No matching players or views found for "{query}"</span>
            </div>
          )}
        </div>

        {/* Footer info */}
        <div className="palette-footer">
          <div className="palette-shortcuts-guide">
            <span><kbd>↑</kbd> <kbd>↓</kbd> Navigate</span>
            <span><kbd>↵</kbd> Select</span>
            <span><kbd>ESC</kbd> Close</span>
          </div>
          <div className="palette-branding">
            <span>APEX SPOTLIGHT</span>
          </div>
        </div>
      </div>
    </div>
  )
}
