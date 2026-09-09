import React, { useState, useMemo, useEffect } from 'react'
import type {
  WRCBMatchupAnalysis,
  VegasIntelligenceResponse,
  VegasGameEnvironment,
  OptimizedLineupResult,
  LeagueSummaryResponse,
  MatchupResponseItem,
  StartSitEvaluation,
  SlotAssignment,
  H2HTaleOfTheTapeResponse,
  DvPRecordItem,
  DvPStatusResponse,
  PlayerMarketSentimentItem,
} from '../../types'
import { MatchupStarRating, getMatchupStars, getMatchupTierInfo } from '../shared/MatchupStarRating'
import { InjuryStatusPill } from '../shared/InjuryStatusPill'
import { Tooltip } from '../shared/Tooltip'
import { NFLTeamLogo } from '../shared/NFLTeamLogo'

export interface IntelTabProps {
  lineup?: OptimizedLineupResult | null
  league?: LeagueSummaryResponse | null
  matchups?: MatchupResponseItem[]
  wrcbData: WRCBMatchupAnalysis[]
  vegasData: VegasIntelligenceResponse | null
  isLoadingWrcb: boolean
  isLoadingVegas: boolean
  onRefresh: () => void
  onCompareStarterWithBench?: (starter: StartSitEvaluation) => void
  onCompareBenchWithStarter?: (bench: StartSitEvaluation) => void
  onSelectTab?: (tab: string) => void
  selectedTeamId?: number | null
}

type SubViewType = 'starters' | 'bench' | 'opportunities' | 'market' | 'wrcb' | 'vegas' | 'dvp'

