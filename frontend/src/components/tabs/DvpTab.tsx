import React, { useState, useMemo, useEffect } from 'react'
import type {
  LeagueSummaryResponse,
  OptimizedLineupResult,
  DvPRecordItem,
  DvPStatusResponse,
} from '../../types'
import { NFLTeamLogo } from '../shared/NFLTeamLogo'
import { Tooltip } from '../shared/Tooltip'

export interface DvpTabProps {
  league?: LeagueSummaryResponse | null
  lineup?: OptimizedLineupResult | null
  selectedTeamId?: number | null
  onNavigateTab?: (tab: string) => void
}

export type DvpPositionMode = 'OVERALL' | 'QB' | 'RB' | 'WR' | 'TE'

export interface OverallDSTRecord {
  id: string
  pro_team: string
  team_name: string
  composite_rank: number // 1 (Best/Toughest Defense) to 32 (Most Vulnerable)
  rank_softness: number  // 1 (Softest Matchup) to 32 (Toughest Matchup)
  tier: string
  tier_label: string
  total_dk_fpa: number
  total_fd_fpa: number
  total_yds: number
  pass_yds: number
  rush_yds: number
  total_td: number
  pass_td: number
  rush_td: number
  sacks: number
  turnovers: number
  qb_rank: number
  rb_rank: number
  wr_rank: number
  te_rank: number
}

const TEAM_ALIASES: Record<string, string> = {
  ARZ: 'ARI',
  BLT: 'BAL',
  CLV: 'CLE',
  HST: 'HOU',
  JAC: 'JAX',
  KAN: 'KC',
  LVR: 'LV',
  OAK: 'LV',
  NEP: 'NE',
  NOS: 'NO',
  SFO: 'SF',
  TAM: 'TB',
  OTI: 'TEN',
  WAS: 'WSH',
}

function normalizeTeamKey(team?: string | null): string {
  if (!team) return ''
  const t = team.toUpperCase().trim()
  return TEAM_ALIASES[t] || t
}

export const DvpTab: React.FC<DvpTabProps> = ({
  league,
  lineup,
  selectedTeamId: _selectedTeamId,
  onNavigateTab: _onNavigateTab,
}) => {
  // Defense vs Position (DvP) state
  const [dvpPosition, setDvpPosition] = useState<DvpPositionMode>('OVERALL')
  const [allDvpRatings, setAllDvpRatings] = useState<DvPRecordItem[]>([])
  const [dvpStatus, setDvpStatus] = useState<DvPStatusResponse | null>(null)
  const [isLoadingDvp, setIsLoadingDvp] = useState<boolean>(false)
  const [isSyncingDvp, setIsSyncingDvp] = useState<boolean>(false)

  // Universal column sorting state (default OVERALL to #32 weakest defense at the top)
  const [dvpSortCol, setDvpSortCol] = useState<string>('composite_rank')
  const [dvpSortAsc, setDvpSortAsc] = useState<boolean>(false)

  const [dvpSyncMsg, setDvpSyncMsg] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [tierFilter, setTierFilter] = useState<'ALL' | 'SMASH' | 'FAVORABLE' | 'TOUGH' | 'LOCKDOWN' | 'ROSTER'>('ALL')

  // Fetch all 128 DvP records (all 32 teams x 4 positions)
  const fetchAllDvpData = async () => {
    setIsLoadingDvp(true)
    try {
      const [ratingsRes, statusRes] = await Promise.all([
        fetch('/api/analysis/dvp-ratings?position=ALL'),
        fetch('/api/analysis/dvp-status'),
      ])
      if (ratingsRes.ok) {
        const data: DvPRecordItem[] = await ratingsRes.json()
        setAllDvpRatings(data)
      }
      if (statusRes.ok) {
        const sData: DvPStatusResponse = await statusRes.json()
        setDvpStatus(sData)
      }
    } catch (err) {
      console.error('Failed to load DvP data:', err)
    } finally {
      setIsLoadingDvp(false)
    }
  }

  useEffect(() => {
    fetchAllDvpData()
  }, [])

  const handleSyncDvp = async () => {
    setIsSyncingDvp(true)
    setDvpSyncMsg(null)
    try {
      const res = await fetch('/api/analysis/dvp-sync', { method: 'POST' })
      if (res.ok) {
        const result = await res.json()
        setDvpSyncMsg(`✅ Synced ${result.records_updated} teams across all positions!`)
        await fetchAllDvpData()
      } else {
        setDvpSyncMsg('⚠️ Sync completed with cached baseline.')
      }
    } catch (err) {
      setDvpSyncMsg('❌ Sync encountered a network error.')
    } finally {
      setIsSyncingDvp(false)
      setTimeout(() => setDvpSyncMsg(null), 5000)
    }
  }

  // Identify user's rostered D/ST team if present
  const { rosteredDstTeam, rosteredDstIsStarter } = useMemo(() => {
    if (!lineup) return { rosteredDstTeam: null, rosteredDstIsStarter: false }
    for (const s of lineup.starters) {
      const p = s.recommended_player
      if (p.position === 'DST' || p.position === 'D/ST' || s.slot_name === 'DST') {
        return { rosteredDstTeam: normalizeTeamKey(p.pro_team), rosteredDstIsStarter: true }
      }
    }
    for (const b of lineup.bench) {
      if (b.position === 'DST' || b.position === 'D/ST') {
        return { rosteredDstTeam: normalizeTeamKey(b.pro_team), rosteredDstIsStarter: false }
      }
    }
    return { rosteredDstTeam: null, rosteredDstIsStarter: false }
  }, [lineup])

  // Map opponent teams faced by active roster
  const rosterOpponents = useMemo(() => {
    const map = new Map<string, Array<{ full_name: string; position: string; is_starter: boolean }>>()
    if (!lineup) return map
    for (const s of lineup.starters) {
      const p = s.recommended_player
      const opp = normalizeTeamKey(p.opponent)
      if (!opp) continue
      const list = map.get(opp) || []
      list.push({ full_name: p.full_name, position: p.position, is_starter: true })
      map.set(opp, list)
    }
    for (const b of lineup.bench) {
      const opp = normalizeTeamKey(b.opponent)
      if (!opp) continue
      const list = map.get(opp) || []
      list.push({ full_name: b.full_name, position: b.position, is_starter: false })
      map.set(opp, list)
    }
    return map
  }, [lineup])

  // Aggregate all 4 positions into 32 Composite Overall DST Records
  const overallDstRecords = useMemo(() => {
    if (allDvpRatings.length === 0) return []

    const teamMap = new Map<string, { pro_team: string; team_name: string; positions: Record<string, DvPRecordItem> }>()

    for (const r of allDvpRatings) {
      const t = r.pro_team.toUpperCase().trim()
      if (!teamMap.has(t)) {
        teamMap.set(t, { pro_team: t, team_name: r.team_name, positions: {} })
      }
      teamMap.get(t)!.positions[r.position] = r
    }

    const aggregated: Array<{
      pro_team: string
      team_name: string
      total_dk_fpa: number
      total_fd_fpa: number
      total_yds: number
      pass_yds: number
      rush_yds: number
      total_td: number
      pass_td: number
      rush_td: number
      sacks: number
      turnovers: number
      qb_rank: number
      rb_rank: number
      wr_rank: number
      te_rank: number
    }> = []

    teamMap.forEach((val) => {
      const qb = val.positions['QB']
      const rb = val.positions['RB']
      const wr = val.positions['WR']
      const te = val.positions['TE']

      const qbFpa = qb?.dk_fpa ?? 0
      const rbFpa = rb?.dk_fpa ?? 0
      const wrFpa = wr?.dk_fpa ?? 0
      const teFpa = te?.dk_fpa ?? 0
      const totalDk = qbFpa + rbFpa + wrFpa + teFpa

      const qbFd = qb?.fd_fpa ?? qbFpa
      const rbFd = rb?.fd_fpa ?? rbFpa
      const wrFd = wr?.fd_fpa ?? wrFpa
      const teFd = te?.fd_fpa ?? teFpa
      const totalFd = qbFd + rbFd + wrFd + teFd

      const qbSupp = qb?.supporting_stats || {}
      const rbSupp = rb?.supporting_stats || {}
      const wrSupp = wr?.supporting_stats || {}

      const passYds = qbSupp.pass_yds ?? 0
      const rushYds = (rbSupp.rush_yds ?? 0) + (qbSupp.qb_rush_yds ?? qbSupp.rush_yds ?? 0) + (wrSupp.rush_yds ?? 0)
      const totalYds = passYds + rushYds

      const passTd = qbSupp.pass_td ?? 0
      const rushTd = rbSupp.rush_td ?? 0
      const totalTd = passTd + rushTd

      const sacks = qbSupp.sacks ?? 0
      const turnovers = qbSupp.int ?? 0

      aggregated.push({
        pro_team: val.pro_team,
        team_name: val.team_name,
        total_dk_fpa: totalDk,
        total_fd_fpa: totalFd,
        total_yds: totalYds,
        pass_yds: passYds,
        rush_yds: rushYds,
        total_td: totalTd,
        pass_td: passTd,
        rush_td: rushTd,
        sacks,
        turnovers,
        qb_rank: qb?.rank_softness ?? 16,
        rb_rank: rb?.rank_softness ?? 16,
        wr_rank: wr?.rank_softness ?? 16,
        te_rank: te?.rank_softness ?? 16,
      })
    })

    // Sort by total_dk_fpa ascending: Lowest points allowed = Rank #1 (Toughest defense)
    aggregated.sort((a, b) => a.total_dk_fpa - b.total_dk_fpa)

    const totalCount = aggregated.length
    return aggregated.map((item, index) => {
      const compositeRank = index + 1 // #1 Toughest to #32 Most Vulnerable
      const softnessRank = totalCount - index // #1 Softest to #32 Toughest

      let tier = 'NEUTRAL'
      let tierLabel = '⚖️ Average Defense'
      if (compositeRank <= 6) {
        tier = 'LOCKDOWN'
        tierLabel = '🛡️ Elite Lockdown DST'
      } else if (compositeRank <= 14) {
        tier = 'FAVORABLE'
        tierLabel = '💪 Strong Defense'
      } else if (compositeRank <= 22) {
        tier = 'NEUTRAL'
        tierLabel = '⚖️ Average Defense'
      } else if (compositeRank <= 28) {
        tier = 'TOUGH'
        tierLabel = '⚠️ Vulnerable Defense'
      } else {
        tier = 'SMASH'
        tierLabel = '🚨 Bleeding Points'
      }

      return {
        id: `overall_${item.pro_team}`,
        pro_team: item.pro_team,
        team_name: item.team_name,
        composite_rank: compositeRank,
        rank_softness: softnessRank,
        tier,
        tier_label: tierLabel,
        total_dk_fpa: item.total_dk_fpa,
        total_fd_fpa: item.total_fd_fpa,
        total_yds: item.total_yds,
        pass_yds: item.pass_yds,
        rush_yds: item.rush_yds,
        total_td: item.total_td,
        pass_td: item.pass_td,
        rush_td: item.rush_td,
        sacks: item.sacks,
        turnovers: item.turnovers,
        qb_rank: item.qb_rank,
        rb_rank: item.rb_rank,
        wr_rank: item.wr_rank,
        te_rank: item.te_rank,
      } as OverallDSTRecord
    })
  }, [allDvpRatings])

  // Current single-position ratings (when viewing QB, RB, WR, or TE)
  const currentPosRatings = useMemo(() => {
    if (dvpPosition === 'OVERALL') return []
    return allDvpRatings.filter((r) => r.position === dvpPosition)
  }, [allDvpRatings, dvpPosition])

  // Universal helper to resolve sort value
  const getSortValue = (row: any, col: string): any => {
    if (col.startsWith('supp_')) {
      const key = col.replace('supp_', '')
      return row.supporting_stats?.[key] ?? 0
    }
    return row[col] ?? 0
  }

  // Universal column header sort toggle
  const handleSort = (colKey: string, defaultDesc: boolean = false) => {
    if (dvpSortCol === colKey) {
      // Toggle sort direction
      setDvpSortAsc(!dvpSortAsc)
    } else {
      // New column selected: use designated default direction
      setDvpSortCol(colKey)
      setDvpSortAsc(!defaultDesc)
    }
  }

  // Filtered and sorted records for Positional view
  const sortedPosRatings = useMemo(() => {
    let list = [...currentPosRatings]

    if (searchQuery) {
      const q = searchQuery.toLowerCase().trim()
      list = list.filter(
        (r) =>
          r.team_name.toLowerCase().includes(q) ||
          r.pro_team.toLowerCase().includes(q) ||
          r.tier_label.toLowerCase().includes(q)
      )
    }

    if (tierFilter === 'SMASH') {
      list = list.filter((r) => r.tier === 'SMASH')
    } else if (tierFilter === 'FAVORABLE') {
      list = list.filter((r) => r.tier === 'FAVORABLE')
    } else if (tierFilter === 'TOUGH') {
      list = list.filter((r) => r.tier === 'TOUGH')
    } else if (tierFilter === 'LOCKDOWN') {
      list = list.filter((r) => r.tier === 'LOCKDOWN')
    } else if (tierFilter === 'ROSTER') {
      list = list.filter((r) => {
        const norm = normalizeTeamKey(r.pro_team)
        const facing = rosterOpponents.get(norm) || []
        return facing.some((p) => p.position === dvpPosition)
      })
    }

    list.sort((a, b) => {
      const aVal = getSortValue(a, dvpSortCol)
      const bVal = getSortValue(b, dvpSortCol)
      if (typeof aVal === 'string') {
        return dvpSortAsc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal)
      }
      const numA = Number(aVal) || 0
      const numB = Number(bVal) || 0
      return dvpSortAsc ? numA - numB : numB - numA
    })

    return list
  }, [currentPosRatings, searchQuery, tierFilter, dvpSortCol, dvpSortAsc, rosterOpponents, dvpPosition])

  // Filtered and sorted records for Overall DST view
  const sortedOverallRecords = useMemo(() => {
    let list = [...overallDstRecords]

    if (searchQuery) {
      const q = searchQuery.toLowerCase().trim()
      list = list.filter(
        (r) =>
          r.team_name.toLowerCase().includes(q) ||
          r.pro_team.toLowerCase().includes(q) ||
          r.tier_label.toLowerCase().includes(q)
      )
    }

    if (tierFilter === 'SMASH') {
      list = list.filter((r) => r.tier === 'SMASH')
    } else if (tierFilter === 'FAVORABLE') {
      list = list.filter((r) => r.tier === 'FAVORABLE')
    } else if (tierFilter === 'TOUGH') {
      list = list.filter((r) => r.tier === 'TOUGH')
    } else if (tierFilter === 'LOCKDOWN') {
      list = list.filter((r) => r.tier === 'LOCKDOWN')
    } else if (tierFilter === 'ROSTER') {
      list = list.filter((r) => {
        const norm = normalizeTeamKey(r.pro_team)
        const facing = rosterOpponents.get(norm) || []
        return facing.length > 0 || rosteredDstTeam === norm
      })
    }

    list.sort((a, b) => {
      const aVal = getSortValue(a, dvpSortCol)
      const bVal = getSortValue(b, dvpSortCol)
      if (typeof aVal === 'string') {
        return dvpSortAsc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal)
      }
      const numA = Number(aVal) || 0
      const numB = Number(bVal) || 0
      return dvpSortAsc ? numA - numB : numB - numA
    })

    return list
  }, [overallDstRecords, searchQuery, tierFilter, dvpSortCol, dvpSortAsc, rosterOpponents, rosteredDstTeam])

  // KPI Quick Calculations
  const pulseKpis = useMemo(() => {
    if (dvpPosition === 'OVERALL') {
      if (overallDstRecords.length === 0) {
        return {
          title1: '🛡️ #1 Toughest Defense',
          val1: '—',
          desc1: 'Calculating composite defense...',
          team1: null as string | null,
          title2: '🚨 #32 Most Vulnerable DST',
          val2: '—',
          desc2: 'Calculating...',
          team2: null as string | null,
          title3: '📊 Avg Total FPA Allowed',
          val3: '0.0',
          desc3: 'Across all 4 offensive skill positions',
          title4: '⚔️ Starters Facing Top-8 Soft',
          val4: '0 Starters',
          desc4: 'Offensive starters with soft composite matchups',
        }
      }

      const toughest = overallDstRecords[0] // Lowest FPA
      const mostGenerous = overallDstRecords[overallDstRecords.length - 1] // Highest FPA
      const avgFpa = overallDstRecords.reduce((acc, r) => acc + r.total_dk_fpa, 0) / (overallDstRecords.length || 1)

      // Count starters facing bottom-8 defenses (rank_softness <= 8)
      let softStartersCount = 0
      for (const r of overallDstRecords) {
        if (r.rank_softness <= 8) {
          const norm = normalizeTeamKey(r.pro_team)
          const facing = rosterOpponents.get(norm) || []
          softStartersCount += facing.filter((p) => p.is_starter && p.position !== 'DST').length
        }
      }

      return {
        title1: '🚨 #32 Most Vulnerable Defense',
        val1: mostGenerous ? `${mostGenerous.team_name}` : '—',
        desc1: mostGenerous ? `Allows league-high ${mostGenerous.total_dk_fpa.toFixed(1)} Total FPA/g (${mostGenerous.total_yds.toFixed(0)} yds/g)` : '',
        team1: mostGenerous?.pro_team || null,
        title2: '🛡️ #1 Toughest Lockdown Defense',
        val2: toughest ? `${toughest.team_name}` : '—',
        desc2: toughest ? `Restricts to league-low ${toughest.total_dk_fpa.toFixed(1)} Total FPA/g (${toughest.total_yds.toFixed(0)} yds/g)` : '',
        team2: toughest?.pro_team || null,
        title3: '📊 Avg Total FPA Allowed',
        val3: `${avgFpa.toFixed(1)} pts/g`,
        desc3: 'League baseline fantasy points allowed across all positions',
        title4: '⚔️ Starters Facing Soft DSTs',
        val4: `${softStartersCount} Starters`,
        desc4: 'Active roster starters facing bottom-8 composite defenses',
      }
    }

    // Positional View KPIs
    if (currentPosRatings.length === 0) {
      return {
        title1: `🔥 #1 Softest ${dvpPosition} Matchup`,
        val1: '—',
        desc1: 'Calculating...',
        team1: null as string | null,
        title2: `🛑 #32 Toughest ${dvpPosition} Defense`,
        val2: '—',
        desc2: 'Calculating...',
        team2: null as string | null,
        title3: '📊 Positional Avg FPA',
        val3: '0.0',
        desc3: `NFL baseline fantasy scoring environment for ${dvpPosition}s`,
        title4: `⚔️ My Roster ${dvpPosition} Smash`,
        val4: '0',
        desc4: `Rostered ${dvpPosition}s facing top-8 soft defenses`,
      }
    }

    const sortedBySoft = [...currentPosRatings].sort((a, b) => a.rank_softness - b.rank_softness)
    const softest = sortedBySoft[0] || null
    const toughest = sortedBySoft[sortedBySoft.length - 1] || null
    const avg = currentPosRatings.reduce((acc, r) => acc + r.dk_fpa, 0) / (currentPosRatings.length || 1)

    let smashCount = 0
    for (const r of currentPosRatings) {
      if (r.rank_softness <= 8) {
        const norm = normalizeTeamKey(r.pro_team)
        const facing = rosterOpponents.get(norm) || []
        const posFacing = facing.filter((p) => p.position === dvpPosition)
        smashCount += posFacing.length
      }
    }

    return {
      title1: `🔥 #1 Softest ${dvpPosition} Matchup`,
      val1: softest ? `${softest.team_name}` : '—',
      desc1: softest ? `Allows ${softest.dk_fpa.toFixed(1)} Half-PPR / ${softest.fd_fpa ? softest.fd_fpa.toFixed(1) : '—'} Full-PPR FPA` : '',
      team1: softest?.pro_team || null,
      title2: `🛑 #32 Toughest ${dvpPosition} Defense`,
      val2: toughest ? `${toughest.team_name}` : '—',
      desc2: toughest ? `Restricts to ${toughest.dk_fpa.toFixed(1)} FPA (${toughest.vs_avg.toFixed(1)} vs avg)` : '',
      team2: toughest?.pro_team || null,
      title3: '📊 Positional Avg FPA',
      val3: `${avg.toFixed(1)} pts/g`,
      desc3: `NFL baseline fantasy scoring environment for ${dvpPosition}s`,
      title4: `⚔️ My Roster ${dvpPosition} Smash`,
      val4: `${smashCount} ${dvpPosition}s`,
      desc4: `Rostered ${dvpPosition}s facing top-8 soft defenses (Rank ≤ 8)`,
    }
  }, [dvpPosition, overallDstRecords, currentPosRatings, rosterOpponents])