export const IntelTab: React.FC<IntelTabProps> = ({
  lineup,
  league,
  matchups = [],
  wrcbData,
  vegasData,
  isLoadingWrcb,
  isLoadingVegas,
  onRefresh,
  onCompareStarterWithBench,
  onCompareBenchWithStarter,
  onSelectTab,
  selectedTeamId,
}) => {
  // Default directly to starting lineup matchups as requested!
  const [subView, setSubView] = useState<SubViewType>('starters')
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [posFilter, setPosFilter] = useState<string>('ALL')
  const [wrcbTagFilter, setWrcbTagFilter] = useState<string>('ALL')
  const [scriptFilter, setScriptFilter] = useState<string>('ALL')

  // Defense vs Position (DvP) state
  const [dvpPosition, setDvpPosition] = useState<'QB' | 'RB' | 'WR' | 'TE'>('QB')
  const [dvpRatings, setDvpRatings] = useState<DvPRecordItem[]>([])
  const [dvpStatus, setDvpStatus] = useState<DvPStatusResponse | null>(null)
  const [isLoadingDvp, setIsLoadingDvp] = useState<boolean>(false)
  const [isSyncingDvp, setIsSyncingDvp] = useState<boolean>(false)
  const [dvpSortCol, setDvpSortCol] = useState<'rank_softness' | 'rank_defense' | 'dk_fpa' | 'vs_avg' | 'team_name'>('rank_softness')
  const [dvpSortAsc, setDvpSortAsc] = useState<boolean>(true)
  const [dvpSyncMsg, setDvpSyncMsg] = useState<string | null>(null)

  // Positional Tale of the Tape state
  const [taleData, setTaleData] = useState<H2HTaleOfTheTapeResponse | null>(null)
  const [isLoadingTale, setIsLoadingTale] = useState<boolean>(false)
  const [showTaleOfTheTape, setShowTaleOfTheTape] = useState<boolean>(true)

  // Dedicated current week matchups state ensuring weekly matchup opponent is always available
  const [currentWeekMatchups, setCurrentWeekMatchups] = useState<MatchupResponseItem[]>([])

  // Prediction Market Buzz & Starter Battles state
  const [marketBuzz, setMarketBuzz] = useState<PlayerMarketSentimentItem[]>([])
  const [isLoadingMarket, setIsLoadingMarket] = useState<boolean>(false)

  useEffect(() => {
    const fetchMarketBuzz = async () => {
      setIsLoadingMarket(true)
      try {
        const week = league?.current_week || 1
        const res = await fetch(`/api/analysis/market-sentiment/buzz?week=${week}`)
        if (res.ok) {
          const data: PlayerMarketSentimentItem[] = await res.json()
          setMarketBuzz(data)
        }
      } catch (err) {
        console.error('Failed to load market sentiment buzz:', err)
      } finally {
        setIsLoadingMarket(false)
      }
    }
    fetchMarketBuzz()
  }, [league?.current_week])

  useEffect(() => {
    const fetchTale = async () => {
      setIsLoadingTale(true)
      try {
        const week = league?.current_week || 1
        const teamParam = selectedTeamId ? `&team_id=${selectedTeamId}` : ''
        const res = await fetch(`/api/analysis/h2h-tale-of-the-tape?week=${week}${teamParam}`)
        if (res.ok) {
          const data: H2HTaleOfTheTapeResponse = await res.json()
          setTaleData(data)
        }
      } catch (err) {
        console.error('Failed to load H2H Tale of the Tape:', err)
      } finally {
        setIsLoadingTale(false)
      }
    }
    fetchTale()
  }, [league?.current_week, selectedTeamId])

  // Fetch current week matchups if not provided or to guarantee fresh week matchups
  useEffect(() => {
    const fetchCurrentMatchups = async () => {
      try {
        const week = league?.current_week || 1
        const res = await fetch(`/api/league/matchups?week=${week}`)
        if (res.ok) {
          const data: MatchupResponseItem[] = await res.json()
          setCurrentWeekMatchups(data)
        }
      } catch (err) {
        console.error('Failed to load current week matchups in IntelTab:', err)
      }
    }
    fetchCurrentMatchups()
  }, [league?.current_week])

  // Fetch DvP Fantasy Points Allowed ratings and sync status
  useEffect(() => {
    const fetchDvp = async () => {
      setIsLoadingDvp(true)
      try {
        const [ratingsRes, statusRes] = await Promise.all([
          fetch(`/api/analysis/dvp-ratings?position=${dvpPosition}`),
          fetch('/api/analysis/dvp-status'),
        ])
        if (ratingsRes.ok) {
          const data: DvPRecordItem[] = await ratingsRes.json()
          setDvpRatings(data)
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
    fetchDvp()
  }, [dvpPosition])

  const handleSyncDvp = async () => {
    setIsSyncingDvp(true)
    setDvpSyncMsg(null)
    try {
      const res = await fetch('/api/analysis/dvp-sync', { method: 'POST' })
      if (res.ok) {
        const result = await res.json()
        setDvpSyncMsg(`✅ Synced ${result.records_updated} teams across all 4 positions!`)
        const [ratingsRes, statusRes] = await Promise.all([
          fetch(`/api/analysis/dvp-ratings?position=${dvpPosition}`),
          fetch('/api/analysis/dvp-status'),
        ])
        if (ratingsRes.ok) setDvpRatings(await ratingsRes.json())
        if (statusRes.ok) setDvpStatus(await statusRes.json())
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

  // Map WR/CB data by player_id and name for fast lookup
  const wrcbMap = useMemo(() => {
    const map = new Map<number, WRCBMatchupAnalysis>()
    for (const item of wrcbData) {
      map.set(item.player_id, item)
    }
    return map
  }, [wrcbData])

  // Map Vegas game environments by pro team
  const teamVegasMap = useMemo(() => {
    const map = new Map<string, { game: VegasGameEnvironment; isHome: boolean; impliedPts: number; oppImpliedPts: number }>()
    if (!vegasData) return map

    for (const game of vegasData.games) {
      map.set(game.home_team.toUpperCase(), {
        game,
        isHome: true,
        impliedPts: game.home_implied_total,
        oppImpliedPts: game.away_implied_total,
      })
      map.set(game.away_team.toUpperCase(), {
        game,
        isHome: false,
        impliedPts: game.away_implied_total,
        oppImpliedPts: game.home_implied_total,
      })
    }
    return map
  }, [vegasData])

  // Map Market Sentiment Buzz by player_id
  const marketSentimentMap = useMemo(() => {
    const map = new Map<number, PlayerMarketSentimentItem>()
    for (const item of marketBuzz) {
      map.set(item.player_id, item)
    }
    return map
  }, [marketBuzz])

  // Extract weekly head-to-head matchup for user's team
  const h2hMatchup = useMemo(() => {
    const userTeamId = selectedTeamId ?? league?.user_team_id
    if (!userTeamId) return null

    // Determine user's team info
    const userTeam = league?.teams.find((t) => t.id === userTeamId)
    const userTeamName = userTeam?.name || taleData?.user_team_name || 'My Team'
    const userAbbrev = userTeam?.abbrev || 'MY'

    // Combine provided matchups prop and local currentWeekMatchups
    const effectiveMatchups = (matchups && matchups.length > 0) ? matchups : currentWeekMatchups
    const match = effectiveMatchups.find((m) => m.home_team_id === userTeamId || m.away_team_id === userTeamId)

    // Check taleData (authoritative H2H endpoint matching userTeamId)
    const hasTaleMatch = taleData && (taleData.user_team_id === userTeamId || !taleData.user_team_id)

    // Check lineup's opponent resolution
    const hasLineupOpponent = lineup && (lineup.opponent_team_name || lineup.opponent_team_id)

    // Resolve Opponent Team ID
    let oppTeamId: number | null = null
    if (match) {
      oppTeamId = match.home_team_id === userTeamId ? match.away_team_id : match.home_team_id
    } else if (hasTaleMatch && taleData?.opp_team_id) {
      oppTeamId = taleData.opp_team_id
    } else if (hasLineupOpponent && lineup?.opponent_team_id) {
      oppTeamId = lineup.opponent_team_id
    }

    const oppTeam = oppTeamId ? league?.teams.find((t) => t.id === oppTeamId) : null

    // Resolve Opponent Team Name
    let oppTeamName = ''
    if (match) {
      oppTeamName = match.home_team_id === userTeamId ? match.away_team_name : match.home_team_name
    } else if (hasTaleMatch && taleData?.opp_team_name) {
      oppTeamName = taleData.opp_team_name
    } else if (oppTeam?.name) {
      oppTeamName = oppTeam.name
    } else if (lineup?.opponent_team_name) {
      oppTeamName = lineup.opponent_team_name
    }

    // Resolve Opponent Abbrev
    let oppAbbrev = ''
    if (match) {
      oppAbbrev = match.home_team_id === userTeamId ? match.away_team_abbrev : match.home_team_abbrev
    } else if (oppTeam?.abbrev) {
      oppAbbrev = oppTeam.abbrev
    } else if (lineup?.opponent_team_abbrev) {
      oppAbbrev = lineup.opponent_team_abbrev
    } else if (oppTeamName && oppTeamName.length >= 3) {
      oppAbbrev = oppTeamName.slice(0, 3).toUpperCase()
    } else {
      oppAbbrev = 'OPP'
    }

    // If no opponent found at all and no lineup/tale data yet, don't show an invalid banner
    if (!match && !hasTaleMatch && !lineup) {
      return null
    }

    // Projections & Scores
    const isHome = match ? match.home_team_id === userTeamId : true
    const isCompleted = match ? (match.winner !== null && match.winner !== 'UNDECIDED' && match.winner !== 'NONE') : false

    const userScore = match ? (isHome ? match.home_score : match.away_score) : undefined
    const oppScore = match ? (isHome ? match.away_score : match.home_score) : undefined

    const userProjected = match
      ? (isHome ? match.home_projected : match.away_projected)
      : (taleData?.user_projected_total ?? (lineup?.total_projected_points || 0))

    const oppProjected = match
      ? (isHome ? match.away_projected : match.home_projected)
      : (taleData?.opp_projected_total ?? (lineup?.opponent_projected_points || 0))

    const spread = (userProjected !== undefined && oppProjected !== undefined)
      ? Math.round((userProjected - oppProjected) * 10) / 10
      : (taleData?.spread ?? (lineup?.implied_matchup_spread ?? 0))

    const posture = lineup?.game_theory_posture || taleData?.posture || (spread >= 8 ? 'HIGH_FLOOR' : spread <= -8 ? 'AGGRESSIVE_CEILING' : 'BALANCED')

    const recommendation =
      lineup?.game_theory_recommendation ||
      taleData?.key_leverage_summary ||
      (spread >= 5
        ? `Favored by +${spread.toFixed(1)} pts. Protect lead with high-floor starters and secure volume.`
        : spread <= -5
        ? `Underdog by ${Math.abs(spread).toFixed(1)} pts. Target shootout environments and ceiling wideouts.`
        : 'Close projected matchup. Matchup edges and red zone opportunities will decide the week.')

    return {
      userTeamName,
      userAbbrev,
      oppTeamName: oppTeamName || 'Scheduled Opponent',
      oppAbbrev,
      userScore,
      oppScore,
      userProjected,
      oppProjected,
      spread,
      posture,
      recommendation,
      isCompleted,
    }
  }, [league, matchups, currentWeekMatchups, lineup, selectedTeamId, taleData])

  // Extract Starters and Bench lists with enriched matchup indicators
  const { startersList, benchList } = useMemo(() => {
    if (!lineup) {
      return { startersList: [], benchList: [] }
    }

    const sList = lineup.starters.map((slot: SlotAssignment) => ({
      slotName: slot.slot_name,
      player: slot.recommended_player,
      isStarter: true,
      wrcb: wrcbMap.get(slot.recommended_player.player_id),
      vegas: teamVegasMap.get(slot.recommended_player.pro_team.toUpperCase()),
      stars: getMatchupStars(slot.recommended_player.matchup_stars, slot.recommended_player.opp_dvp_rank),
    }))

    const bList = lineup.bench.map((player: StartSitEvaluation) => ({
      slotName: 'BENCH',
      player,
      isStarter: false,
      wrcb: wrcbMap.get(player.player_id),
      vegas: teamVegasMap.get(player.pro_team.toUpperCase()),
      stars: getMatchupStars(player.matchup_stars, player.opp_dvp_rank),
    }))

    return { startersList: sList, benchList: bList }
  }, [lineup, wrcbMap, teamVegasMap])

  // Roster Matchup Health Pulse stats
  const pulseStats = useMemo(() => {
    const totalStarters = startersList.length
    const smashCount = startersList.filter((s) => s.stars >= 4).length
    const toughCount = startersList.filter((s) => s.stars <= 2).length
    const shadowAlerts = startersList.filter(
      (s) => s.player.wrcb_is_shadow || s.wrcb?.is_shadow_projected || s.wrcb?.advantage_rating === 'SHADOW_LOCKDOWN'
    ).length
    const shootoutGames = startersList.filter((s) => s.vegas?.game.over_under && s.vegas.game.over_under >= 48.0).length

    return {
      totalStarters,
      smashCount,
      toughCount,
      shadowAlerts,
      shootoutGames,
    }
  }, [startersList])

  // Matchup Opportunities: Find bench players with significant matchup edges over active starters
  const matchupOpportunities = useMemo(() => {
    if (!startersList.length || !benchList.length) return []

    const opportunities: Array<{
      starter: typeof startersList[0]
      bench: typeof benchList[0]
      starDelta: number
      wrcbDelta: number
      reason: string
    }> = []

    for (const b of benchList) {
      // Find same position starters
      const candidateStarters = startersList.filter((s) => {
        if (s.player.position === b.player.position) return true
        if (['RB', 'WR', 'TE'].includes(b.player.position) && s.slotName === 'FLEX') return true
        return false
      })

      for (const s of candidateStarters) {
        const starDelta = b.stars - s.stars
        const bAdv = b.wrcb?.advantage_score || 0
        const sAdv = s.wrcb?.advantage_score || 0
        const wrcbDelta = Math.round((bAdv - sAdv) * 10) / 10

        // Highlight if bench has >= 2 star edge, OR bench is in 4-5 star while starter is in 1-2 star, OR +20% WR/CB edge
        if (starDelta >= 2 || (b.stars >= 4 && s.stars <= 2) || (wrcbDelta >= 20.0)) {
          let reason = ''
          if (b.wrcb?.advantage_rating === 'SLOT_MISMATCH' && s.wrcb?.advantage_rating === 'SHADOW_LOCKDOWN') {
            reason = `High-conviction mismatch: ${b.player.full_name} has a prime slot mismatch while ${s.player.full_name} is locked in shadow coverage.`
          } else if (starDelta >= 2) {
            reason = `${b.player.full_name} has a ${b.stars}★ matchup vs #${b.player.opp_dvp_rank ?? 'N/A'} DvP, while ${s.player.full_name} faces a stiff ${s.stars}★ defense.`
          } else if (wrcbDelta >= 15.0) {
            reason = `WR/CB Edge: ${b.player.full_name} holds a +${bAdv.toFixed(1)}% coverage advantage over ${s.player.full_name}'s ${sAdv.toFixed(1)}% matchup.`
          } else {
            reason = `${b.player.full_name} is in a significantly superior scoring environment this week.`
          }

          opportunities.push({
            starter: s,
            bench: b,
            starDelta,
            wrcbDelta,
            reason,
          })
        }
      }
    }

    // Sort opportunities by greatest star delta then bench projected points
    opportunities.sort((a, b) => b.starDelta - a.starDelta || b.bench.player.projected_points - a.bench.player.projected_points)
    return opportunities
  }, [startersList, benchList])

  // Filtered Starters
  const filteredStarters = useMemo(() => {
    return startersList.filter((s) => {
      if (posFilter !== 'ALL' && s.player.position !== posFilter) return false
      if (searchQuery) {
        const q = searchQuery.toLowerCase().trim()
        const matchName = s.player.full_name.toLowerCase().includes(q)
        const matchTeam = s.player.pro_team.toLowerCase().includes(q)
        const matchOpp = s.player.opponent.toLowerCase().includes(q)
        if (!matchName && !matchTeam && !matchOpp) return false
      }
      return true
    })
  }, [startersList, posFilter, searchQuery])

  // Filtered Bench
  const filteredBench = useMemo(() => {
    return benchList.filter((b) => {
      if (posFilter !== 'ALL' && b.player.position !== posFilter) return false
      if (searchQuery) {
        const q = searchQuery.toLowerCase().trim()
        const matchName = b.player.full_name.toLowerCase().includes(q)
        const matchTeam = b.player.pro_team.toLowerCase().includes(q)
        const matchOpp = b.player.opponent.toLowerCase().includes(q)
        if (!matchName && !matchTeam && !matchOpp) return false
      }
      return true
    })
  }, [benchList, posFilter, searchQuery])

  // Map selected team roster players by their NFL pro team from active lineup
  const rosterPlayersByTeam = useMemo(() => {
    const map = new Map<string, Array<{
      player_id: number
      full_name: string
      position: string
      pro_team: string
      is_starter: boolean
      projected_points: number
    }>>()

    if (!lineup) return map

    for (const s of lineup.starters) {
      const p = s.recommended_player
      const t = p.pro_team?.toUpperCase().trim()
      if (!t) continue
      const list = map.get(t) || []
      list.push({
        player_id: p.player_id,
        full_name: p.full_name,
        position: p.position,
        pro_team: t,
        is_starter: true,
        projected_points: p.projected_points || 0,
      })
      map.set(t, list)
    }

    for (const b of lineup.bench) {
      const t = b.pro_team?.toUpperCase().trim()
      if (!t) continue
      const list = map.get(t) || []
      list.push({
        player_id: b.player_id,
        full_name: b.full_name,
        position: b.position,
        pro_team: t,
        is_starter: false,
        projected_points: b.projected_points || 0,
      })
      map.set(t, list)
    }

    return map
  }, [lineup])

  // Map opponent teams faced by active roster to highlight DvP rows
  const rosterOpponents = useMemo(() => {
    const map = new Map<string, Array<{ full_name: string; position: string; is_starter: boolean }>>()
    if (!lineup) return map
    for (const s of lineup.starters) {
      const p = s.recommended_player
      const opp = p.opponent?.toUpperCase().trim()
      if (!opp) continue
      const list = map.get(opp) || []
      list.push({ full_name: p.full_name, position: p.position, is_starter: true })
      map.set(opp, list)
    }
    for (const b of lineup.bench) {
      const opp = b.opponent?.toUpperCase().trim()
      if (!opp) continue
      const list = map.get(opp) || []
      list.push({ full_name: b.full_name, position: b.position, is_starter: false })
      map.set(opp, list)
    }
    return map
  }, [lineup])

  // Filtered and sorted DvP ratings
  const sortedDvpRatings = useMemo(() => {
    let list = [...dvpRatings]
    if (searchQuery && subView === 'dvp') {
      const q = searchQuery.toLowerCase().trim()
      list = list.filter(
        (r) =>
          r.team_name.toLowerCase().includes(q) ||
          r.pro_team.toLowerCase().includes(q) ||
          r.tier_label.toLowerCase().includes(q)
      )
    }
    list.sort((a, b) => {
      let aVal: any = a[dvpSortCol]
      let bVal: any = b[dvpSortCol]
      if (typeof aVal === 'string') {
        return dvpSortAsc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal)
      }
      aVal = aVal ?? 0
      bVal = bVal ?? 0
      return dvpSortAsc ? aVal - bVal : bVal - aVal
    })
    return list
  }, [dvpRatings, searchQuery, subView, dvpSortCol, dvpSortAsc])

  // Selected team WR IDs from lineup
  const { rosteredWRPids, starterWRPids } = useMemo(() => {
    const rostered = new Set<number>()
    const starters = new Set<number>()
    if (lineup) {
      for (const s of lineup.starters) {
        if (s.recommended_player.position === 'WR') {
          starters.add(s.recommended_player.player_id)
          rostered.add(s.recommended_player.player_id)
        }
      }
      for (const b of lineup.bench) {
        if (b.position === 'WR') {
          rostered.add(b.player_id)
        }
      }
    }
    return { rosteredWRPids: rostered, starterWRPids: starters }
  }, [lineup])

  // Filtered WR/CB Scouting Data (All 32 teams, dynamically matching selected roster)
  const filteredWrcbList = useMemo(() => {
    return wrcbData.filter((item) => {
      const isRostered = lineup ? rosteredWRPids.has(item.player_id) : item.is_user_rostered

      if (wrcbTagFilter === 'SHADOW' && !item.is_shadow_projected && item.advantage_rating !== 'SHADOW_LOCKDOWN') return false
      if (wrcbTagFilter === 'SLOT' && item.advantage_rating !== 'SLOT_MISMATCH') return false
      if (wrcbTagFilter === 'FAVORABLE' && !['FAVORABLE', 'MAJOR_ADVANTAGE'].includes(item.advantage_rating)) return false
      if (wrcbTagFilter === 'ROSTERED' && !isRostered) return false

      if (searchQuery) {
        const q = searchQuery.toLowerCase().trim()
        const matchesName = item.full_name.toLowerCase().includes(q)
        const matchesTeam = item.pro_team.toLowerCase().includes(q)
        const matchesOpp = item.opponent.toLowerCase().includes(q)
        const matchesCb = item.primary_cb.name.toLowerCase().includes(q)
        if (!matchesName && !matchesTeam && !matchesOpp && !matchesCb) return false
      }
      return true
    })
  }, [wrcbData, wrcbTagFilter, searchQuery, lineup, rosteredWRPids])

  // Vegas games enriched with the selected team's roster exposure
  const vegasGamesWithRoster = useMemo(() => {
    if (!vegasData) return []
    return vegasData.games.map((g) => {
      let exposure = g.user_roster_exposure || []
      // When lineup is loaded for the selected team, dynamically compute exposure for that team
      if (lineup && (lineup.starters.length > 0 || lineup.bench.length > 0)) {
        const homeKey = g.home_team.toUpperCase().trim()
        const awayKey = g.away_team.toUpperCase().trim()
        const homeList = rosterPlayersByTeam.get(homeKey) || []
        const awayList = rosterPlayersByTeam.get(awayKey) || []
        const seen = new Set<number>()
        const combined = []
        for (const p of [...homeList, ...awayList]) {
          if (!seen.has(p.player_id)) {
            seen.add(p.player_id)
            combined.push(p)
          }
        }
        exposure = combined
      }
      return {
        ...g,
        user_roster_exposure: exposure,
      }
    })
  }, [vegasData, lineup, rosterPlayersByTeam])

  // Filtered Vegas Games (respects selected team exposure)
  const filteredVegasGames = useMemo(() => {
    let list = [...vegasGamesWithRoster]

    if (scriptFilter === 'MY_PLAYERS') {
      list = list.filter((g) => g.user_roster_exposure.length > 0)
    } else if (scriptFilter !== 'ALL') {
      list = list.filter((g) => g.game_script === scriptFilter)
    }

    if (searchQuery) {
      const q = searchQuery.toLowerCase().trim()
      list = list.filter(
        (g) =>
          g.game_name.toLowerCase().includes(q) ||
          g.home_team.toLowerCase().includes(q) ||
          g.away_team.toLowerCase().includes(q)
      )
    }

    // Pin games featuring selected team roster players to the top
    list.sort((a, b) => {
      const aHas = a.user_roster_exposure.length > 0 ? 1 : 0
      const bHas = b.user_roster_exposure.length > 0 ? 1 : 0
      if (aHas !== bHas) return bHas - aHas
      return b.over_under - a.over_under
    })

    return list
  }, [vegasGamesWithRoster, scriptFilter, searchQuery])

  // Helper for WR/CB Advantage badge
  const renderAdvantageBadge = (rating: string, score: number) => {
    switch (rating) {
      case 'SHADOW_LOCKDOWN':
        return (
          <span className="pill rose" style={{ fontSize: '11px', fontWeight: 800 }}>
            🚨 SHADOW LOCKDOWN ({score > 0 ? `+${score}` : score}%)
          </span>
        )
      case 'SLOT_MISMATCH':
        return (
          <span className="pill emerald" style={{ fontSize: '11px', fontWeight: 800 }}>
            🔥 SLOT MISMATCH (+{score}%)
          </span>
        )
      case 'MAJOR_ADVANTAGE':
        return (
          <span className="pill cyan" style={{ fontSize: '11px', fontWeight: 800 }}>
            ⭐ MAJOR MISMATCH (+{score}%)
          </span>
        )
      case 'FAVORABLE':
        return (
          <span className="pill cyan" style={{ fontSize: '11px', fontWeight: 700 }}>
            👍 FAVORABLE (+{score}%)
          </span>
        )
      case 'TOUGH_PERIMETER':
        return (
          <span className="pill amber" style={{ fontSize: '11px', fontWeight: 700 }}>
            ⚠️ TOUGH PERIMETER ({score}%)
          </span>
        )
      default:
        return (
          <span className="pill zinc" style={{ fontSize: '11px', fontWeight: 600 }}>
            ⚖️ NEUTRAL ({score > 0 ? `+${score}` : score}%)
          </span>
        )
    }
  }

  // Helper for CB Grade badge
  const renderCbGradeBadge = (grade: number) => {
    if (grade >= 88.0) {
      return <span className="pill purple" style={{ fontSize: '10.5px' }}>{grade.toFixed(1)} Elite</span>
    }
    if (grade >= 78.0) {
      return <span className="pill cyan" style={{ fontSize: '10.5px' }}>{grade.toFixed(1)} Above Avg</span>
    }
    if (grade >= 70.0) {
      return <span className="pill amber" style={{ fontSize: '10.5px' }}>{grade.toFixed(1)} Neutral</span>
    }
    return <span className="pill rose" style={{ fontSize: '10.5px' }}>{grade.toFixed(1)} Burnable</span>
  }

  // Helper for Game Script badge
  const renderScriptBadge = (script: string, label: string) => {
    switch (script) {
      case 'SHOOTOUT':
        return <span className="pill amber" style={{ fontWeight: 800 }}>🔥 {label}</span>
      case 'FAVORITE_RUN_FUNNEL':
        return <span className="pill emerald" style={{ fontWeight: 800 }}>🏃 {label}</span>
      case 'UNDERDOG_PASS_FUNNEL':
        return <span className="pill cyan" style={{ fontWeight: 800 }}>📈 {label}</span>
      case 'DEFENSIVE_SLUGFEST':
        return <span className="pill zinc" style={{ fontWeight: 800 }}>🛡️ {label}</span>
      default:
        return <span className="pill purple" style={{ fontWeight: 700 }}>⚖️ {label}</span>
    }
  }

  // Renders a unified, professional player matchup card
  const renderPlayerMatchupCard = (item: {
    slotName: string
    player: StartSitEvaluation
    isStarter: boolean
    wrcb?: WRCBMatchupAnalysis
    vegas?: { game: VegasGameEnvironment; isHome: boolean; impliedPts: number; oppImpliedPts: number }
    stars: number
  }) => {
    const { slotName, player: p, isStarter, wrcb, vegas, stars } = item
    const tier = getMatchupTierInfo(stars, p.position)
    const hasVegas = !!vegas
    const isShootout = (vegas?.game.over_under || 0) >= 48.0
    const sentiment = marketSentimentMap.get(p.player_id)

    return (
      <div
        key={`${slotName}-${p.player_id}`}
        className={`intel-player-card ${isStarter ? 'starter' : 'bench'}`}
      >
        {/* Card Header */}
        <div className="intel-card-header">
          <div className="intel-player-identity">
            <div className="intel-player-name-row">
              <span className={`intel-slot-badge ${!isStarter ? 'bench' : ''}`}>
                {slotName}
              </span>
              <span className="intel-player-name">{p.full_name}</span>
              <InjuryStatusPill status={p.injury_status} fullName={p.full_name} position={p.position} />
            </div>
            <div className="intel-team-opp-badge" style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
              <NFLTeamLogo team={p.pro_team} size={18} />
              <strong>{p.pro_team}</strong>
              <span>{p.is_home ? 'vs' : '@'}</span>
              <NFLTeamLogo team={p.opponent} size={18} />
              <strong>{p.opponent}</strong>
              {p.game_date && (
                <span style={{ color: 'var(--text-muted)', fontSize: '11px', marginLeft: '4px' }}>
                  • {new Date(p.game_date).toLocaleDateString(undefined, { weekday: 'short', hour: 'numeric', minute: '2-digit' })}
                </span>
              )}
            </div>
          </div>

          <div className="intel-card-header-right">
            <div className="intel-projected-pts">
              {p.projected_points.toFixed(1)} <span>pts</span>
            </div>
            <span
              className={`pill ${isStarter ? 'emerald' : 'zinc'}`}
              style={{ fontSize: '10px', padding: '1px 6px', fontWeight: 800 }}
            >
              {isStarter ? 'STARTER' : 'BENCH'}
            </span>
          </div>
        </div>

        {/* Primary Matchup Rating Strip */}
        <div className="intel-matchup-strip">
          <div className="intel-stars-group">
            <MatchupStarRating stars={stars} oppDvpRank={p.opp_dvp_rank} position={p.position} />
            <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-primary)' }}>
              {tier.label}
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            {p.boris_chen_tier && (
              <Tooltip term="BORIS_TIER" title={`Boris Chen GMM Tier ${p.boris_chen_tier}`}>
                <span className={`boris-tier-badge tier-${p.boris_chen_tier}`}>
                  <span>💎</span> {p.boris_chen_tier_label || `Tier ${p.boris_chen_tier}`}
                </span>
              </Tooltip>
            )}
            {p.dvp_fpa ? (
              <Tooltip term="DVP_FPA" title={`DraftKings Fantasy Points Allowed to ${p.position}s`}>
                <span
                  className={`pill ${
                    p.dvp_fpa.tier === 'SMASH'
                      ? 'emerald'
                      : p.dvp_fpa.tier === 'FAVORABLE'
                      ? 'cyan'
                      : p.dvp_fpa.tier === 'TOUGH'
                      ? 'amber'
                      : p.dvp_fpa.tier === 'LOCKDOWN'
                      ? 'rose'
                      : 'zinc'
                  }`}
                  style={{
                    fontSize: '11px',
                    fontWeight: 800,
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    ...(p.dvp_fpa.tier === 'SMASH'
                      ? { background: 'rgba(16, 185, 129, 0.25)', border: '1px solid rgba(16, 185, 129, 0.7)' }
                      : {}),
                    ...(p.dvp_fpa.tier === 'LOCKDOWN'
                      ? { background: 'rgba(244, 63, 94, 0.25)', border: '1px solid rgba(244, 63, 94, 0.7)' }
                      : {}),
                  }}
                >
                  🛡️ {p.dvp_fpa.dk_fpa.toFixed(1)} DK FPA (#{p.dvp_fpa.rank_softness} {p.dvp_fpa.tier_label})
                </span>
              </Tooltip>
            ) : p.opp_dvp_rank ? (
              <Tooltip term="DVP" title={`DvP #${p.opp_dvp_rank} vs ${p.position}`}>
                <span
                  className={`pill ${p.opp_dvp_rank >= 27 ? 'emerald' : p.opp_dvp_rank >= 21 ? 'cyan' : p.opp_dvp_rank <= 6 ? 'rose' : p.opp_dvp_rank <= 12 ? 'amber' : 'zinc'}`}
                  style={{
                    fontSize: '11px',
                    fontWeight: 800,
                    ...(p.opp_dvp_rank >= 27 ? { background: 'rgba(16, 185, 129, 0.25)', border: '1px solid rgba(16, 185, 129, 0.7)' } : {}),
                    ...(p.opp_dvp_rank <= 6 ? { background: 'rgba(244, 63, 94, 0.25)', border: '1px solid rgba(244, 63, 94, 0.7)' } : {}),
                  }}
                >
                  {p.opp_dvp_rank >= 27 ? '🚀 ELITE' : p.opp_dvp_rank <= 6 ? '🛑 BRUTAL' : '🛡️ DvP'} #{p.opp_dvp_rank}
                </span>
              </Tooltip>
            ) : null}
            {p.opp_def_rank && (
              <span className="pill zinc" style={{ fontSize: '10.5px' }} title="Overall Team Defense Rank">
                Def #{p.opp_def_rank}
              </span>
            )}
            {sentiment?.has_starter_controversy && (
              <Tooltip term="MARKET_STARTER" title={sentiment.tactical_advice}>
                <span
                  className="pill amber"
                  style={{ fontSize: '10.5px', fontWeight: 800, border: '1px solid rgba(245, 158, 11, 0.7)' }}
                >
                  ⚡ Market Odds: {Math.round(sentiment.starter_confidence * 100)}% Start
                </span>
              </Tooltip>
            )}
            {sentiment?.decoy_risk === 'HIGH' && (
              <Tooltip term="DECOY_RISK" title={sentiment.tactical_advice}>
                <span
                  className="pill rose"
                  style={{ fontSize: '10.5px', fontWeight: 800, border: '1px solid rgba(244, 63, 94, 0.7)' }}
                >
                  🚨 High Decoy Risk
                </span>
              </Tooltip>
            )}
            {sentiment?.is_rookie && sentiment.rookie_tier === 'DAY1_ALPHA' && (
              <span className="pill purple" style={{ fontSize: '10.5px', fontWeight: 800 }}>
                🌟 Day-1 Alpha Rookie
              </span>
            )}
            {sentiment?.is_thursday_kickoff && (
              <span className="pill cyan" style={{ fontSize: '10.5px', fontWeight: 800 }}>
                🏈 TNF Kickoff
              </span>
            )}
          </div>
        </div>

        {/* Defensive Matchup Strength (DvP) Strip */}
        {p.dvp_fpa && (
          <div className="intel-dvp-strip">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              <span style={{ fontWeight: 700, color: 'var(--text-secondary)' }}>
                🛡️ {p.opponent} vs {p.position}:
              </span>
              <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
                Allows <strong style={{ color: p.dvp_fpa.vs_avg >= 0 ? 'var(--accent-emerald)' : 'var(--accent-rose)' }}>{p.dvp_fpa.dk_fpa.toFixed(1)} DK pts/G</strong> ({p.dvp_fpa.vs_avg >= 0 ? `+${p.dvp_fpa.vs_avg.toFixed(1)}` : p.dvp_fpa.vs_avg.toFixed(1)} vs avg)
              </span>
              {p.dvp_fpa.trend && (
                <span
                  className={`pill ${p.dvp_fpa.trend === 'UP' ? 'emerald' : p.dvp_fpa.trend === 'DOWN' ? 'rose' : 'zinc'}`}
                  style={{ fontSize: '9.5px', padding: '0 5px', fontWeight: 700 }}
                  title="Last 4 games trend"
                >
                  {p.dvp_fpa.trend === 'UP' ? '📈 Softer L4' : p.dvp_fpa.trend === 'DOWN' ? '📉 Tougher L4' : '⚖️ Stable'}
                </span>
              )}
              {p.dvp_fpa.supporting_stats && (
                <div style={{ display: 'flex', gap: '5px', color: 'var(--text-muted)', fontSize: '10.5px' }}>
                  {p.position === 'QB' && p.dvp_fpa.supporting_stats.pass_yds && (
                    <span style={{ background: 'rgba(255, 255, 255, 0.04)', padding: '1px 5px', borderRadius: '3px' }}>
                      Pass: <strong style={{ color: 'var(--text-secondary)' }}>{p.dvp_fpa.supporting_stats.pass_yds.toFixed(0)} yds, {p.dvp_fpa.supporting_stats.pass_td?.toFixed(1)} TD</strong>
                    </span>
                  )}
                  {['RB', 'FB'].includes(p.position) && p.dvp_fpa.supporting_stats.rush_yds && (
                    <span style={{ background: 'rgba(255, 255, 255, 0.04)', padding: '1px 5px', borderRadius: '3px' }}>
                      Rush: <strong style={{ color: 'var(--text-secondary)' }}>{p.dvp_fpa.supporting_stats.rush_yds.toFixed(0)} yds, {p.dvp_fpa.supporting_stats.rush_td?.toFixed(1)} TD</strong>
                    </span>
                  )}
                  {p.position === 'WR' && p.dvp_fpa.supporting_stats.rec_yds && (
                    <span style={{ background: 'rgba(255, 255, 255, 0.04)', padding: '1px 5px', borderRadius: '3px' }}>
                      WR Allowed: <strong style={{ color: 'var(--text-secondary)' }}>{p.dvp_fpa.supporting_stats.rec_yds.toFixed(0)} yds, {p.dvp_fpa.supporting_stats.rec_td?.toFixed(1)} TD</strong>
                    </span>
                  )}
                  {p.position === 'TE' && p.dvp_fpa.supporting_stats.rec_yds && (
                    <span style={{ background: 'rgba(255, 255, 255, 0.04)', padding: '1px 5px', borderRadius: '3px' }}>
                      TE Allowed: <strong style={{ color: 'var(--text-secondary)' }}>{p.dvp_fpa.supporting_stats.rec_yds.toFixed(0)} yds ({p.dvp_fpa.supporting_stats.targets?.toFixed(1)} tgt)</strong>
                    </span>
                  )}
                </div>
              )}
            </div>

            {p.dvp_fpa.is_baseline && (
              <Tooltip term="DVP_BASELINE" title="Week 1 Baseline Logic">
                <span style={{ fontSize: '10px', color: 'var(--accent-cyan)', fontStyle: 'italic', cursor: 'help' }}>
                  ℹ️ 2025-26 Weighted Baseline
                </span>
              </Tooltip>
            )}
          </div>
        )}

        {/* PPR Opportunity & High-Value Touch (HVT) Strip */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap', padding: '6px 14px', background: 'rgba(255, 255, 255, 0.02)', borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
          {p.itemized_stats?.receptions !== undefined && p.itemized_stats.receptions > 0 && (
            <span className="pill cyan" style={{ padding: '1px 6px', fontWeight: 700, fontSize: '10.5px' }} title="Projected Receptions in PPR">
              🎯 {p.itemized_stats.receptions.toFixed(1)} Proj Rec
            </span>
          )}
          {p.volume_share !== undefined && p.volume_share !== null && p.volume_share > 0 && (
            <span className="pill purple" style={{ padding: '1px 6px', fontWeight: 700, fontSize: '10.5px' }} title="Projected Target or Touch Share">
              📈 {(p.volume_share * 100).toFixed(0)}% Share
            </span>
          )}
          {['RB', 'FB'].includes(p.position) && ((p.itemized_stats?.receptions ?? 0) >= 2.5 || p.projected_points >= 15.0) && (
            <span className="pill emerald" style={{ padding: '1px 6px', fontWeight: 800, fontSize: '10px' }} title="3-Down Bellcow with High-Value PPR Touches">
              🔥 3-Down Bellcow (High HVT)
            </span>
          )}
          {p.position === 'WR' && (p.volume_share ?? 0) >= 0.22 && (
            <span className="pill emerald" style={{ padding: '1px 6px', fontWeight: 800, fontSize: '10px' }} title="Alpha 1st Read Target Funnel">
              ⭐ Alpha 1st Read
            </span>
          )}
          {p.position === 'TE' && p.projected_points >= 12.0 && (
            <span className="pill emerald" style={{ padding: '1px 6px', fontWeight: 800, fontSize: '10px' }} title="Elite Seam Weapon">
              ⚡ Elite Seam Weapon
            </span>
          )}
        </div>

        {/* Vegas & Game Environment Strip */}
        {hasVegas && (
          <div className="intel-env-strip">
            <Tooltip term="ITT" title="Vegas Over/Under Total">
              <span
                className={`intel-env-pill ${isShootout ? 'shootout' : ''}`}
              >
                {isShootout ? '🔥' : '🎰'} O/U {vegas.game.over_under.toFixed(1)}
              </span>
            </Tooltip>
            <Tooltip term="ITT" title="Team Implied Scoring Total">
              <span className="intel-env-pill implied-high">
                Implied: <strong>{vegas.impliedPts.toFixed(1)}</strong> pts
              </span>
            </Tooltip>
            <Tooltip term="GAME_SCRIPT" title="Vegas Spread Margin">
              <span className="intel-env-pill">
                {vegas.game.favorite_team === p.pro_team ? `-${vegas.game.spread_magnitude.toFixed(1)} Fav` : `+${vegas.game.spread_magnitude.toFixed(1)} Dog`}
              </span>
            </Tooltip>
            {vegas.game.is_dome ? (
              <span className="intel-env-pill" title="Indoor Dome: Fast track with zero weather friction">
                🏟️ Dome
              </span>
            ) : p.weather_summary?.toLowerCase().includes('wind') ? (
              <span className="intel-env-pill" style={{ color: 'var(--accent-amber)', borderColor: 'rgba(245, 158, 11, 0.4)' }} title={p.weather_summary}>
                💨 {p.weather_summary}
              </span>
            ) : p.weather_summary ? (
              <span className="intel-env-pill" style={{ color: 'var(--text-muted)' }} title={p.weather_summary}>
                🌤️ {p.weather_summary}
              </span>
            ) : null}
          </div>
        )}

        {/* Vegas Player Prop Outlook & Grade Strip */}
        {(p.props_vegas_grade || p.props_receptions_ou || p.props_rush_yds_ou || p.props_pass_yds_ou || p.props_implied_ppr_pts) && (
          <div className="intel-vegas-outlook-strip">
            <div className="intel-vegas-outlook-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                <Tooltip term="VEGAS_PROPS" title="Vegas Player Prop Outlook">
                  <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-secondary)' }}>
                    🎲 Vegas Prop Outlook:
                  </span>
                </Tooltip>
                {p.props_vegas_grade && (
                  <span className={`intel-vegas-grade-badge ${p.props_vegas_grade_color || 'zinc'}`} title={`Vegas statistical grade for ${p.position} in PPR`}>
                    {p.props_vegas_grade_label || p.props_vegas_grade}
                  </span>
                )}
              </div>
              {p.props_implied_ppr_pts !== undefined && p.props_implied_ppr_pts !== null && (
                <Tooltip term="VEGAS_PROPS" title="PPR Fantasy Points Implied by Betting Lines">
                  <span className="intel-prop-chip implied">
                    ⚡ <strong>{p.props_implied_ppr_pts.toFixed(1)}</strong> Implied PPR
                  </span>
                </Tooltip>
              )}
            </div>

            <div className="intel-vegas-props-pills">
              {/* QB Props */}
              {p.position === 'QB' && (
                <>
                  {p.props_pass_yds_ou && (
                    <span className="intel-prop-chip" title="Passing Yards Over/Under">
                      🎯 <strong>{p.props_pass_yds_ou}</strong> Pass Yds O/U
                    </span>
                  )}
                  {p.props_pass_tds_ou && (
                    <span className="intel-prop-chip" title="Passing Touchdowns Over/Under">
                      🏈 <strong>{p.props_pass_tds_ou}</strong> Pass TDs
                    </span>
                  )}
                  {p.props_rush_yds_ou && p.props_rush_yds_ou >= 10.0 && (
                    <span className="intel-prop-chip" title="QB Rushing Yards Over/Under">
                      🏃 <strong>{p.props_rush_yds_ou}</strong> Rush Yds
                    </span>
                  )}
                </>
              )}

              {/* RB Props */}
              {['RB', 'FB'].includes(p.position) && (
                <>
                  {p.props_rush_att_ou && (
                    <span className="intel-prop-chip" title="Rushing Attempts Over/Under">
                      🏃 <strong>{p.props_rush_att_ou}</strong> Carries O/U
                    </span>
                  )}
                  {p.props_rush_yds_ou && (
                    <span className="intel-prop-chip" title="Rushing Yards Over/Under">
                      💨 <strong>{p.props_rush_yds_ou}</strong> Rush Yds
                    </span>
                  )}
                  {p.props_receptions_ou && (
                    <span className="intel-prop-chip" title="Receptions Over/Under in PPR">
                      🎯 <strong>{p.props_receptions_ou}</strong> Rec O/U
                    </span>
                  )}
                </>
              )}

              {/* WR & TE Props */}
              {['WR', 'TE'].includes(p.position) && (
                <>
                  {p.props_receptions_ou && (
                    <span className="intel-prop-chip" title="Receptions Over/Under (PPR Gold Standard)">
                      🎯 <strong>{p.props_receptions_ou}</strong> Rec O/U
                    </span>
                  )}
                  {p.props_rec_yds_ou && (
                    <span className="intel-prop-chip" title="Receiving Yards Over/Under">
                      💨 <strong>{p.props_rec_yds_ou}</strong> Rec Yds
                    </span>
                  )}
                </>
              )}

              {/* Anytime TD Odds & Probability */}
              {p.props_anytime_td_prob && p.props_anytime_td_prob >= 0.25 ? (
                <span className="intel-prop-chip td" title="Market Implied Touchdown Probability">
                  💰 <strong>{Math.round(p.props_anytime_td_prob * 100)}%</strong> Anytime TD
                  {p.props_anytime_td_odds ? ` (${p.props_anytime_td_odds > 0 ? `+${p.props_anytime_td_odds}` : p.props_anytime_td_odds})` : ''}
                </span>
              ) : null}
            </div>

            {/* Actionable Sharp Takeaway */}
            {(p.props_vegas_takeaway || (p.props_sharp_notes && p.props_sharp_notes.length > 0)) && (
              <div className="intel-vegas-takeaway-text">
                <span style={{ color: 'var(--accent-amber)', fontSize: '12px' }}>💡</span>
                <span>{p.props_vegas_takeaway || p.props_sharp_notes?.[0]}</span>
              </div>
            )}
          </div>
        )}

        {/* WR vs CB Coverage Intelligence (if WR) */}
        {wrcb && (
          <div className="intel-cb-strip">
            <div className="intel-cb-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Tooltip term="WRCB" title="Primary Cornerback Coverage">
                  <span>Primary CB:</span>
                </Tooltip>
                <strong>{wrcb.primary_cb.name}</strong>
                {wrcb.primary_cb.is_shadow && (
                  <Tooltip term="WRCB" title="Shadow Coverage Lockdown Alert">
                    <span className="pill rose" style={{ fontSize: '9px', padding: '0 4px', fontWeight: 800 }}>
                      SHADOW
                    </span>
                  </Tooltip>
                )}
              </div>
              {renderCbGradeBadge(wrcb.primary_cb.coverage_grade)}
            </div>

            <div className="intel-cb-stats-row">
              <div>
                Role: <span className="intel-cb-stat-val">{wrcb.primary_cb.slot_role}</span>
              </div>
              <div>
                Catch Allowed: <span className="intel-cb-stat-val">{(wrcb.primary_cb.catch_rate_allowed * 100).toFixed(0)}%</span>
              </div>
              <div>
                FP/Route: <span className="intel-cb-stat-val">{wrcb.primary_cb.fpts_per_route_allowed.toFixed(2)}</span>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '2px' }}>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                Alignment: <strong style={{ color: 'var(--text-secondary)' }}>{(wrcb.alignment.pct_slot * 100).toFixed(0)}% Slot</strong> / {(wrcb.alignment.pct_wide * 100).toFixed(0)}% Wide
              </span>
              {renderAdvantageBadge(wrcb.advantage_rating, wrcb.advantage_score)}
            </div>
          </div>
        )}

        {/* Tactical Takeaway */}
        {(wrcb?.tactical_takeaway || p.game_script_label) && (
          <div className="intel-takeaway-box">
            {wrcb?.tactical_takeaway || `Game Script: ${p.game_script_label}. Target volume aligned with weekly game pace.`}
          </div>
        )}

        {/* Action Button */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', paddingTop: '4px' }}>
          {isStarter && onCompareStarterWithBench && (
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => onCompareStarterWithBench(p)}
              style={{ fontSize: '11px', padding: '4px 10px' }}
            >
              ⚔️ Compare with Bench
            </button>
          )}
          {!isStarter && onCompareBenchWithStarter && (
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={() => onCompareBenchWithStarter(p)}
              style={{ fontSize: '11px', padding: '4px 10px' }}
            >
              ⚡ Start/Sit Check
            </button>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="intel-container">
      {/* 1. EXECUTIVE HEADER */}
      <div className="intel-hero-card">
        <div className="intel-hero-top">
          <div className="intel-title-group">
            <div className="intel-icon-badge">🧠</div>
            <div>
              <h2 className="intel-heading">Matchup Intelligence Command Center</h2>
              <p className="intel-subtitle">
                Positional matchup leverage, WR/CB secondary tracking, and Vegas game environments.
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span className="pill cyan" style={{ fontWeight: 700 }}>
              Week {league?.current_week || 1} Intel
            </span>
            <button
              type="button"
              onClick={onRefresh}
              className="btn btn-secondary btn-sm"
              style={{ padding: '6px 12px' }}
            >
              🔄 Refresh Intel
            </button>
          </div>
        </div>
      </div>

      {/* 2. WEEKLY HEAD-TO-HEAD MATCHUP BANNER */}
      {h2hMatchup && (
        <div className="intel-h2h-card">
          <div className="intel-h2h-main">
            {/* User Team */}
            <div className="intel-h2h-team user">
              <div className="intel-h2h-team-name">
                <span>{h2hMatchup.userTeamName}</span>
                <span className="pill cyan" style={{ fontSize: '10px', padding: '1px 6px' }}>My Team</span>
              </div>
              <div className="intel-h2h-score">
                {h2hMatchup.isCompleted && h2hMatchup.userScore !== undefined
                  ? h2hMatchup.userScore.toFixed(1)
                  : h2hMatchup.userProjected.toFixed(1)}{' '}
                <span style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text-muted)' }}>
                  {h2hMatchup.isCompleted ? 'Final' : 'Proj Pts'}
                </span>
              </div>
              <div className="intel-h2h-meta">
                Posture: <strong style={{ color: 'var(--accent-cyan)' }}>{h2hMatchup.posture}</strong>
              </div>
            </div>

            {/* Center VS & Spread */}
            <div className="intel-h2h-vs-center">
              <span className="intel-h2h-vs-badge">
                {h2hMatchup.isCompleted ? 'FINAL' : 'WEEKLY H2H'}
              </span>
              <span
                className={`intel-h2h-spread ${h2hMatchup.spread >= 0 ? 'favored' : 'underdog'}`}
              >
                {h2hMatchup.spread >= 0
                  ? `+${h2hMatchup.spread.toFixed(1)} Favored`
                  : `${h2hMatchup.spread.toFixed(1)} Underdog`}
              </span>
            </div>

            {/* Opponent Team */}
            <div className="intel-h2h-team opp">
              <div className="intel-h2h-team-name">
                <span className="pill zinc" style={{ fontSize: '10px', padding: '1px 6px' }}>Opponent</span>
                <span>{h2hMatchup.oppTeamName}</span>
              </div>
              <div className="intel-h2h-score">
                {h2hMatchup.isCompleted && h2hMatchup.oppScore !== undefined
                  ? h2hMatchup.oppScore.toFixed(1)
                  : h2hMatchup.oppProjected.toFixed(1)}{' '}
                <span style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text-muted)' }}>
                  {h2hMatchup.isCompleted ? 'Final' : 'Proj Pts'}
                </span>
              </div>
              <div className="intel-h2h-meta">
                Matchup Target: <strong style={{ color: 'var(--text-secondary)' }}>{h2hMatchup.oppAbbrev}</strong>
              </div>
            </div>
          </div>

          <div className="intel-h2h-advice">
            💡 <strong>Tactical Roster Guidance:</strong> {h2hMatchup.recommendation}
          </div>

          {/* Positional Tale of the Tape: Slot-by-Slot Breakdown */}
          {isLoadingTale && !taleData && (
            <div style={{ padding: '12px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '12px' }}>
              ⏳ Loading slot-by-slot Tale of the Tape...
            </div>
          )}

          {taleData && (
            <div className="intel-tale-section">
              <div 
                className="intel-tale-toggle-bar"
                onClick={() => setShowTaleOfTheTape(!showTaleOfTheTape)}
                role="button"
                tabIndex={0}
                style={{ cursor: 'pointer' }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '15px' }}>⚔️</span>
                  <span style={{ fontWeight: 700, fontSize: '13px', color: 'var(--text-primary)' }}>
                    Slot-by-Slot Tale of the Tape ({taleData.slots.length} Positions)
                  </span>
                  <span className={`pill ${taleData.spread >= 0 ? 'emerald' : 'rose'}`} style={{ fontSize: '11px', fontWeight: 800 }}>
                    {taleData.spread >= 0 ? `+${taleData.spread.toFixed(1)} pt Margin` : `${taleData.spread.toFixed(1)} pt Deficit`}
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
                    {taleData.key_leverage_summary}
                  </span>
                  <span style={{ fontSize: '12px', color: 'var(--accent-cyan)', fontWeight: 600 }}>
                    {showTaleOfTheTape ? '▲ Hide' : '▼ Expand'}
                  </span>
                </div>
              </div>

              {showTaleOfTheTape && (
                <div className="intel-tale-grid">
                  <div className="intel-tale-header-row">
                    <div className="intel-tale-col-slot">Slot</div>
                    <div className="intel-tale-col-user">{taleData.user_team_name} (You)</div>
                    <div className="intel-tale-col-delta">Delta / Leverage</div>
                    <div className="intel-tale-col-opp">{taleData.opp_team_name} (Opponent)</div>
                  </div>

                  {taleData.slots.map((slot, idx) => {
                    const isUserAdv = slot.advantage === 'USER'
                    const isOppAdv = slot.advantage === 'OPPONENT'
                    const deltaFormatted = slot.point_delta > 0 
                      ? `+${slot.point_delta.toFixed(1)}`
                      : slot.point_delta.toFixed(1)

                    return (
                      <div key={`${slot.slot_name}-${idx}`} className={`intel-tale-row ${isUserAdv ? 'user-lead' : isOppAdv ? 'opp-lead' : ''}`}>
                        {/* Slot Badge */}
                        <div className="intel-tale-col-slot">
                          <span className="slot-badge">{slot.slot_name}</span>
                        </div>

                        {/* User Player Card */}
                        <div className="intel-tale-col-user">
                          <div className="intel-tale-player-info">
                            <span className="intel-tale-player-name">{slot.user_player.full_name}</span>
                            <span className="intel-tale-player-sub" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                              <NFLTeamLogo team={slot.user_player.pro_team} size={15} />
                              <span>{slot.user_player.pro_team} vs</span>
                              <NFLTeamLogo team={slot.user_player.opponent} size={15} />
                              <span>{slot.user_player.opponent} • #{slot.user_player.opp_dvp_rank} DvP</span>
                            </span>
                          </div>
                          <div className="intel-tale-player-scoring">
                            <span className="intel-tale-pts">{slot.user_player.projected_points.toFixed(1)} <small>pts</small></span>
                            {slot.user_player.matchup_grade === 'ELITE' && (
                              <span className="pill purple" style={{ fontSize: '9.5px', padding: '1px 5px', fontWeight: 800 }}>🚀 ELITE</span>
                            )}
                            {slot.user_player.matchup_grade === 'FAVORABLE' && (
                              <span className="pill cyan" style={{ fontSize: '9.5px', padding: '1px 5px', fontWeight: 700 }}>👍 FAV</span>
                            )}
                            {slot.user_player.matchup_grade === 'NEUTRAL' && (
                              <span className="pill zinc" style={{ fontSize: '9.5px', padding: '1px 5px' }}>NEU</span>
                            )}
                            {slot.user_player.matchup_grade === 'TOUGH' && (
                              <span className="pill amber" style={{ fontSize: '9.5px', padding: '1px 5px' }}>⚠️ TOUGH</span>
                            )}
                            {slot.user_player.matchup_grade === 'BRUTAL' && (
                              <span className="pill rose" style={{ fontSize: '9.5px', padding: '1px 5px', fontWeight: 800 }}>🛑 BRUTAL</span>
                            )}
                          </div>
                        </div>

                        {/* Center Delta & Tactical Leverage */}
                        <div className="intel-tale-col-delta">
                          <span className={`intel-tale-delta-pill ${isUserAdv ? 'emerald' : isOppAdv ? 'rose' : 'zinc'}`}>
                            {deltaFormatted} pts
                          </span>
                          <span className="intel-tale-leverage-text">
                            {slot.leverage_label}
                          </span>
                        </div>

                        {/* Opponent Player Card */}
                        <div className="intel-tale-col-opp">
                          <div className="intel-tale-player-scoring opp">
                            {slot.opp_player.matchup_grade === 'ELITE' && (
                              <span className="pill purple" style={{ fontSize: '9.5px', padding: '1px 5px', fontWeight: 800 }}>🚀 ELITE</span>
                            )}
                            {slot.opp_player.matchup_grade === 'FAVORABLE' && (
                              <span className="pill cyan" style={{ fontSize: '9.5px', padding: '1px 5px', fontWeight: 700 }}>👍 FAV</span>
                            )}
                            {slot.opp_player.matchup_grade === 'NEUTRAL' && (
                              <span className="pill zinc" style={{ fontSize: '9.5px', padding: '1px 5px' }}>NEU</span>
                            )}
                            {slot.opp_player.matchup_grade === 'TOUGH' && (
                              <span className="pill amber" style={{ fontSize: '9.5px', padding: '1px 5px' }}>⚠️ TOUGH</span>
                            )}
                            {slot.opp_player.matchup_grade === 'BRUTAL' && (
                              <span className="pill rose" style={{ fontSize: '9.5px', padding: '1px 5px', fontWeight: 800 }}>🛑 BRUTAL</span>
                            )}
                            <span className="intel-tale-pts opp">{slot.opp_player.projected_points.toFixed(1)} <small>pts</small></span>
                          </div>
                          <div className="intel-tale-player-info opp">
                            <span className="intel-tale-player-name">{slot.opp_player.full_name}</span>
                            <span className="intel-tale-player-sub" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                              <NFLTeamLogo team={slot.opp_player.pro_team} size={15} />
                              <span>{slot.opp_player.pro_team} vs</span>
                              <NFLTeamLogo team={slot.opp_player.opponent} size={15} />
                              <span>{slot.opp_player.opponent} • #{slot.opp_player.opp_dvp_rank} DvP</span>
                            </span>
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* 3. ROSTER MATCHUP HEALTH PULSE KPI STRIP */}
      <div className="intel-pulse-grid">
        <div className="intel-pulse-card">
          <div className="intel-pulse-label">
            <span>⭐ Smash Matchups (4–5★)</span>
          </div>
          <div className="intel-pulse-val" style={{ color: 'var(--accent-emerald)' }}>
            {pulseStats.smashCount} <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>/ {pulseStats.totalStarters} Starters</span>
          </div>
          <div className="intel-pulse-desc">Starters facing vulnerable, bottom-tier defenses</div>
        </div>

        <div className="intel-pulse-card">
          <div className="intel-pulse-label">
            <span>⚠️ Tough Matchups (1–2★)</span>
          </div>
          <div className="intel-pulse-val" style={{ color: 'var(--accent-rose)' }}>
            {pulseStats.toughCount} <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>/ {pulseStats.totalStarters} Starters</span>
          </div>
          <div className="intel-pulse-desc">Starters facing stiff defensive resistance</div>
        </div>

        <div className="intel-pulse-card">
          <div className="intel-pulse-label">
            <span>🚨 Shadow Coverage Alerts</span>
          </div>
          <div className="intel-pulse-val" style={{ color: pulseStats.shadowAlerts > 0 ? 'var(--accent-rose)' : 'var(--text-primary)' }}>
            {pulseStats.shadowAlerts}
          </div>
          <div className="intel-pulse-desc">Active wideouts tracked by shutdown lockdown corners</div>
        </div>

        <div className="intel-pulse-card">
          <div className="intel-pulse-label">
            <span>🔥 Shootout Exposures</span>
          </div>
          <div className="intel-pulse-val" style={{ color: 'var(--accent-amber)' }}>
            {pulseStats.shootoutGames}
          </div>
          <div className="intel-pulse-desc">Rostered players in high-total games (O/U ≥ 48.0)</div>
        </div>
      </div>

      {/* 4. ROSTER-FIRST SEGMENTED NAVIGATION */}
      <div className="intel-nav-bar">
        <button
          type="button"
          onClick={() => setSubView('starters')}
          className={`intel-nav-pill ${subView === 'starters' ? 'active' : ''}`}
        >
          <span>🟢 Starting Lineup Matchups</span>
          <span className="intel-nav-pill-count">{startersList.length}</span>
        </button>

        <button
          type="button"
          onClick={() => setSubView('bench')}
          className={`intel-nav-pill ${subView === 'bench' ? 'active' : ''}`}
        >
          <span>🪑 Bench Matchups & Sleepers</span>
          <span className="intel-nav-pill-count">{benchList.length}</span>
        </button>

        <button
          type="button"
          onClick={() => setSubView('opportunities')}
          className={`intel-nav-pill ${subView === 'opportunities' ? 'active' : ''}`}
        >
          <span>⚡ Starter vs Bench Opportunities</span>
          {matchupOpportunities.length > 0 && (
            <span className="intel-nav-pill-count" style={{ background: 'var(--accent-amber)', color: '#000' }}>
              {matchupOpportunities.length}
            </span>
          )}
        </button>

        <button
          type="button"
          onClick={() => setSubView('market')}
          className={`intel-nav-pill ${subView === 'market' ? 'active' : ''}`}
        >
          <span>📊 Market Buzz & Starter Battles</span>
          {marketBuzz.length > 0 && (
            <span className="intel-nav-pill-count" style={{ background: 'var(--accent-purple, #8b5cf6)', color: '#fff' }}>
              {marketBuzz.length}
            </span>
          )}
        </button>

        <button
          type="button"
          onClick={() => setSubView('wrcb')}
          className={`intel-nav-pill ${subView === 'wrcb' ? 'active' : ''}`}
        >
          <span>🎯 WR vs CB Secondary Matrix</span>
          <span className="intel-nav-pill-count">{wrcbData.length}</span>
        </button>

        <button
          type="button"
          onClick={() => setSubView('vegas')}
          className={`intel-nav-pill ${subView === 'vegas' ? 'active' : ''}`}
        >
          <span>🎰 Vegas Game Environments</span>
          <span className="intel-nav-pill-count">{vegasData?.games.length || 0}</span>
        </button>

        <button
          type="button"
          onClick={() => setSubView('dvp')}
          className={`intel-nav-pill ${subView === 'dvp' ? 'active' : ''}`}
        >
          <span>🛡️ Defense vs Position (DvP)</span>
          <span className="intel-nav-pill-count">32</span>
        </button>
      </div>

      {/* 5. FILTER & SEARCH CONTROLS */}
      {(subView === 'starters' || subView === 'bench' || subView === 'wrcb' || subView === 'vegas') && (
        <div className="intel-filter-bar">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            {/* Position Filter for Starters and Bench */}
            {(subView === 'starters' || subView === 'bench') && (
              <div style={{ display: 'flex', gap: '4px' }}>
                {['ALL', 'QB', 'RB', 'WR', 'TE', 'DST', 'K'].map((pos) => (
                  <button
                    key={pos}
                    type="button"
                    onClick={() => setPosFilter(pos)}
                    className={`btn btn-sm ${posFilter === pos ? 'btn-primary' : 'btn-secondary'}`}
                    style={{ padding: '4px 10px', fontSize: '11px' }}
                  >
                    {pos}
                  </button>
                ))}
              </div>
            )}

            {/* WR/CB Tag Filter */}
            {subView === 'wrcb' && (
              <div style={{ display: 'flex', gap: '4px' }}>
                {[
                  { id: 'ALL', label: 'All Wideouts' },
                  { id: 'ROSTERED', label: '👤 My Roster' },
                  { id: 'SHADOW', label: '🚨 Shadow Alerts' },
                  { id: 'SLOT', label: '🔥 Slot Mismatches' },
                  { id: 'FAVORABLE', label: '⭐ Favorable Edges' },
                ].map((f) => (
                  <button
                    key={f.id}
                    type="button"
                    onClick={() => setWrcbTagFilter(f.id)}
                    className={`btn btn-sm ${wrcbTagFilter === f.id ? 'btn-primary' : 'btn-secondary'}`}
                    style={{ padding: '4px 10px', fontSize: '11px' }}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
            )}

            {/* Vegas Script Filter */}
            {subView === 'vegas' && (
              <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                {[
                  { id: 'ALL', label: 'All Games' },
                  { id: 'MY_PLAYERS', label: '👤 Games with My Roster' },
                  { id: 'SHOOTOUT', label: '🔥 Shootouts (O/U ≥ 47.5)' },
                  { id: 'FAVORITE_RUN_FUNNEL', label: '🏃 Run Funnels' },
                  { id: 'UNDERDOG_PASS_FUNNEL', label: '📈 Pass Funnels' },
                  { id: 'DEFENSIVE_SLUGFEST', label: '🛡️ Slugfests' },
                ].map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => setScriptFilter(s.id)}
                    className={`btn btn-sm ${scriptFilter === s.id ? 'btn-primary' : 'btn-secondary'}`}
                    style={{ padding: '4px 10px', fontSize: '11px' }}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            )}
          </div>

          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search player, team, or opponent..."
            className="intel-search-input"
          />
        </div>
      )}

      {/* ===================================================================== */}
      {/* VIEW 1: STARTING LINEUP MATCHUPS (DEFAULT)                            */}
      {/* ===================================================================== */}
      {subView === 'starters' && (
        <div>
          {isLoadingWrcb ? (
            <div className="card" style={{ textAlign: 'center', padding: '48px', color: 'var(--text-muted)' }}>
              Loading starter matchup profiles...
            </div>
          ) : filteredStarters.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
              No starting players match your search filter.
            </div>
          ) : (
            <div className="intel-grid">
              {filteredStarters.map((s) => renderPlayerMatchupCard(s))}
            </div>
          )}
        </div>
      )}

      {/* ===================================================================== */}
      {/* VIEW 2: BENCH MATCHUPS & SLEEPERS                                     */}
      {/* ===================================================================== */}
      {subView === 'bench' && (
        <div>
          {isLoadingWrcb ? (
            <div className="card" style={{ textAlign: 'center', padding: '48px', color: 'var(--text-muted)' }}>
              Loading bench matchup profiles...
            </div>
          ) : filteredBench.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
              No bench players match your search filter.
            </div>
          ) : (
            <div className="intel-grid">
              {filteredBench.map((b) => renderPlayerMatchupCard(b))}
            </div>
          )}
        </div>
      )}

      {/* ===================================================================== */}
      {/* VIEW 3: STARTER VS BENCH MATCHUP OPPORTUNITIES                        */}
      {/* ===================================================================== */}
      {subView === 'opportunities' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {matchupOpportunities.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: '48px' }}>
              <div style={{ fontSize: '32px', marginBottom: '8px' }}>🛡️</div>
              <h3 style={{ fontSize: '18px', fontWeight: 800, marginBottom: '6px' }}>
                No High-Leverage Matchup Discrepancies Detected
              </h3>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', maxWidth: '520px', margin: '0 auto' }}>
                Your current active starting lineup is already matched up into the best available defensive spots on your roster.
              </p>
            </div>
          ) : (
            matchupOpportunities.map((opp, idx) => (
              <div key={idx} className="intel-opportunity-card">
                <div className="intel-opp-header">
                  <span className="intel-opp-badge">
                    ⚡ Matchup Leverage Opportunity: +{opp.starDelta}★ Edge
                  </span>
                  <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                    Position: {opp.bench.player.position}
                  </span>
                </div>

                <div className="intel-opp-body">
                  {/* Left: Active Starter (Tougher Matchup) */}
                  <div className="intel-opp-player starter-box">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span className="pill rose" style={{ fontSize: '10px', fontWeight: 800 }}>
                        CURRENT STARTER
                      </span>
                      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: '14px' }}>
                        {opp.starter.player.projected_points.toFixed(1)} pts
                      </span>
                    </div>
                    <div style={{ fontWeight: 800, fontSize: '16px' }}>
                      {opp.starter.player.full_name} ({opp.starter.player.pro_team})
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                      vs {opp.starter.player.opponent} • DvP #{opp.starter.player.opp_dvp_rank ?? 'N/A'}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '2px' }}>
                      <MatchupStarRating stars={opp.starter.stars} oppDvpRank={opp.starter.player.opp_dvp_rank} position={opp.starter.player.position} />
                      <span style={{ fontSize: '11px', color: 'var(--accent-rose)', fontWeight: 700 }}>
                        {opp.starter.stars}★ Matchup
                      </span>
                    </div>
                    {opp.starter.wrcb?.is_shadow_projected && (
                      <span className="pill rose" style={{ fontSize: '10px', marginTop: '4px' }}>
                        🚨 Shadow: {opp.starter.wrcb.primary_cb.name}
                      </span>
                    )}
                  </div>

                  {/* Center Divider */}
                  <div className="intel-opp-vs-divider">
                    <span style={{ fontSize: '14px' }}>⚡</span>
                    <span>VS</span>
                    <span className="intel-opp-edge-pill">
                      +{opp.starDelta}★
                    </span>
                  </div>

                  {/* Right: Bench Option (Superior Matchup) */}
                  <div className="intel-opp-player bench-box">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span className="pill emerald" style={{ fontSize: '10px', fontWeight: 800 }}>
                        BENCH LEVERAGE
                      </span>
                      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: '14px' }}>
                        {opp.bench.player.projected_points.toFixed(1)} pts
                      </span>
                    </div>
                    <div style={{ fontWeight: 800, fontSize: '16px' }}>
                      {opp.bench.player.full_name} ({opp.bench.player.pro_team})
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                      vs {opp.bench.player.opponent} • DvP #{opp.bench.player.opp_dvp_rank ?? 'N/A'}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '2px' }}>
                      <MatchupStarRating stars={opp.bench.stars} oppDvpRank={opp.bench.player.opp_dvp_rank} position={opp.bench.player.position} />
                      <span style={{ fontSize: '11px', color: 'var(--accent-emerald)', fontWeight: 700 }}>
                        {opp.bench.stars}★ Matchup
                      </span>
                    </div>
                    {opp.bench.wrcb?.advantage_rating === 'SLOT_MISMATCH' && (
                      <span className="pill emerald" style={{ fontSize: '10px', marginTop: '4px' }}>
                        🔥 Slot Mismatch (+{opp.bench.wrcb.advantage_score}%)
                      </span>
                    )}
                  </div>
                </div>

                <div className="intel-takeaway-box" style={{ borderLeftColor: 'var(--accent-amber)' }}>
                  💡 <strong>Analysis:</strong> {opp.reason}
                </div>

                <div className="intel-opp-cta-row">
                  {onCompareStarterWithBench && (
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={() => onCompareStarterWithBench(opp.starter.player)}
                    >
                      ⚔️ Compare in Start/Sit Tool
                    </button>
                  )}
                  {onSelectTab && (
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => onSelectTab('lineup')}
                    >
                      📋 Open Lineup Optimizer
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* ===================================================================== */}
      {/* VIEW 3.5: PREDICTION MARKET BUZZ & STARTER BATTLES (POLYMARKET)        */}
      {/* ===================================================================== */}
      {subView === 'market' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Week 1 Context & Kickoff Banner */}
          <div className="intel-dvp-banner" style={{ borderLeft: '4px solid var(--accent-purple, #8b5cf6)' }}>
            <div className="intel-dvp-banner-content">
              <div className="intel-dvp-banner-title">
                <span>🏈 Week 1 Prediction Market Intelligence (Polymarket Integration)</span>
                <span className="pill purple" style={{ fontSize: '10px', fontWeight: 800 }}>
                  Real-Money Crowd Probabilities
                </span>
              </div>
              <p className="intel-dvp-banner-text">
                Week 1 is the most unpredictable slate of the NFL calendar. Because zero regular-season snaps have occurred, official coach statements and depth charts are frequently guarded. <strong>Polymarket</strong> aggregates real-money crowd bets into live implied probabilities—pricing true starting quarterback battles, Thursday/Sunday game-time injury risks, and rookie target ceilings before kickoff.
              </p>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap', marginTop: '6px' }}>
                <span className="pill cyan" style={{ fontSize: '10.5px' }}>
                  ⚡ Free Public Gamma API Active
                </span>
                <span className="pill amber" style={{ fontSize: '10.5px' }}>
                  🚨 Thursday Night Kickoff Rule: Never place a Thursday starter in FLEX
                </span>
              </div>
            </div>
          </div>

          {isLoadingMarket ? (
            <div className="card" style={{ textAlign: 'center', padding: '48px', color: 'var(--text-muted)' }}>
              Loading Polymarket sentiment & starter battle odds...
            </div>
          ) : marketBuzz.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
              No active prediction market controversies detected for this week.
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: '16px' }}>
              {marketBuzz.map((m) => {
                const isControversy = m.has_starter_controversy
                const isDecoy = m.decoy_risk === 'HIGH' || m.decoy_risk === 'MODERATE'
                const isRookie = m.is_rookie
                const isTnf = m.is_thursday_kickoff

                return (
                  <div
                    key={m.player_id}
                    className="card"
                    style={{
                      background: 'var(--card-bg, #18181b)',
                      border: isTnf
                        ? '1px solid rgba(6, 182, 212, 0.6)'
                        : isDecoy
                        ? '1px solid rgba(244, 63, 94, 0.6)'
                        : isControversy
                        ? '1px solid rgba(245, 158, 11, 0.6)'
                        : '1px solid var(--border-color, #27272a)',
                      borderRadius: '12px',
                      padding: '16px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '12px',
                      position: 'relative',
                    }}
                  >
                    {/* Header Row */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span style={{ fontWeight: 800, fontSize: '16px', color: 'var(--text-primary)' }}>
                            {m.player_name}
                          </span>
                          <span className="pill zinc" style={{ fontSize: '10px' }}>
                            {m.position} • {m.pro_team}
                          </span>
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                          vs {m.opponent} {m.game_date ? `• ${m.game_date}` : ''}
                        </div>
                      </div>

                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px' }}>
                        {isTnf && (
                          <span className="pill cyan" style={{ fontSize: '10px', fontWeight: 800 }}>
                            🏈 TNF KICKOFF
                          </span>
                        )}
                        {m.decoy_risk === 'HIGH' ? (
                          <span className="pill rose" style={{ fontSize: '10px', fontWeight: 800 }}>
                            🚨 HIGH DECOY RISK
                          </span>
                        ) : m.decoy_risk === 'MODERATE' ? (
                          <span className="pill amber" style={{ fontSize: '10px', fontWeight: 700 }}>
                            ⚠️ MODERATE INJURY RISK
                          </span>
                        ) : null}
                        {isRookie && m.rookie_tier === 'DAY1_ALPHA' && (
                          <span className="pill purple" style={{ fontSize: '10px', fontWeight: 800 }}>
                            🌟 DAY-1 ALPHA
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Starter Probability Dial / Bar */}
                    <div style={{ background: 'rgba(0, 0, 0, 0.25)', borderRadius: '8px', padding: '10px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '6px' }}>
                        <span style={{ color: 'var(--text-secondary)' }}>Market Starter Confidence:</span>
                        <strong
                          style={{
                            fontFamily: 'var(--font-mono)',
                            color:
                              m.starter_confidence >= 0.75
                                ? 'var(--accent-emerald, #10b981)'
                                : m.starter_confidence >= 0.5
                                ? 'var(--accent-amber, #f59e0b)'
                                : 'var(--accent-rose, #f43f5e)',
                          }}
                        >
                          {Math.round(m.starter_confidence * 100)}%
                        </strong>
                      </div>
                      <div
                        style={{
                          width: '100%',
                          height: '8px',
                          background: 'rgba(255, 255, 255, 0.1)',
                          borderRadius: '4px',
                          overflow: 'hidden',
                        }}
                      >
                        <div
                          style={{
                            width: `${Math.round(m.starter_confidence * 100)}%`,
                            height: '100%',
                            background:
                              m.starter_confidence >= 0.75
                                ? 'var(--accent-emerald, #10b981)'
                                : m.starter_confidence >= 0.5
                                ? 'var(--accent-amber, #f59e0b)'
                                : 'var(--accent-rose, #f43f5e)',
                            borderRadius: '4px',
                            transition: 'width 0.4s ease',
                          }}
                        />
                      </div>
                      {m.starter_market_question && (
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '6px', fontStyle: 'italic' }}>
                          Market: "{m.starter_market_question}"
                        </div>
                      )}
                    </div>

                    {/* Injury Practice Status Details */}
                    {m.injury_status !== 'ACTIVE' && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px' }}>
                        <span style={{ color: 'var(--text-secondary)' }}>Official Status:</span>
                        <span className={`pill ${m.injury_status === 'QUESTIONABLE' ? 'amber' : 'rose'}`} style={{ fontSize: '10px' }}>
                          {m.injury_status}
                        </span>
                        {m.practice_status && (
                          <span className="pill zinc" style={{ fontSize: '10px' }}>
                            Practice: {m.practice_status}
                          </span>
                        )}
                      </div>
                    )}

                    {/* Headline Banner */}
                    <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--accent-cyan, #06b6d4)' }}>
                      {m.market_headline}
                    </div>

                    {/* Tactical Fantasy Advice */}
                    <div
                      className="intel-takeaway-box"
                      style={{
                        margin: 0,
                        fontSize: '12px',
                        borderLeftColor: isTnf ? 'var(--accent-cyan)' : isDecoy ? 'var(--accent-rose)' : 'var(--accent-amber)',
                      }}
                    >
                      💡 <strong>PPR Advice:</strong> {m.tactical_advice}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}


      {/* ===================================================================== */}
      {/* VIEW 4: WR vs CB SECONDARY MATRIX (ALL NFL SCOUTING)                  */}
      {/* ===================================================================== */}
      {subView === 'wrcb' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {isLoadingWrcb ? (
            <div className="card" style={{ textAlign: 'center', padding: '48px', color: 'var(--text-muted)' }}>
              Loading NFL WR vs CB matrix...
            </div>
          ) : filteredWrcbList.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
              No wide receivers match your current search or filter criteria.
            </div>
          ) : (
            <div className="intel-grid">
              {filteredWrcbList.map((item) => {
                const isUserStarter = lineup ? starterWRPids.has(item.player_id) : item.is_user_starter
                const isUserRostered = lineup ? rosteredWRPids.has(item.player_id) : item.is_user_rostered

                return (
                <div
                  key={item.player_id}
                  className={`intel-player-card ${isUserStarter ? 'starter' : isUserRostered ? 'bench' : ''}`}
                >
                  <div className="intel-card-header">
                    <div className="intel-player-identity">
                      <div className="intel-player-name-row">
                        <span className="intel-player-name">{item.full_name}</span>
                        {isUserStarter && (
                          <span className="pill emerald" style={{ fontSize: '9px', fontWeight: 800 }}>
                            MY STARTER
                          </span>
                        )}
                        {isUserRostered && !isUserStarter && (
                          <span className="pill zinc" style={{ fontSize: '9px', fontWeight: 700 }}>
                            MY BENCH
                          </span>
                        )}
                      </div>
                      <div className="intel-team-opp-badge" style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
                        <NFLTeamLogo team={item.pro_team} size={18} />
                        <strong>{item.pro_team}</strong> vs <NFLTeamLogo team={item.opponent} size={18} /> <strong>{item.opponent}</strong>
                        <span style={{ color: 'var(--text-muted)', fontSize: '11px', marginLeft: '4px' }}>
                          • Proj: {item.projected_points.toFixed(1)} pts
                        </span>
                      </div>
                    </div>

                    <div>{renderAdvantageBadge(item.advantage_rating, item.advantage_score)}</div>
                  </div>

                  {/* Route Alignment */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: 'var(--text-muted)' }}>
                    <span>Route Distribution:</span>
                    <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                      {(item.alignment.pct_slot * 100).toFixed(0)}% Slot / {(item.alignment.pct_wide * 100).toFixed(0)}% Wide
                    </span>
                  </div>

                  {/* CB Matchup Strip */}
                  <div className="intel-cb-strip">
                    <div className="intel-cb-header">
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span>Primary CB:</span>
                        <strong>{item.primary_cb.name}</strong>
                        {item.primary_cb.is_shadow && (
                          <span className="pill rose" style={{ fontSize: '9px', padding: '0 4px', fontWeight: 800 }}>
                            SHADOW
                          </span>
                        )}
                      </div>
                      {renderCbGradeBadge(item.primary_cb.coverage_grade)}
                    </div>

                    <div className="intel-cb-stats-row">
                      <div>Role: <span className="intel-cb-stat-val">{item.primary_cb.slot_role}</span></div>
                      <div>Catch Allowed: <span className="intel-cb-stat-val">{(item.primary_cb.catch_rate_allowed * 100).toFixed(0)}%</span></div>
                      <div>FP/Route: <span className="intel-cb-stat-val">{item.primary_cb.fpts_per_route_allowed.toFixed(2)}</span></div>
                    </div>
                  </div>

                  {/* Tactical Takeaway */}
                  <div className="intel-takeaway-box">
                    {item.tactical_takeaway}
                  </div>
                </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* ===================================================================== */}
      {/* VIEW 5: VEGAS GAME ENVIRONMENTS                                       */}
      {/* ===================================================================== */}
      {subView === 'vegas' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {isLoadingVegas ? (
            <div className="card" style={{ textAlign: 'center', padding: '48px', color: 'var(--text-muted)' }}>
              Loading Vegas betting environments...
            </div>
          ) : !vegasData || filteredVegasGames.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
              No Vegas games match your filter.
            </div>
          ) : (
            <div className="intel-grid">
              {filteredVegasGames.map((game) => {
                const hasRoster = game.user_roster_exposure.length > 0

                return (
                  <div
                    key={game.game_id}
                    className={`intel-vegas-card ${hasRoster ? 'roster-exposed' : ''}`}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px' }}>
                      <div>
                        <div style={{ fontWeight: 800, fontSize: '16px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span>{game.game_name}</span>
                          {game.is_dome && (
                            <span className="pill cyan" style={{ fontSize: '10px' }}>🏟️ Dome</span>
                          )}
                        </div>
                        <div style={{ fontSize: '11.5px', color: 'var(--text-muted)', marginTop: '2px' }}>
                          {game.venue_name}
                        </div>
                      </div>

                      <div>{renderScriptBadge(game.game_script, game.game_script_label)}</div>
                    </div>

                    {/* Odds Grid */}
                    <div className="intel-vegas-odds-grid">
                      <div className="intel-vegas-odds-cell">
                        <span className="intel-vegas-odds-label">Over / Under</span>
                        <span className="intel-vegas-odds-val" style={{ color: 'var(--accent-amber)' }}>
                          {game.over_under.toFixed(1)}
                        </span>
                      </div>
                      <div className="intel-vegas-odds-cell">
                        <span className="intel-vegas-odds-label">Line</span>
                        <span className="intel-vegas-odds-val">
                          {game.favorite_team} -{game.spread_magnitude.toFixed(1)}
                        </span>
                      </div>
                      <div className="intel-vegas-odds-cell">
                        <span className="intel-vegas-odds-label">Pace Index</span>
                        <span className="intel-vegas-odds-val" style={{ color: 'var(--accent-cyan)' }}>
                          {game.pace_index}
                        </span>
                      </div>
                    </div>

                    {/* Implied Scores */}
                    <div className="intel-vegas-scores-row">
                      <div>
                        <span style={{ color: 'var(--text-secondary)' }}>{game.away_team} (Away): </span>
                        <strong style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-emerald)' }}>
                          {game.away_implied_total.toFixed(1)} pts
                        </strong>
                      </div>
                      <span style={{ color: 'var(--text-muted)', fontWeight: 700 }}>vs</span>
                      <div>
                        <span style={{ color: 'var(--text-secondary)' }}>{game.home_team} (Home): </span>
                        <strong style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-emerald)' }}>
                          {game.home_implied_total.toFixed(1)} pts
                        </strong>
                      </div>
                    </div>

                    {/* Tactical Advice */}
                    <div className="intel-takeaway-box">
                      {game.tactical_advice}
                    </div>

                    {/* User Roster Exposure */}
                    {hasRoster && (
                      <div className="intel-vegas-exposure-chips">
                        <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-secondary)', marginRight: '4px' }}>
                          My Players in Game:
                        </span>
                        {game.user_roster_exposure.map((p) => (
                          <span
                            key={p.player_id}
                            className={`pill ${p.is_starter ? 'emerald' : 'zinc'}`}
                            style={{ fontSize: '11px', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                          >
                            <span>{p.full_name}</span>
                            <span style={{ fontSize: '9px', opacity: 0.8 }}>({p.position})</span>
                            {p.is_starter ? (
                              <span style={{ fontWeight: 800, fontSize: '9px', color: '#fff' }}>START</span>
                            ) : (
                              <span style={{ fontWeight: 700, fontSize: '9px', opacity: 0.75 }}>BENCH</span>
                            )}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* ===================================================================== */}
      {/* VIEW 6: DEFENSE VS POSITION (DvP) FANTASY MATRIX                      */}
      {/* ===================================================================== */}
      {subView === 'dvp' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Week 1 Baseline Explainer Banner & Synchronization Bar */}
          <div className="intel-dvp-banner">
            <div className="intel-dvp-banner-content">
              <div className="intel-dvp-banner-title">
                <span>🛡️ NFL Defense vs Position (DvP) Fantasy Points Allowed</span>
                <span className="pill cyan" style={{ fontSize: '10px' }}>DraftKings & FanDuel Scoring</span>
              </div>
              <p className="intel-dvp-banner-text">
                Rankings evaluate defensive matchup generosity per position group. In <strong>Week 1</strong>, zero 2026-27 regular season games have occurred; ratings are calibrated from the full <strong>2025-26 regular season</strong> with heavy weighting on the final 8 games. As 2026-27 games are played, current-season data automatically enters the blend. Higher DK FPA represents a softer, more favorable fantasy matchup.
              </p>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginTop: '4px' }}>
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

            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '8px' }}>
              <button
                type="button"
                onClick={handleSyncDvp}
                disabled={isSyncingDvp}
                className="btn btn-primary btn-sm"
                style={{ padding: '6px 14px', fontSize: '12px', fontWeight: 700 }}
              >
                {isSyncingDvp ? '⏳ Syncing DraftEdge...' : '🔄 Sync DvP Feed'}
              </button>
              <span style={{ fontSize: '10.5px', color: 'var(--text-muted)' }}>
                Auto-seeded fallback active
              </span>
            </div>
          </div>

          {/* Controls: Position Pills and Search Bar */}
          <div className="intel-filter-bar">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              <div className="intel-dvp-pos-selector">
                {(['QB', 'RB', 'WR', 'TE'] as const).map((pos) => (
                  <button
                    key={pos}
                    type="button"
                    onClick={() => setDvpPosition(pos)}
                    className={`intel-dvp-pos-btn ${dvpPosition === pos ? 'active' : ''}`}
                  >
                    {pos === 'QB' ? '🎯 QB Matchups' : pos === 'RB' ? '🏃 RB Matchups' : pos === 'WR' ? '⚡ WR Matchups' : '🛡️ TE Matchups'}
                  </button>
                ))}
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Filter by team (e.g. KC, Bills)..."
                className="intel-search-input"
                style={{ width: '220px' }}
              />
            </div>
          </div>

          {/* DvP Matrix Table */}
          {isLoadingDvp ? (
            <div className="card" style={{ textAlign: 'center', padding: '48px', color: 'var(--text-muted)' }}>
              Loading {dvpPosition} Defense vs Position ratings...
            </div>
          ) : sortedDvpRatings.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
              No defensive teams found matching your filter.
            </div>
          ) : (
            <div className="intel-dvp-table-wrap">
              <table className="intel-dvp-table">
                <thead>
                  <tr>
                    <th onClick={() => { setDvpSortCol('rank_softness'); setDvpSortAsc(!dvpSortAsc) }}>
                      Softness Rank {dvpSortCol === 'rank_softness' ? (dvpSortAsc ? '▲' : '▼') : ''}
                    </th>
                    <th onClick={() => { setDvpSortCol('team_name'); setDvpSortAsc(!dvpSortAsc) }}>
                      Defensive Team {dvpSortCol === 'team_name' ? (dvpSortAsc ? '▲' : '▼') : ''}
                    </th>
                    <th>Matchup Tier</th>
                    <th>My Roster Exposure</th>
                    <th onClick={() => { setDvpSortCol('dk_fpa'); setDvpSortAsc(!dvpSortAsc) }}>
                      DK FPA {dvpSortCol === 'dk_fpa' ? (dvpSortAsc ? '▲' : '▼') : ''}
                    </th>
                    <th>FD FPA</th>
                    <th onClick={() => { setDvpSortCol('vs_avg'); setDvpSortAsc(!dvpSortAsc) }}>
                      vs Pos Avg {dvpSortCol === 'vs_avg' ? (dvpSortAsc ? '▲' : '▼') : ''}
                    </th>
                    <th>2025-26 Base</th>
                    <th>2026-27 Curr</th>
                    <th>L4 Trend</th>
                    {/* Position-Specific Stat Columns */}
                    {dvpPosition === 'QB' && (
                      <>
                        <th>Pass Yds/G</th>
                        <th>Pass TD/G</th>
                        <th>Sacks/G</th>
                        <th>Rush Yds/G</th>
                      </>
                    )}
                    {dvpPosition === 'RB' && (
                      <>
                        <th>Rush Yds/G</th>
                        <th>Rush TD/G</th>
                        <th>Targets/G</th>
                        <th>Rec Yds/G</th>
                      </>
                    )}
                    {dvpPosition === 'WR' && (
                      <>
                        <th>Rec Yds/G</th>
                        <th>Rec TD/G</th>
                        <th>Targets/G</th>
                        <th>Rec/G</th>
                      </>
                    )}
                    {dvpPosition === 'TE' && (
                      <>
                        <th>Rec Yds/G</th>
                        <th>Rec TD/G</th>
                        <th>Targets/G</th>
                        <th>Rec/G</th>
                      </>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {sortedDvpRatings.map((row) => {
                    const facingPlayers = rosterOpponents.get(row.pro_team.toUpperCase()) || []
                    const isFacingMyTeam = facingPlayers.length > 0
                    const posFacing = facingPlayers.filter((p) => p.position === dvpPosition)

                    return (
                      <tr
                        key={row.id}
                        className={isFacingMyTeam ? 'roster-facing' : ''}
                      >
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

                        {/* Team */}
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

                        {/* My Roster Exposure */}
                        <td>
                          {posFacing.length > 0 ? (
                            <span
                              className="pill cyan"
                              style={{ fontSize: '10px', fontWeight: 700 }}
                              title={`Facing your active ${dvpPosition}: ${posFacing.map((p) => p.full_name).join(', ')}`}
                            >
                              ⚔️ Faces Your {dvpPosition} ({posFacing.map((p) => p.full_name.split(' ').pop()).join(', ')})
                            </span>
                          ) : isFacingMyTeam ? (
                            <span
                              className="pill zinc"
                              style={{ fontSize: '9.5px' }}
                              title={`Facing other roster players: ${facingPlayers.map((p) => `${p.full_name} (${p.position})`).join(', ')}`}
                            >
                              Facing {facingPlayers[0].full_name.split(' ').pop()} ({facingPlayers[0].position})
                            </span>
                          ) : (
                            <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>—</span>
                          )}
                        </td>

                        {/* DK FPA */}
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

                        {/* FD FPA */}
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
                            <td>{row.supporting_stats?.rush_yds ? `${row.supporting_stats.rush_yds.toFixed(0)} yds` : '—'}</td>
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
      )}
    </div>
  )
}