// Prominent, high-contrast SVG sort indicator icon
const SortArrowIcon: React.FC<{ isActive: boolean; isAsc: boolean }> = ({ isActive, isAsc }) => {
  if (isActive) {
    return isAsc ? (
      <svg width="12" height="12" viewBox="0 0 12 12" fill="none" style={{ display: 'block' }}>
        <path d="M6 1.5L10.5 8.5H1.5L6 1.5Z" fill="#00f0ff" />
      </svg>
    ) : (
      <svg width="12" height="12" viewBox="0 0 12 12" fill="none" style={{ display: 'block' }}>
        <path d="M6 10.5L1.5 3.5H10.5L6 10.5Z" fill="#00f0ff" />
      </svg>
    )
  }

  // Inactive state: Both UP and DOWN arrows clearly visible and distinct
  return (
    <svg width="10" height="14" viewBox="0 0 10 14" fill="none" style={{ display: 'block' }}>
      <path d="M5 1L9 5.5H1L5 1Z" fill="#cbd5e1" />
      <path d="M5 13L1 8.5H9L5 13Z" fill="#cbd5e1" />
    </svg>
  )
}

  // Helper to render interactive sortable table header with prominent, dedicated sort arrows
  const renderSortTh = (title: string, colKey: string, defaultDesc: boolean = false, tooltipTerm?: string) => {
    const isActive = dvpSortCol === colKey

    return (
      <th
        key={colKey}
        onClick={() => handleSort(colKey, defaultDesc)}
        style={{
          cursor: 'pointer',
          userSelect: 'none',
          whiteSpace: 'nowrap',
          color: isActive ? 'var(--accent-cyan)' : undefined,
          transition: 'all 0.15s ease',
        }}
        title={`Click anywhere to sort by ${title} ${
          isActive
            ? dvpSortAsc
              ? '(Currently Low to High, click for High to Low)'
              : '(Currently High to Low, click for Low to High)'
            : defaultDesc
            ? '(High to Low first)'
            : '(Low to High first)'
        }`}
      >
        <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', gap: '6px' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
            {tooltipTerm ? (
              <Tooltip term={tooltipTerm}>
                <span
                  style={{
                    borderBottom: '1px dotted rgba(6, 182, 212, 0.65)',
                    cursor: 'help',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '2px',
                  }}
                  title="Click metric name for definition"
                >
                  <span>{title}</span>
                  <span style={{ fontSize: '9px', opacity: 0.75, color: '#38bdf8' }}>ℹ</span>
                </span>
              </Tooltip>
            ) : (
              <span>{title}</span>
            )}
          </div>

          <button
            type="button"
            className={`intel-dvp-sort-btn ${isActive ? 'active' : ''}`}
            onClick={(e) => {
              e.preventDefault()
              e.stopPropagation()
              handleSort(colKey, defaultDesc)
            }}
            title={
              isActive
                ? `Sorted ${dvpSortAsc ? '▲ (Low to High)' : '▼ (High to Low)'}. Click to reverse.`
                : `Click to sort by ${title} ${defaultDesc ? '▼ (High to Low)' : '▲ (Low to High)'}`
            }
            aria-label={`Sort by ${title}`}
          >
            <SortArrowIcon isActive={isActive} isAsc={dvpSortAsc} />
          </button>
        </div>
      </th>
    )
  }

  return (
    <div className="intel-container" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* 1. EXECUTIVE HERO HEADER */}
      <div className="intel-hero-card">
        <div className="intel-hero-top">
          <div className="intel-title-group">
            <div className="intel-icon-badge" style={{ background: 'linear-gradient(135deg, #0ea5e9, #6366f1)', color: '#fff' }}>
              🛡️
            </div>
            <div>
              <h2 className="intel-heading">DEFENSES VS POSITION (DvP)</h2>
              <p className="intel-subtitle">
                32-team composite defensive rankings, positional Fantasy Points Allowed (Half-PPR & Full-PPR), and active roster leverage.
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span className="pill cyan" style={{ fontWeight: 700 }}>
              Week {league?.current_week || 2} DvP Matrix
            </span>
            <button
              type="button"
              onClick={handleSyncDvp}
              disabled={isSyncingDvp}
              className="btn btn-primary btn-sm"
              style={{ padding: '6px 14px', fontSize: '12px', fontWeight: 700 }}
            >
              {isSyncingDvp ? '⏳ Syncing Feed...' : '🔄 Sync DvP Feed'}
            </button>
          </div>
        </div>
      </div>

      {/* 2. BASELINE STATUS & METHODOLOGY BANNER */}
      <div className="intel-dvp-banner">
        <div className="intel-dvp-banner-content">
          <div className="intel-dvp-banner-title">
            <span>🛡️ NFL Defense vs Position (DvP) Fantasy Points Allowed (FPA) Calibration</span>
            <span className="pill cyan" style={{ fontSize: '10px' }}>Half-PPR (FanDuel) & Full-PPR (ESPN)</span>
          </div>
          <p className="intel-dvp-banner-text">
            Rankings evaluate defensive generosity per position group and overall as a composite unit. For <strong>Week {league?.current_week || 2}</strong>, ratings blend realized game data with the weighted 2025-26 baseline. Click any column header to sort high-to-low or low-to-high.
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginTop: '6px' }}>
            <span className="pill purple" style={{ fontSize: '10.5px' }}>
              ℹ️ Status: {dvpStatus?.is_baseline ? '2025-26 Weighted Baseline Active' : 'Current Season Calibrated'}
            </span>
            <span className="pill zinc" style={{ fontSize: '10.5px' }}>
              2026-27 Sample: {dvpStatus?.sample_games_current ?? 0} games
            </span>
            {dvpStatus?.last_updated && (
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                Last Synced: {new Date(dvpStatus.last_updated).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
              </span>
            )}
            {dvpSyncMsg && (
              <span style={{ fontSize: '11.5px', fontWeight: 700, color: 'var(--accent-emerald)' }}>
                {dvpSyncMsg}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* 3. POSITIONAL / OVERALL KPI PULSE STRIP */}
      <div className="intel-pulse-grid">
        <div className="intel-pulse-card">
          <div className="intel-pulse-label">
            <span>{pulseKpis.title1}</span>
          </div>
          <div className="intel-pulse-val" style={{ color: 'var(--accent-emerald)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            {pulseKpis.team1 && <NFLTeamLogo team={pulseKpis.team1} size={22} />}
            <span>{pulseKpis.val1}</span>
          </div>
          <div className="intel-pulse-desc">{pulseKpis.desc1}</div>
        </div>

        <div className="intel-pulse-card">
          <div className="intel-pulse-label">
            <span>{pulseKpis.title2}</span>
          </div>
          <div className="intel-pulse-val" style={{ color: 'var(--accent-rose)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            {pulseKpis.team2 && <NFLTeamLogo team={pulseKpis.team2} size={22} />}
            <span>{pulseKpis.val2}</span>
          </div>
          <div className="intel-pulse-desc">{pulseKpis.desc2}</div>
        </div>

        <div className="intel-pulse-card">
          <div className="intel-pulse-label">
            <span>{pulseKpis.title3}</span>
          </div>
          <div className="intel-pulse-val" style={{ color: 'var(--accent-cyan)' }}>
            {pulseKpis.val3}
          </div>
          <div className="intel-pulse-desc">{pulseKpis.desc3}</div>
        </div>

        <div className="intel-pulse-card">
          <div className="intel-pulse-label">
            <span>{pulseKpis.title4}</span>
          </div>
          <div className="intel-pulse-val" style={{ color: 'var(--accent-amber)' }}>
            {pulseKpis.val4}
          </div>
          <div className="intel-pulse-desc">{pulseKpis.desc4}</div>
        </div>
      </div>

      {/* 4. CONTROLS: POSITION SELECTOR (OVERALL + QB/RB/WR/TE), TIER FILTERS & SEARCH */}
      <div className="intel-filter-bar" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          {/* Position Selector with OVERALL DST */}
          <div className="intel-dvp-pos-selector">
            {(['OVERALL', 'QB', 'RB', 'WR', 'TE'] as const).map((pos) => (
              <button
                key={pos}
                type="button"
                onClick={() => {
                  setDvpPosition(pos)
                  if (pos === 'OVERALL') {
                    setDvpSortCol('composite_rank')
                    setDvpSortAsc(false)
                  } else {
                    setDvpSortCol('rank_softness')
                    setDvpSortAsc(true)
                  }
                }}
                className={`intel-dvp-pos-btn ${dvpPosition === pos ? 'active' : ''}`}
                style={{ fontSize: '13px', padding: '8px 16px', fontWeight: dvpPosition === pos ? 800 : 600 }}
              >
                {pos === 'OVERALL'
                  ? '🏆 OVERALL DST'
                  : pos === 'QB'
                  ? '🎯 QB Matchups'
                  : pos === 'RB'
                  ? '🏃 RB Matchups'
                  : pos === 'WR'
                  ? '⚡ WR Matchups'
                  : '🛡️ TE Matchups'}
              </button>
            ))}
          </div>

          {/* Tier Quick Filter Buttons */}
          <div style={{ display: 'flex', gap: '4px' }}>
            {(['ALL', 'SMASH', 'FAVORABLE', 'TOUGH', 'LOCKDOWN', 'ROSTER'] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTierFilter(t)}
                className={`btn btn-sm ${tierFilter === t ? 'btn-primary' : 'btn-secondary'}`}
                style={{ padding: '4px 10px', fontSize: '11px' }}
              >
                {t === 'ALL'
                  ? 'All 32 Teams'
                  : t === 'SMASH'
                  ? '🚀 Smash'
                  : t === 'FAVORABLE'
                  ? '👍 Strong'
                  : t === 'TOUGH'
                  ? '⚠️ Tough'
                  : t === 'LOCKDOWN'
                  ? '🛑 Lockdown'
                  : dvpPosition === 'OVERALL'
                  ? '⚔️ My Matchups'
                  : `⚔️ My ${dvpPosition} Matchups`}
              </button>
            ))}
          </div>
        </div>

        {/* Search Bar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Filter by team (e.g. KC, Bills, Ravens)..."
            className="intel-search-input"
            style={{ width: '240px' }}
          />
        </div>
      </div>

      {/* 5. INTERACTIVE SORTABLE MATRIX TABLE */}
      {isLoadingDvp ? (
        <div className="card" style={{ textAlign: 'center', padding: '60px', color: 'var(--text-muted)' }}>
          <div style={{ fontSize: '32px', marginBottom: '12px' }}>⏳</div>
          Loading Defense vs Position ratings and composite rankings...
        </div>
      ) : (dvpPosition === 'OVERALL' ? sortedOverallRecords.length === 0 : sortedPosRatings.length === 0) ? (
        <div className="card" style={{ textAlign: 'center', padding: '48px', color: 'var(--text-muted)' }}>
          No defensive teams found matching your filter criteria.
        </div>
      ) : dvpPosition === 'OVERALL' ? (
        /* ========================================================================= */
        /* VIEW A: OVERALL COMPOSITE DST LEADERBOARD                                 */
        /* ========================================================================= */
        <div className="intel-dvp-table-wrap">
          <table className="intel-dvp-table">
            <thead>
              <tr>
                {renderSortTh('Overall DST Rank', 'composite_rank', true)}
                {renderSortTh('Defensive Team', 'team_name', false)}
                {renderSortTh('Defense Tier', 'tier', false)}
                <th>My Roster Exposure</th>
                {renderSortTh('Total Half-PPR FPA', 'total_dk_fpa', true, 'DVP_FPA')}
                {renderSortTh('Total Full-PPR FPA', 'total_fd_fpa', true, 'DVP_FULL_PPR_FPA')}
                {renderSortTh('Total Yds/G', 'total_yds', true)}
                {renderSortTh('Pass Yds/G', 'pass_yds', true)}
                {renderSortTh('Rush Yds/G', 'rush_yds', true)}
                {renderSortTh('Total TDs/G', 'total_td', true)}
                {renderSortTh('Sacks/G', 'sacks', true)}
                {renderSortTh('Turnovers/G', 'turnovers', true)}
                <th style={{ whiteSpace: 'nowrap' }}>Positional Softness (QB / RB / WR / TE)</th>
              </tr>
            </thead>
            <tbody>
              {sortedOverallRecords.map((row) => {
                const normProTeam = normalizeTeamKey(row.pro_team)
                const facingPlayers = rosterOpponents.get(normProTeam) || []
                const hasRosteredDst = rosteredDstTeam === normProTeam
                const facingStarters = facingPlayers.filter((p) => p.is_starter && p.position !== 'DST')
                const facingBench = facingPlayers.filter((p) => !p.is_starter && p.position !== 'DST')
                const isFacing = facingStarters.length > 0 || hasRosteredDst

                return (
                  <tr key={row.id} className={isFacing ? 'roster-facing' : ''}>
                    {/* Overall DST Composite Rank */}
                    <td>
                      <span
                        className={`pill ${
                          row.composite_rank <= 6
                            ? 'emerald'
                            : row.composite_rank <= 14
                            ? 'cyan'
                            : row.composite_rank <= 22
                            ? 'zinc'
                            : row.composite_rank <= 28
                            ? 'amber'
                            : 'rose'
                        }`}
                        style={{ fontWeight: 800, fontSize: '11px', minWidth: '46px', justifyContent: 'center' }}
                      >
                        #{row.composite_rank}
                      </span>
                    </td>

                    {/* Defensive Team */}
                    <td>
                      <div className="intel-dvp-team-cell">
                        <NFLTeamLogo team={row.pro_team} size={24} />
                        <div>
                          <strong style={{ color: 'var(--text-primary)', fontSize: '13px' }}>
                            {row.team_name}
                          </strong>
                          <span style={{ fontSize: '10.5px', color: 'var(--text-muted)', marginLeft: '4px' }}>
                            ({row.pro_team})
                          </span>
                        </div>
                      </div>
                    </td>

                    {/* Matchup Tier */}
                    <td>
                      <span
                        className={`pill ${
                          row.tier === 'LOCKDOWN'
                            ? 'emerald'
                            : row.tier === 'FAVORABLE'
                            ? 'cyan'
                            : row.tier === 'NEUTRAL'
                            ? 'zinc'
                            : row.tier === 'TOUGH'
                            ? 'amber'
                            : 'rose'
                        }`}
                        style={{ fontSize: '10px', fontWeight: 800 }}
                      >
                        {row.tier_label}
                      </span>
                    </td>

                    {/* My Roster Exposure (Overall DST) */}
                    <td>
                      {hasRosteredDst ? (
                        <span
                          className="pill emerald"
                          style={{ fontSize: '10px', fontWeight: 800, display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                        >
                          🛡️ YOUR D/ST {rosteredDstIsStarter ? '[STARTER]' : '[BENCH]'}
                        </span>
                      ) : facingStarters.length > 0 ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                          <span
                            className="pill cyan"
                            style={{ fontSize: '10px', fontWeight: 700 }}
                            title={`Active Starters facing this defense: ${facingStarters.map((p) => `${p.full_name} (${p.position})`).join(', ')}`}
                          >
                            ⚔️ {facingStarters.length} Starter{facingStarters.length > 1 ? 's' : ''} ({facingStarters.map((p) => `${p.full_name.split(' ').pop()} ${p.position}`).join(', ')})
                          </span>
                          {facingBench.length > 0 && (
                            <span style={{ fontSize: '9.5px', color: 'var(--text-muted)' }}>
                              +{facingBench.length} Bench ({facingBench.map((p) => `${p.full_name.split(' ').pop()} ${p.position}`).join(', ')})
                            </span>
                          )}
                        </div>
                      ) : (
                        <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>—</span>
                      )}
                    </td>

                    {/* Total Half-PPR FPA (FanDuel) */}
                    <td>
                      <strong
                        className="intel-dvp-val-mono"
                        style={{
                          color:
                            row.composite_rank <= 6
                              ? 'var(--accent-emerald)'
                              : row.composite_rank >= 27
                              ? 'var(--accent-rose)'
                              : 'var(--text-primary)',
                          fontSize: '13.5px',
                        }}
                      >
                        {row.total_dk_fpa.toFixed(1)}
                      </strong>
                    </td>

                    {/* Total Full-PPR FPA (ESPN) */}
                    <td>
                      <span className="intel-dvp-val-mono" style={{ color: 'var(--text-secondary)' }}>
                        {row.total_fd_fpa ? row.total_fd_fpa.toFixed(1) : '—'}
                      </span>
                    </td>

                    {/* Total Yds/G (Pass + Rush) */}
                    <td>
                      <span className="intel-dvp-val-mono" style={{ color: 'var(--text-primary)' }}>
                        {row.total_yds ? `${row.total_yds.toFixed(0)} yds` : '—'}
                      </span>
                    </td>

                    {/* Pass Yds/G */}
                    <td>{row.pass_yds ? `${row.pass_yds.toFixed(0)} yds` : '—'}</td>

                    {/* Rush Yds/G */}
                    <td>{row.rush_yds ? `${row.rush_yds.toFixed(0)} yds` : '—'}</td>

                    {/* Total TDs/G */}
                    <td>
                      <span style={{ fontWeight: 700 }}>
                        {row.total_td ? row.total_td.toFixed(1) : '—'}
                      </span>
                    </td>

                    {/* Sacks/G */}
                    <td>
                      <span style={{ color: row.sacks >= 2.5 ? 'var(--accent-emerald)' : 'inherit', fontWeight: row.sacks >= 2.5 ? 700 : 400 }}>
                        {row.sacks ? row.sacks.toFixed(1) : '—'}
                      </span>
                    </td>

                    {/* Turnovers/G */}
                    <td>{row.turnovers ? row.turnovers.toFixed(1) : '—'}</td>

                    {/* Positional Softness Matrix (QB, RB, WR, TE) */}
                    <td>
                      <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                        <span
                          className={`pill ${row.qb_rank <= 8 ? 'emerald' : row.qb_rank >= 25 ? 'rose' : 'zinc'}`}
                          style={{ fontSize: '9.5px', padding: '1px 5px', fontWeight: 700 }}
                          title={`QB Softness Rank #${row.qb_rank} (${row.qb_rank <= 8 ? 'Soft' : row.qb_rank >= 25 ? 'Tough' : 'Neutral'})`}
                        >
                          QB #{row.qb_rank}
                        </span>
                        <span
                          className={`pill ${row.rb_rank <= 8 ? 'emerald' : row.rb_rank >= 25 ? 'rose' : 'zinc'}`}
                          style={{ fontSize: '9.5px', padding: '1px 5px', fontWeight: 700 }}
                          title={`RB Softness Rank #${row.rb_rank} (${row.rb_rank <= 8 ? 'Soft' : row.rb_rank >= 25 ? 'Tough' : 'Neutral'})`}
                        >
                          RB #{row.rb_rank}
                        </span>
                        <span
                          className={`pill ${row.wr_rank <= 8 ? 'emerald' : row.wr_rank >= 25 ? 'rose' : 'zinc'}`}
                          style={{ fontSize: '9.5px', padding: '1px 5px', fontWeight: 700 }}
                          title={`WR Softness Rank #${row.wr_rank} (${row.wr_rank <= 8 ? 'Soft' : row.wr_rank >= 25 ? 'Tough' : 'Neutral'})`}
                        >
                          WR #{row.wr_rank}
                        </span>
                        <span
                          className={`pill ${row.te_rank <= 8 ? 'emerald' : row.te_rank >= 25 ? 'rose' : 'zinc'}`}
                          style={{ fontSize: '9.5px', padding: '1px 5px', fontWeight: 700 }}
                          title={`TE Softness Rank #${row.te_rank} (${row.te_rank <= 8 ? 'Soft' : row.te_rank >= 25 ? 'Tough' : 'Neutral'})`}
                        >
                          TE #{row.te_rank}
                        </span>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ) : (
        /* ========================================================================= */
        /* VIEW B: POSITIONAL DVP MATRIX (QB / RB / WR / TE)                         */
        /* ========================================================================= */
        <div className="intel-dvp-table-wrap">
          <table className="intel-dvp-table">
            <thead>
              <tr>
                {renderSortTh('Softness Rank', 'rank_softness', false)}
                {renderSortTh('Defensive Team', 'team_name', false)}
                {renderSortTh('Matchup Tier', 'tier', false)}
                <th>My Roster Exposure ({dvpPosition})</th>
                {renderSortTh('Half-PPR FPA (FanDuel)', 'dk_fpa', true, 'DVP_FPA')}
                {renderSortTh('Full-PPR FPA (ESPN Fantasy)', 'fd_fpa', true, 'DVP_FULL_PPR_FPA')}
                {renderSortTh('vs Pos Avg', 'vs_avg', true, 'DVP_VS_AVG')}
                {renderSortTh('2025-26 Base', 'prior_season_fpa', true, 'DVP_BASELINE')}
                {renderSortTh('2026-27 Curr', 'current_season_fpa', true)}
                {renderSortTh('L4 Trend', 'trend', false)}

                {/* Position-Specific Stat Columns with universal bidirectional sorting */}
                {dvpPosition === 'QB' && (
                  <>
                    {renderSortTh('Pass Yds/G', 'supp_pass_yds', true)}
                    {renderSortTh('Pass TD/G', 'supp_pass_td', true)}
                    {renderSortTh('Sacks/G', 'supp_sacks', true)}
                    {renderSortTh('Rush Yds/G', 'supp_qb_rush_yds', true)}
                  </>
                )}
                {dvpPosition === 'RB' && (
                  <>
                    {renderSortTh('Rush Yds/G', 'supp_rush_yds', true)}
                    {renderSortTh('Rush TD/G', 'supp_rush_td', true)}
                    {renderSortTh('Targets/G', 'supp_targets', true)}
                    {renderSortTh('Rec Yds/G', 'supp_rec_yds', true)}
                  </>
                )}
                {dvpPosition === 'WR' && (
                  <>
                    {renderSortTh('Rec Yds/G', 'supp_rec_yds', true)}
                    {renderSortTh('Rec TD/G', 'supp_rec_td', true)}
                    {renderSortTh('Targets/G', 'supp_targets', true)}
                    {renderSortTh('Rec/G', 'supp_rec', true)}
                  </>
                )}
                {dvpPosition === 'TE' && (
                  <>
                    {renderSortTh('Rec Yds/G', 'supp_rec_yds', true)}
                    {renderSortTh('Rec TD/G', 'supp_rec_td', true)}
                    {renderSortTh('Targets/G', 'supp_targets', true)}
                    {renderSortTh('Rec/G', 'supp_rec', true)}
                  </>
                )}
              </tr>
            </thead>
            <tbody>
              {sortedPosRatings.map((row) => {
                const normProTeam = normalizeTeamKey(row.pro_team)
                const facingPlayers = rosterOpponents.get(normProTeam) || []
                // Strictly filter to only roster players matching the current position category
                const posFacing = facingPlayers.filter((p) => p.position === dvpPosition)

                return (
                  <tr key={row.id} className={posFacing.length > 0 ? 'roster-facing' : ''}>
                    {/* Softness Rank */}
                    <td>
                      <span
                        className={`pill ${
                          row.rank_softness <= 8
                            ? 'emerald'
                            : row.rank_softness <= 16
                            ? 'cyan'
                            : row.rank_softness <= 24
                            ? 'amber'
                            : 'rose'
                        }`}
                        style={{ fontWeight: 800, fontSize: '11px', minWidth: '46px', justifyContent: 'center' }}
                      >
                        #{row.rank_softness}
                      </span>
                    </td>

                    {/* Defensive Team */}
                    <td>
                      <div className="intel-dvp-team-cell">
                        <NFLTeamLogo team={row.pro_team} size={24} />
                        <div>
                          <strong style={{ color: 'var(--text-primary)', fontSize: '13px' }}>
                            {row.team_name}
                          </strong>
                          <span style={{ fontSize: '10.5px', color: 'var(--text-muted)', marginLeft: '4px' }}>
                            ({row.pro_team})
                          </span>
                        </div>
                      </div>
                    </td>

                    {/* Tier */}
                    <td>
                      <span
                        className={`pill ${
                          row.tier === 'SMASH'
                            ? 'emerald'
                            : row.tier === 'FAVORABLE'
                            ? 'cyan'
                            : row.tier === 'TOUGH'
                            ? 'amber'
                            : row.tier === 'LOCKDOWN'
                            ? 'rose'
                            : 'zinc'
                        }`}
                        style={{ fontSize: '10px', fontWeight: 800 }}
                      >
                        {row.tier_label}
                      </span>
                    </td>

                    {/* My Roster Exposure (Position-Specific Only) */}
                    <td>
                      {posFacing.length > 0 ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                          {posFacing.map((p) => (
                            <span
                              key={`${p.full_name}-${p.is_starter ? 'start' : 'bench'}`}
                              className={`pill ${p.is_starter ? 'cyan' : 'zinc'}`}
                              style={{
                                fontSize: '10px',
                                fontWeight: 700,
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '5px',
                                width: 'fit-content',
                              }}
                              title={`${p.full_name} (${p.is_starter ? 'Active Starter' : 'Bench'}) vs ${row.team_name}`}
                            >
                              <span>{p.is_starter ? '⚔️' : '🪑'}</span>
                              <span>{p.full_name}</span>
                              <span style={{ fontSize: '9px', opacity: 0.85, fontWeight: 800 }}>
                                [{p.is_starter ? 'STARTER' : 'BENCH'}]
                              </span>
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>—</span>
                      )}
                    </td>

                    {/* Half-PPR FPA (FanDuel) */}
                    <td>
                      <strong
                        className="intel-dvp-val-mono"
                        style={{
                          color:
                            row.rank_softness <= 8
                              ? 'var(--accent-emerald)'
                              : row.rank_softness >= 25
                              ? 'var(--accent-rose)'
                              : 'var(--text-primary)',
                          fontSize: '13.5px',
                        }}
                      >
                        {row.dk_fpa.toFixed(1)}
                      </strong>
                    </td>

                    {/* Full-PPR FPA (ESPN) */}
                    <td>
                      <span className="intel-dvp-val-mono" style={{ color: 'var(--text-secondary)' }}>
                        {row.fd_fpa ? row.fd_fpa.toFixed(1) : '—'}
                      </span>
                    </td>

                    {/* vs Average */}
                    <td>
                      <span
                        className="intel-dvp-val-mono"
                        style={{
                          color:
                            row.vs_avg > 0
                              ? 'var(--accent-emerald)'
                              : row.vs_avg < 0
                              ? 'var(--accent-rose)'
                              : 'var(--text-muted)',
                        }}
                      >
                        {row.vs_avg > 0 ? `+${row.vs_avg.toFixed(1)}` : row.vs_avg.toFixed(1)}
                      </span>
                    </td>

                    {/* Prior Season Baseline */}
                    <td>
                      <span style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                        {row.prior_season_fpa ? row.prior_season_fpa.toFixed(1) : '—'}
                      </span>
                    </td>

                    {/* Current Season */}
                    <td>
                      <span style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                        {row.sample_games_current > 0 && row.current_season_fpa
                          ? row.current_season_fpa.toFixed(1)
                          : 'Stabilizing...'}
                      </span>
                    </td>

                    {/* Trend */}
                    <td>
                      <span
                        className={`pill ${
                          row.trend === 'UP' ? 'emerald' : row.trend === 'DOWN' ? 'rose' : 'zinc'
                        }`}
                        style={{ fontSize: '10px', padding: '1px 6px', fontWeight: 700 }}
                      >
                        {row.trend === 'UP' ? '📈 Softening' : row.trend === 'DOWN' ? '📉 Stiffening' : '⚖️ Stable'}
                      </span>
                    </td>

                    {/* Position-Specific Key Allowed Stats */}
                    {dvpPosition === 'QB' && (
                      <>
                        <td>{row.supporting_stats?.pass_yds ? `${row.supporting_stats.pass_yds.toFixed(0)} yds` : '—'}</td>
                        <td>{row.supporting_stats?.pass_td ? row.supporting_stats.pass_td.toFixed(2) : '—'}</td>
                        <td>{row.supporting_stats?.sacks ? row.supporting_stats.sacks.toFixed(1) : '—'}</td>
                        <td>
                          {row.supporting_stats?.qb_rush_yds !== undefined
                            ? `${row.supporting_stats.qb_rush_yds.toFixed(0)} yds`
                            : row.supporting_stats?.rush_yds !== undefined
                            ? `${row.supporting_stats.rush_yds.toFixed(0)} yds`
                            : '—'}
                        </td>
                      </>
                    )}
                    {dvpPosition === 'RB' && (
                      <>
                        <td>{row.supporting_stats?.rush_yds ? `${row.supporting_stats.rush_yds.toFixed(0)} yds` : '—'}</td>
                        <td>{row.supporting_stats?.rush_td ? row.supporting_stats.rush_td.toFixed(2) : '—'}</td>
                        <td>{row.supporting_stats?.targets ? row.supporting_stats.targets.toFixed(1) : '—'}</td>
                        <td>{row.supporting_stats?.rec_yds ? `${row.supporting_stats.rec_yds.toFixed(0)} yds` : '—'}</td>
                      </>
                    )}
                    {dvpPosition === 'WR' && (
                      <>
                        <td>{row.supporting_stats?.rec_yds ? `${row.supporting_stats.rec_yds.toFixed(0)} yds` : '—'}</td>
                        <td>{row.supporting_stats?.rec_td ? row.supporting_stats.rec_td.toFixed(2) : '—'}</td>
                        <td>{row.supporting_stats?.targets ? row.supporting_stats.targets.toFixed(1) : '—'}</td>
                        <td>{row.supporting_stats?.rec ? row.supporting_stats.rec.toFixed(1) : '—'}</td>
                      </>
                    )}
                    {dvpPosition === 'TE' && (
                      <>
                        <td>{row.supporting_stats?.rec_yds ? `${row.supporting_stats.rec_yds.toFixed(0)} yds` : '—'}</td>
                        <td>{row.supporting_stats?.rec_td ? row.supporting_stats.rec_td.toFixed(2) : '—'}</td>
                        <td>{row.supporting_stats?.targets ? row.supporting_stats.targets.toFixed(1) : '—'}</td>
                        <td>{row.supporting_stats?.rec ? row.supporting_stats.rec.toFixed(1) : '—'}</td>
                      </>
                    )}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
