import { useState, useEffect, useRef } from 'react'
import type {
  LeagueSummaryResponse,
  OptimizedLineupResult,
  PlayerDirectoryItem,
  ScoringWeights,
  ScoringSettings,
  ComparisonResult,
  StartSitEvaluation,
  PreFlightPushPreview,
  LineupPushResponse,
  InactiveAlertItem,
  InactiveAlertsResponse,
  WaiverAnalysisResult,
  ConsolidationTradeAnalysisResult,
  InjuryFeedResponse,
  BacktestReport,
  MatchupResponseItem,
  TeamSummary,
  SlotAssignment,
  WRCBMatchupAnalysis,
  VegasIntelligenceResponse,
  TeamRosterResponse,
} from './types'

// Extracted Modals
import { PreFlightPushModal } from './components/modals/PreFlightPushModal'

// Extracted Tabs
import { LineupTab } from './components/tabs/LineupTab'
import { CompareTab } from './components/tabs/CompareTab'
import { WaiversTab } from './components/tabs/WaiversTab'
import { TradesTab } from './components/tabs/TradesTab'
import { InjuriesTab } from './components/tabs/InjuriesTab'
import { LeagueTab } from './components/tabs/LeagueTab'
import { SettingsTab } from './components/tabs/SettingsTab'
import { FantasyProsTab } from './components/tabs/FantasyProsTab'
import { IntelTab } from './components/tabs/IntelTab'
import { DfsTab } from './components/tabs/DfsTab'
import { VegasTab } from './components/tabs/VegasTab'

export function App() {
  // Navigation & View State
  const [activeTab, setActiveTab] = useState<
    'lineup' | 'compare' | 'waivers' | 'trades' | 'injuries' | 'league' | 'settings' | 'fantasypros' | 'intel' | 'dfs' | 'vegas'
  >('lineup')
  const [strategyMode, setStrategyMode] = useState<'BALANCED' | 'CEILING' | 'FLOOR' | 'AUTO'>(() => {
    const saved = localStorage.getItem('agy_strategy_mode')
    if (saved === 'BALANCED' || saved === 'CEILING' || saved === 'FLOOR' || saved === 'AUTO') return saved
    return 'BALANCED'
  })
  const [projectionSource, setProjectionSource] = useState<'MODEL' | 'CONSENSUS' | 'FANTASYPROS' | 'SLEEPER' | 'ESPN'>(() => {
    const saved = localStorage.getItem('agy_projection_source')
    if (saved === 'MODEL' || saved === 'CONSENSUS' || saved === 'FANTASYPROS' || saved === 'SLEEPER' || saved === 'ESPN') return saved
    return 'MODEL'
  })
  const [lineupViewMode, setLineupViewMode] = useState<'split' | 'unified'>(() => {
    const saved = localStorage.getItem('agy_lineup_view_mode')
    if (saved === 'split' || saved === 'unified') return saved
    return 'split'
  })
  const [showMatchupKey, setShowMatchupKey] = useState<boolean>(false)

  // Client Tab Memoization Refs to prevent redundant roundtrips on instant navigation
  const lastLoadedLineupKey = useRef<string>('')
  const lastLoadedIntelTeamId = useRef<number | null>(null)

  // Persist user view preferences across page reloads
  useEffect(() => {
    try {
      localStorage.setItem('agy_strategy_mode', strategyMode)
    } catch {
      // Ignore in restricted environments
    }
  }, [strategyMode])

  useEffect(() => {
    try {
      localStorage.setItem('agy_projection_source', projectionSource)
    } catch {
      // Ignore in restricted environments
    }
  }, [projectionSource])

  useEffect(() => {
    try {
      localStorage.setItem('agy_lineup_view_mode', lineupViewMode)
    } catch {
      // Ignore in restricted environments
    }
  }, [lineupViewMode])

  // Primary Data State
  const [league, setLeague] = useState<LeagueSummaryResponse | null>(null)
  const [selectedTeamId, setSelectedTeamId] = useState<number>(1)
  const [lineup, setLineup] = useState<OptimizedLineupResult | null>(null)
  const [allPlayers, setAllPlayers] = useState<PlayerDirectoryItem[]>([])
  const [inactivesAlerts, setInactivesAlerts] = useState<InactiveAlertItem[]>([])

  // Feature-Specific Data State
  const [waivers, setWaivers] = useState<WaiverAnalysisResult | null>(null)
  const [consolidationTrades, setConsolidationTrades] = useState<ConsolidationTradeAnalysisResult | null>(null)
  const [isLoadingTrades, setIsLoadingTrades] = useState<boolean>(false)
  const [injuriesFeed, setInjuriesFeed] = useState<InjuryFeedResponse | null>(null)
  const [isLoadingInjuries, setIsLoadingInjuries] = useState<boolean>(false)
  const [matchups, setMatchups] = useState<MatchupResponseItem[]>([])
  const [matchupWeek, setMatchupWeek] = useState<number>(1)
  const [selectedRosterTeamId, setSelectedRosterTeamId] = useState<number>(1)
  const [teamRosterData, setTeamRosterData] = useState<TeamRosterResponse | null>(null)
  const [teamRostersCache, setTeamRostersCache] = useState<Record<number, TeamRosterResponse>>({})
  const [isLoadingRoster, setIsLoadingRoster] = useState<boolean>(false)
  const [backtest, setBacktest] = useState<BacktestReport | null>(null)
  const [tuningMessage, setTuningMessage] = useState<string | null>(null)

  // Matchup & Market Intel State
  const [wrcbData, setWrcbData] = useState<WRCBMatchupAnalysis[]>([])
  const [vegasData, setVegasData] = useState<VegasIntelligenceResponse | null>(null)
  const [isLoadingIntel, setIsLoadingIntel] = useState<boolean>(false)
  const intelReqSeq = useRef<number>(0)

  // Model Weights & Settings
  const [weights, setWeights] = useState<ScoringWeights>({
    projection_weight: 0.35,
    opportunity_weight: 0.20,
    matchup_weight: 0.20,
    environment_weight: 0.10,
    health_weight: 0.10,
    weather_weight: 0.05,
  })
  const [leagueSizeSetting, setLeagueSizeSetting] = useState<number>(8)

  // Custom Lineup Substitutions (What-If Sandbox)
  const [customSubstitutions, setCustomSubstitutions] = useState<{ [slotIdx: number]: StartSitEvaluation }>({})
  const [activeSwapSlotIndex, setActiveSwapSlotIndex] = useState<number | null>(null)
  const [expandedWhy, setExpandedWhy] = useState<number | null>(null)
  const [expandedStatsPlayerId, setExpandedStatsPlayerId] = useState<number | null>(null)

  // Start/Sit Comparator State
  const [compareIds, setCompareIds] = useState<number[]>([])
  const [comparisonResult, setComparisonResult] = useState<ComparisonResult | null>(null)
  const [isExplicitCompare, setIsExplicitCompare] = useState<boolean>(false)

  // Push to ESPN State
  const [showPushModal, setShowPushModal] = useState<boolean>(false)
  const [pushPreview, setPushPreview] = useState<PreFlightPushPreview | null>(null)
  const [isPushing, setIsPushing] = useState<boolean>(false)
  const [pushResult, setPushResult] = useState<LineupPushResponse | null>(null)
  const [selectedMoveIds, setSelectedMoveIds] = useState<number[]>([])

  // Global Sync & Loading State
  const [isSyncing, setIsSyncing] = useState<boolean>(false)
  const [syncMessage, setSyncMessage] = useState<string | null>(null)

  // Initial Load
  useEffect(() => {
    loadLeagueData()
    loadWeights()
    loadAllPlayers()
    loadInjuries()
  }, [])

  // When selected team changes, load lineup, waivers, trades, and inactives
  useEffect(() => {
    if (selectedTeamId) {
      loadTeamLineup(selectedTeamId, strategyMode, projectionSource)
      loadWaivers(selectedTeamId)
      loadConsolidationTrades(selectedTeamId)
      loadBacktestReport(selectedTeamId)
      checkInactivesAlerts(selectedTeamId)
      loadIntelData(selectedTeamId)
    }
  }, [selectedTeamId])

  // When selected roster team changes in League tab
  useEffect(() => {
    if (selectedRosterTeamId) {
      loadTeamRoster(selectedRosterTeamId)
    }
  }, [selectedRosterTeamId])

  // When matchupWeek changes
  useEffect(() => {
    if (matchupWeek) {
      loadMatchups(matchupWeek)
    }
  }, [matchupWeek])

  const loadLeagueData = async () => {
    try {
      const res = await fetch('/api/league/summary')
      if (res.ok) {
        const data: LeagueSummaryResponse = await res.json()
        setLeague(data)
        const userTeam = data.user_team_id || (data.teams.length > 0 ? data.teams[0].id : 1)
        if (selectedTeamId !== userTeam) {
          setIsExplicitCompare(false)
          setSelectedTeamId(userTeam)
        }
        setSelectedRosterTeamId(userTeam)
        loadTeamRoster(userTeam)
        prefetchAllTeamRosters(data.teams)
        const curWeek = data.current_week || 1
        setMatchupWeek(curWeek)
        loadMatchups(curWeek)
      } else {
        await handleSync(true)
      }
    } catch {
      await handleSync(true)
    }
  }

  const loadAllPlayers = async () => {
    try {
      const res = await fetch('/api/league/players')
      if (res.ok) {
        const data: PlayerDirectoryItem[] = await res.json()
        setAllPlayers(data)
      }
    } catch (err) {
      console.error('Failed to load players directory:', err)
    }
  }

  const loadInjuries = async () => {
    setIsLoadingInjuries(true)
    try {
      const res = await fetch('/api/injuries?limit=250')
      if (res.ok) {
        const data: InjuryFeedResponse = await res.json()
        setInjuriesFeed(data)
      }
    } catch (err) {
      console.error('Failed to load injuries:', err)
    } finally {
      setIsLoadingInjuries(false)
    }
  }

  const loadMatchups = async (week: number) => {
    try {
      const res = await fetch(`/api/league/matchups?week=${week}`)
      if (res.ok) {
        const data: MatchupResponseItem[] = await res.json()
        setMatchups(data)
      }
    } catch (err) {
      console.error('Failed to load matchups:', err)
    }
  }

  const loadTeamRoster = async (teamId: number, forceRefresh = false) => {
    // If cached in memory and not forcing a refresh, apply immediately with 0 latency
    if (!forceRefresh && teamRostersCache[teamId]) {
      setTeamRosterData(teamRostersCache[teamId])
      return
    }

    setIsLoadingRoster(true)
    try {
      const res = await fetch(`/api/league/teams/${teamId}/roster`)
      if (res.ok) {
        const data: TeamRosterResponse = await res.json()
        setTeamRostersCache((prev) => ({ ...prev, [teamId]: data }))
        setTeamRosterData(data)
      } else {
        const altRes = await fetch(`/api/league/roster?team_id=${teamId}`)
        if (altRes.ok) {
          const data: TeamRosterResponse = await altRes.json()
          setTeamRostersCache((prev) => ({ ...prev, [teamId]: data }))
          setTeamRosterData(data)
        }
      }
    } catch (err) {
      console.error('Failed to load team roster:', err)
    } finally {
      setIsLoadingRoster(false)
    }
  }

  // Pre-fetch all league member rosters in parallel so browsing any team is instant
  const prefetchAllTeamRosters = async (teams: TeamSummary[]) => {
    if (!teams || teams.length === 0) return
    try {
      const promises = teams.map(async (t) => {
        try {
          const res = await fetch(`/api/league/teams/${t.id}/roster`)
          if (res.ok) {
            const data: TeamRosterResponse = await res.json()
            return { teamId: t.id, data }
          }
        } catch {
          // Ignore background prefetch errors
        }
        return null
      })
      const results = await Promise.all(promises)
      const newCache: Record<number, TeamRosterResponse> = {}
      for (const r of results) {
        if (r && r.data) {
          newCache[r.teamId] = r.data
        }
      }
      if (Object.keys(newCache).length > 0) {
        setTeamRostersCache((prev) => ({ ...prev, ...newCache }))
      }
    } catch (err) {
      console.error('Failed to prefetch all team rosters:', err)
    }
  }

  // Seamless handler to switch inspected roster team with instant cache retrieval
  const handleSelectRosterTeam = (teamId: number) => {
    setSelectedRosterTeamId(teamId)
    if (teamRostersCache[teamId]) {
      setTeamRosterData(teamRostersCache[teamId])
    } else {
      setTeamRosterData(null)
      loadTeamRoster(teamId)
    }
  }

  const loadWaivers = async (teamId: number) => {
    try {
      const res = await fetch(`/api/waiver/upgrades?team_id=${teamId}`)
      if (res.ok) {
        const data: WaiverAnalysisResult = await res.json()
        setWaivers(data)
      }
    } catch (err) {
      console.error('Failed to load waivers:', err)
    }
  }

  const loadConsolidationTrades = async (teamId: number) => {
    setIsLoadingTrades(true)
    try {
      const res = await fetch(`/api/recommendation/trades/consolidation?team_id=${teamId}`)
      if (res.ok) {
        const data: ConsolidationTradeAnalysisResult = await res.json()
        setConsolidationTrades(data)
      }
    } catch (err) {
      console.error('Failed to load consolidation trades:', err)
    } finally {
      setIsLoadingTrades(false)
    }
  }

  const loadBacktestReport = async (teamId: number) => {
    try {
      const res = await fetch(`/api/backtest/report?team_id=${teamId}`)
      if (res.ok) {
        const data: BacktestReport = await res.json()
        setBacktest(data)
      }
    } catch (err) {
      console.error('Failed to load backtest report:', err)
    }
  }

  const loadWeights = async () => {
    try {
      const res = await fetch('/api/recommendation/settings')
      if (res.ok) {
        const data: ScoringSettings = await res.json()
        setWeights(data.weights)
        setLeagueSizeSetting(data.league_size)
      }
    } catch (err) {
      console.error('Failed to load weights:', err)
    }
  }

  const handleWeightChange = (key: keyof ScoringWeights, val: number) => {
    setWeights((prev) => ({ ...prev, [key]: val }))
  }

  const handleSaveWeights = async () => {
    try {
      const res = await fetch('/api/recommendation/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ league_size: leagueSizeSetting, weights }),
      })
      if (res.ok) {
        const updated: ScoringSettings = await res.json()
        setWeights(updated.weights)
        setLeagueSizeSetting(updated.league_size)
        setTuningMessage('Settings saved successfully and persisted in database!')
        loadTeamLineup(selectedTeamId, strategyMode, projectionSource, true)
      }
    } catch (err) {
      setTuningMessage(`Save failed: ${err}`)
    }
  }

  const handleRunBacktesting = async () => {
    try {
      const res = await fetch(`/api/backtest/tune?team_id=${selectedTeamId}`, { method: 'POST' })
      if (res.ok) {
        const data = await res.json()
        setWeights(data.optimized_weights)
        setTuningMessage(data.message)
        loadTeamLineup(selectedTeamId, strategyMode, projectionSource, true)
        loadBacktestReport(selectedTeamId)
      }
    } catch (err) {
      setTuningMessage(`Tuning failed: ${err}`)
    }
  }

  const loadTeamLineup = async (teamId: number, mode?: string, source?: string, force = false) => {
    try {
      const activeMode = mode || strategyMode
      const activeSource = source || projectionSource
      const cacheKey = `${teamId}_${activeMode}_${activeSource}`
      if (!force && lastLoadedLineupKey.current === cacheKey && lineup) {
        return
      }
      lastLoadedLineupKey.current = cacheKey
      const res = await fetch(
        `/api/lineup/optimal?team_id=${teamId}&mode=${activeMode}&projection_source=${activeSource}`
      )
      if (res.ok) {
        const data: OptimizedLineupResult = await res.json()
        setLineup(data)
        setCustomSubstitutions({})
        setActiveSwapSlotIndex(null)

        // Check if current compareIds belong to this team's roster
        const rosterPlayerIds = new Set<number>()
        data.starters.forEach((s: SlotAssignment) => rosterPlayerIds.add(s.recommended_player.player_id))
        data.bench.forEach((b: StartSitEvaluation) => rosterPlayerIds.add(b.player_id))

        const hasForeignPlayers = compareIds.length > 0 && compareIds.some((id) => !rosterPlayerIds.has(id))

        // Seed comparator defaults with close-call candidates if not explicit or if current candidates not in this team
        if (!isExplicitCompare || hasForeignPlayers || compareIds.length === 0) {
          if (data.close_calls && data.close_calls.length > 0) {
            const cc = data.close_calls[0]
            const ids = [cc.starter.player_id, cc.bench_player.player_id]
            setCompareIds(ids)
            runComparison(ids, activeMode, activeSource)
          } else if (data.starters.length > 0 && data.bench.length > 0) {
            const benchCand = data.bench[0]
            const matchingStarter = data.starters.find(
              (s: SlotAssignment) =>
                s.recommended_player.position === benchCand.position ||
                ['RB', 'WR', 'TE'].includes(benchCand.position)
            )
            const starterId = matchingStarter
              ? matchingStarter.recommended_player.player_id
              : data.starters[0].recommended_player.player_id
            const ids = [starterId, benchCand.player_id]
            setCompareIds(ids)
            runComparison(ids, activeMode, activeSource)
          } else {
            setCompareIds([])
            setComparisonResult(null)
          }
        }
      }
    } catch (err) {
      console.error('Error loading lineup:', err)
    }
  }

  const checkInactivesAlerts = async (teamId: number) => {
    try {
      const res = await fetch(`/api/lineup/inactives-alert?team_id=${teamId}`)
      if (res.ok) {
        const data: InactiveAlertsResponse = await res.json()
        setInactivesAlerts(data.alerts || [])
      }
    } catch (err) {
      console.error('Error checking inactives:', err)
    }
  }

  const loadIntelData = async (teamId: number, force = false) => {
    if (!force && lastLoadedIntelTeamId.current === teamId && wrcbData.length > 0 && vegasData) {
      return
    }
    lastLoadedIntelTeamId.current = teamId
    const seq = ++intelReqSeq.current
    try {
      setIsLoadingIntel(true)
      const [wrcbRes, vegasRes] = await Promise.all([
        fetch(`/api/analysis/wrcb-matrix?team_id=${teamId}`),
        fetch(`/api/analysis/vegas-environments?team_id=${teamId}`),
      ])
      if (seq !== intelReqSeq.current) return
      if (wrcbRes.ok) {
        const wdata: WRCBMatchupAnalysis[] = await wrcbRes.json()
        setWrcbData(wdata)
      }
      if (vegasRes.ok) {
        const vdata: VegasIntelligenceResponse = await vegasRes.json()
        setVegasData(vdata)
      }
    } catch (err) {
      console.error('Error loading matchup intel:', err)
    } finally {
      if (seq === intelReqSeq.current) {
        setIsLoadingIntel(false)
      }
    }
  }

  const handleSync = async (force = false) => {
    setIsSyncing(true)
    setSyncMessage(null)
    lastLoadedLineupKey.current = ''
    lastLoadedIntelTeamId.current = null
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 45000)
    try {
      const res = await fetch(`/api/league/sync?force=${force}`, {
        method: 'POST',
        signal: controller.signal,
      })
      const data = await res.json()
      setSyncMessage(data.message)

      // Reload fresh league data
      const summaryRes = await fetch('/api/league/summary', { signal: controller.signal })
      if (summaryRes.ok) {
        const summaryData: LeagueSummaryResponse = await summaryRes.json()
        setLeague(summaryData)
        const teamId = summaryData.user_team_id || (summaryData.teams.length > 0 ? summaryData.teams[0].id : 1)
        setSelectedTeamId(teamId)
        loadTeamLineup(teamId, strategyMode, projectionSource, true)
        loadWaivers(teamId)
        loadAllPlayers()
        loadInjuries()
        checkInactivesAlerts(teamId)
        loadIntelData(teamId, true)
      }
    } catch (err: any) {
      if (err?.name === 'AbortError') {
        setSyncMessage('Sync timed out after 45 seconds. Check connection and try again.')
      } else {
        setSyncMessage(`Sync failed: ${err?.message || err}`)
      }
    } finally {
      clearTimeout(timeoutId)
      setIsSyncing(false)
    }
  }

  const handleStrategyChange = (newMode: 'BALANCED' | 'CEILING' | 'FLOOR' | 'AUTO') => {
    setStrategyMode(newMode)
    loadTeamLineup(selectedTeamId, newMode, projectionSource, true)
    if (compareIds.length >= 2) {
      runComparison(compareIds, newMode, projectionSource)
    }
  }

  const handleProjectionSourceChange = (newSource: 'MODEL' | 'CONSENSUS' | 'FANTASYPROS' | 'SLEEPER' | 'ESPN') => {
    setProjectionSource(newSource)
    loadTeamLineup(selectedTeamId, strategyMode, newSource, true)
    if (compareIds.length >= 2) {
      runComparison(compareIds, strategyMode, newSource)
    }
  }

  const runComparison = async (ids: number[], mode?: string, source?: string) => {
    if (ids.length < 2) return
    try {
      const activeMode = mode || strategyMode
      const activeSource = source || projectionSource
      const res = await fetch('/api/recommendation/compare', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          player_ids: ids,
          mode: activeMode,
          projection_source: activeSource,
        }),
      })
      if (res.ok) {
        const data: ComparisonResult = await res.json()
        setComparisonResult(data)
      }
    } catch (err) {
      console.error('Comparison error:', err)
    }
  }

  const handleCompareStarterWithBench = (starterPlayer: StartSitEvaluation) => {
    if (!lineup) return
    const matchingBench = lineup.bench
      .filter((b: StartSitEvaluation) => b.position === starterPlayer.position)
      .sort((a: StartSitEvaluation, b: StartSitEvaluation) => b.start_score - a.start_score)

    const targetBench = matchingBench.length > 0 ? matchingBench[0] : lineup.bench[0]
    if (targetBench) {
      const ids = [starterPlayer.player_id, targetBench.player_id]
      setIsExplicitCompare(true)
      setCompareIds(ids)
      runComparison(ids, strategyMode, projectionSource)
      setActiveTab('compare')
    }
  }

  const handleCompareBenchWithStarter = (benchPlayer: StartSitEvaluation) => {
    if (!lineup) return
    let targetStarter: StartSitEvaluation | null = null
    const samePosStarters = lineup.starters
      .map((s: SlotAssignment) => s.recommended_player)
      .filter((s: StartSitEvaluation) => s.position === benchPlayer.position)
      .sort((a: StartSitEvaluation, b: StartSitEvaluation) => a.start_score - b.start_score)

    if (samePosStarters.length > 0) {
      targetStarter = samePosStarters[0]
    } else if (['RB', 'WR', 'TE'].includes(benchPlayer.position)) {
      const flexStarters = lineup.starters
        .map((s: SlotAssignment) => s.recommended_player)
        .filter((s: StartSitEvaluation) => ['RB', 'WR', 'TE'].includes(s.position))
        .sort((a: StartSitEvaluation, b: StartSitEvaluation) => a.start_score - b.start_score)
      if (flexStarters.length > 0) {
        targetStarter = flexStarters[0]
      }
    }

    if (!targetStarter && lineup.starters.length > 0) {
      targetStarter = lineup.starters[0].recommended_player
    }

    if (targetStarter) {
      const ids = [targetStarter.player_id, benchPlayer.player_id]
      setIsExplicitCompare(true)
      setCompareIds(ids)
      runComparison(ids, strategyMode, projectionSource)
      setActiveTab('compare')
    }
  }

  const handleCompareFromRoster = (player: any) => {
    if (!lineup) return
    const match = lineup.starters.find(
      (s: SlotAssignment) => s.recommended_player.position === player.position
    )
    const starterId = match ? match.recommended_player.player_id : lineup.starters[0]?.recommended_player.player_id
    const targetPlayerId = player.player_id ?? player.id
    if (starterId && targetPlayerId) {
      const ids = [starterId, targetPlayerId]
      setIsExplicitCompare(true)
      setCompareIds(ids)
      runComparison(ids, strategyMode, projectionSource)
      setActiveTab('compare')
    }
  }

  const handleClearComparison = () => {
    setCompareIds([])
    setComparisonResult(null)
    setIsExplicitCompare(true)
  }

  const handleAutoLoadRosterDilemma = () => {
    if (!lineup) return
    setIsExplicitCompare(true)
    if (lineup.close_calls && lineup.close_calls.length > 0) {
      const cc = lineup.close_calls[0]
      const ids = [cc.starter.player_id, cc.bench_player.player_id]
      setCompareIds(ids)
      runComparison(ids, strategyMode, projectionSource)
    } else if (lineup.starters.length > 0 && lineup.bench.length > 0) {
      const benchCand = lineup.bench[0]
      const matchingStarter = lineup.starters.find(
        (s: SlotAssignment) =>
          s.recommended_player.position === benchCand.position ||
          ['RB', 'WR', 'TE'].includes(benchCand.position)
      )
      const starterId = matchingStarter
        ? matchingStarter.recommended_player.player_id
        : lineup.starters[0].recommended_player.player_id
      const ids = [starterId, benchCand.player_id]
      setCompareIds(ids)
      runComparison(ids, strategyMode, projectionSource)
    }
  }

  const handleOpenPushModal = async () => {
    setIsPushing(true)
    setPushResult(null)
    try {
      const res = await fetch('/api/lineup/push', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          team_id: selectedTeamId,
          confirm: false,
          mode: strategyMode,
          projection_source: projectionSource,
          custom_starter_ids:
            Object.keys(customSubstitutions).length > 0 && lineup
              ? lineup.starters.map((slot: SlotAssignment, idx: number) =>
                  customSubstitutions[idx]
                    ? customSubstitutions[idx].player_id
                    : slot.recommended_player.player_id
                )
              : undefined,
        }),
      })
      if (res.ok) {
        const preview: PreFlightPushPreview = await res.json()
        setPushPreview(preview)
        setSelectedMoveIds(preview.moves.map((m) => m.player_id))
        setShowPushModal(true)
      }
    } catch (err) {
      console.error('Error getting pre-flight push preview:', err)
    } finally {
      setIsPushing(false)
    }
  }

  const handleExecutePush = async () => {
    if (!pushPreview) return
    setIsPushing(true)
    try {
      const movesToPush = pushPreview.moves
        .filter((m) => selectedMoveIds.includes(m.player_id))
        .map((m) => ({
          player_id: m.player_id,
          from_slot_id: m.from_slot_id,
          to_slot_id: m.to_slot_id,
        }))

      const res = await fetch('/api/lineup/push', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          team_id: selectedTeamId,
          confirm: true,
          mode: strategyMode,
          projection_source: projectionSource,
          custom_starter_ids:
            Object.keys(customSubstitutions).length > 0 && lineup
              ? lineup.starters.map((slot: SlotAssignment, idx: number) =>
                  customSubstitutions[idx]
                    ? customSubstitutions[idx].player_id
                    : slot.recommended_player.player_id
                )
              : undefined,
          selected_moves: movesToPush,
        }),
      })

      const data: LineupPushResponse = await res.json()
      setPushResult(data)
      if (data.success) {
        await loadTeamLineup(selectedTeamId, strategyMode, projectionSource, true)
        await loadLeagueData()
      }
    } catch (err) {
      setPushResult({
        success: false,
        message: `Failed to push lineup: ${err}`,
        moves_executed: 0,
        team_id: selectedTeamId,
      })
    } finally {
      setIsPushing(false)
    }
  }

  const toggleMoveSelection = (playerId: number) => {
    setSelectedMoveIds((prev) =>
      prev.includes(playerId) ? prev.filter((id) => id !== playerId) : [...prev, playerId]
    )
  }

  return (
    <div className="app-container">
      {/* App Header */}
      <header className="app-header">
        <div className="brand-section">
          <div className="brand-icon">🏈</div>
          <div>
            <h1 className="brand-title">Apex Fantasy Analytics</h1>
            <div className="brand-subtitle" style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              <span>{league ? `${league.name} • Season ${league.season} (Week ${league.current_week})` : '2026 Season'}</span>
              <span className="pill cyan" style={{ fontSize: '11px', padding: '2px 8px' }}>
                ⚡ 8-Team PPR Calibrated
              </span>
              <span className="pill gold" style={{ fontSize: '11px', padding: '2px 8px', fontWeight: 800, background: 'rgba(234, 179, 8, 0.15)', color: '#facc15', border: '1px solid rgba(234, 179, 8, 0.3)' }}>
                🏈 Kickoff Tomorrow: NE @ SEA (Wed, Sep 9 • 8:20 PM ET)
              </span>
              {inactivesAlerts.length > 0 && (
                <span className="pill rose" style={{ fontSize: '11px', padding: '2px 8px', fontWeight: 800 }}>
                  🚨 {inactivesAlerts.length} Starter Inactive Alert{inactivesAlerts.length > 1 ? 's' : ''}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="header-status">
          {/* Team Switcher */}
          {league && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Focus Team:</span>
              <select
                className="select-dropdown"
                value={selectedTeamId}
                onChange={(e) => {
                  const newId = Number(e.target.value)
                  setIsExplicitCompare(false)
                  setSelectedTeamId(newId)
                  // Intentionally do NOT overwrite selectedRosterTeamId so user can browse any roster on League tab independently
                }}
              >
                {league.teams.map((t: TeamSummary) => (
                  <option key={t.id} value={t.id}>
                    {t.name}{t.primary_owner ? ` (${t.primary_owner})` : ''} • {t.record} {t.is_user_team ? '★ (My Team)' : ''}
                  </option>
                ))}
              </select>
            </div>
          )}

          <button
            className="btn btn-primary btn-sm"
            onClick={() => handleSync(true)}
            disabled={isSyncing}
          >
            {isSyncing ? '⏳ Syncing...' : '🔄 Sync ESPN Now'}
          </button>
        </div>
      </header>

      {syncMessage && (
        <div className="diag-box info" style={{ marginBottom: '20px' }}>
          {syncMessage}
        </div>
      )}

      {/* Main Tab Navigation */}
      <nav className="tab-nav">
        <button
          className={`tab-btn ${activeTab === 'lineup' ? 'active' : ''}`}
          onClick={() => setActiveTab('lineup')}
        >
          🏈 Optimal Lineup
          {lineup && lineup.differences_count > 0 && (
            <span className="badge-count">{lineup.differences_count} Diffs</span>
          )}
        </button>

        <button
          className={`tab-btn ${activeTab === 'compare' ? 'active' : ''}`}
          onClick={() => setActiveTab('compare')}
        >
          ⚖️ Start/Sit Comparator
        </button>

        <button
          className={`tab-btn ${activeTab === 'waivers' ? 'active' : ''}`}
          onClick={() => setActiveTab('waivers')}
        >
          🔄 Waiver Upgrades
        </button>

        <button
          className={`tab-btn ${activeTab === 'trades' ? 'active' : ''}`}
          onClick={() => setActiveTab('trades')}
        >
          🤝 2-for-1 Trades
        </button>

        <button
          className={`tab-btn ${activeTab === 'league' ? 'active' : ''}`}
          onClick={() => setActiveTab('league')}
        >
          👥 League Rosters
        </button>

        <button
          className={`tab-btn ${activeTab === 'injuries' ? 'active' : ''}`}
          onClick={() => setActiveTab('injuries')}
        >
          🩺 Injury Wire
        </button>

        <button
          className={`tab-btn ${activeTab === 'fantasypros' ? 'active' : ''}`}
          onClick={() => setActiveTab('fantasypros')}
        >
          ⭐ FantasyPros ECR
        </button>

        <button
          className={`tab-btn ${activeTab === 'intel' ? 'active' : ''}`}
          onClick={() => setActiveTab('intel')}
        >
          🧠 Matchup Intel
        </button>

        <button
          className={`tab-btn ${activeTab === 'dfs' ? 'active' : ''}`}
          onClick={() => setActiveTab('dfs')}
        >
          ⚡ DFS Optimizer
        </button>

        <button
          className={`tab-btn ${activeTab === 'vegas' ? 'active' : ''}`}
          onClick={() => setActiveTab('vegas')}
        >
          🎲 Vegas Odds
        </button>

        <button
          className={`tab-btn ${activeTab === 'settings' ? 'active' : ''}`}
          onClick={() => setActiveTab('settings')}
        >
          ⚙️ Settings & Weights
        </button>
      </nav>

      {/* TAB VIEWS */}
      {activeTab === 'lineup' && (
        <LineupTab
          projectionSource={projectionSource}
          onProjectionSourceChange={handleProjectionSourceChange}
          strategyMode={strategyMode}
          onStrategyChange={handleStrategyChange}
          lineup={lineup}
          league={league}
          lineupViewMode={lineupViewMode}
          setLineupViewMode={setLineupViewMode}
          showMatchupKey={showMatchupKey}
          setShowMatchupKey={setShowMatchupKey}
          expandedWhy={expandedWhy}
          setExpandedWhy={setExpandedWhy}
          expandedStatsPlayerId={expandedStatsPlayerId}
          setExpandedStatsPlayerId={setExpandedStatsPlayerId}
          customSubstitutions={customSubstitutions}
          setCustomSubstitutions={setCustomSubstitutions}
          activeSwapSlotIndex={activeSwapSlotIndex}
          setActiveSwapSlotIndex={setActiveSwapSlotIndex}
          onOpenPushModal={handleOpenPushModal}
          isPushing={isPushing}
          onCompareStarterWithBench={handleCompareStarterWithBench}
          onCompareBenchWithStarter={handleCompareBenchWithStarter}
          onReviewCloseCall={(starterId, benchId) => {
            const ids = [starterId, benchId]
            setIsExplicitCompare(true)
            setCompareIds(ids)
            runComparison(ids, strategyMode, projectionSource)
            setActiveTab('compare')
          }}
          inactivesAlerts={inactivesAlerts}
        />
      )}

      {activeTab === 'compare' && (
        <CompareTab
          strategyMode={strategyMode}
          onStrategyChange={handleStrategyChange}
          projectionSource={projectionSource}
          selectedTeamId={selectedTeamId}
          league={league}
          allPlayers={allPlayers}
          lineup={lineup}
          compareIds={compareIds}
          setCompareIds={setCompareIds}
          comparisonResult={comparisonResult}
          runComparison={runComparison}
          onClearComparison={handleClearComparison}
          onAutoLoadDilemma={handleAutoLoadRosterDilemma}
        />
      )}

      {activeTab === 'waivers' && (
        <WaiversTab
          waivers={waivers}
        />
      )}

      {activeTab === 'trades' && (
        <TradesTab
          consolidationTrades={consolidationTrades}
          isLoadingTrades={isLoadingTrades}
          selectedTeamId={selectedTeamId}
          onScanTrades={loadConsolidationTrades}
        />
      )}

      {activeTab === 'injuries' && (
        <InjuriesTab
          injuriesFeed={injuriesFeed}
          isLoadingInjuries={isLoadingInjuries}
          onRefreshInjuries={loadInjuries}
        />
      )}

      {activeTab === 'league' && (
        <LeagueTab
          league={league}
          matchups={matchups}
          matchupWeek={matchupWeek}
          setMatchupWeek={setMatchupWeek}
          selectedRosterTeamId={selectedRosterTeamId}
          setSelectedRosterTeamId={handleSelectRosterTeam}
          teamRosterData={teamRosterData}
          isLoadingRoster={isLoadingRoster}
          onRefreshRoster={() => loadTeamRoster(selectedRosterTeamId, true)}
          lineup={lineup}
          onCompareFromRoster={handleCompareFromRoster}
        />
      )}

      {activeTab === 'settings' && (
        <SettingsTab
          league={league}
          leagueSizeSetting={leagueSizeSetting}
          setLeagueSizeSetting={setLeagueSizeSetting}
          weights={weights}
          onWeightChange={handleWeightChange}
          onSaveWeights={handleSaveWeights}
          onRunBacktesting={handleRunBacktesting}
          tuningMessage={tuningMessage}
          backtest={backtest}
        />
      )}

      {activeTab === 'fantasypros' && (
        <FantasyProsTab
          currentWeek={league?.current_week || 1}
          onSyncSuccess={() => {
            loadLeagueData()
            loadTeamLineup(selectedTeamId, strategyMode, projectionSource, true)
          }}
        />
      )}

      {activeTab === 'intel' && (
        <IntelTab
          lineup={lineup}
          league={league}
          matchups={matchups}
          wrcbData={wrcbData}
          vegasData={vegasData}
          isLoadingWrcb={isLoadingIntel}
          isLoadingVegas={isLoadingIntel}
          onRefresh={() => {
            loadIntelData(selectedTeamId, true)
            loadTeamLineup(selectedTeamId, strategyMode, projectionSource, true)
            if (league?.current_week) {
              loadMatchups(league.current_week)
            }
          }}
          onCompareStarterWithBench={handleCompareStarterWithBench}
          onCompareBenchWithStarter={handleCompareBenchWithStarter}
          onSelectTab={(tab) => setActiveTab(tab as any)}
          selectedTeamId={selectedTeamId}
        />
      )}

      {activeTab === 'dfs' && (
        <DfsTab
          projectionSource={projectionSource}
          onProjectionSourceChange={(source) => {
            setProjectionSource(source)
            try {
              localStorage.setItem('agy_projection_source', source)
            } catch {}
          }}
        />
      )}

      {activeTab === 'vegas' && (
        <VegasTab
          league={league}
          selectedTeamId={selectedTeamId}
          lineup={lineup}
          onSelectTab={(tab) => setActiveTab(tab as any)}
          onCompareStarterWithBench={handleCompareStarterWithBench}
        />
      )}

      {/* MODALS */}
      {showPushModal && pushPreview && (
        <PreFlightPushModal
          isOpen={showPushModal}
          onClose={() => setShowPushModal(false)}
          pushPreview={pushPreview}
          pushResult={pushResult}
          selectedMoveIds={selectedMoveIds}
          toggleMoveSelection={toggleMoveSelection}
          onExecutePush={handleExecutePush}
          isPushing={isPushing}
          currentWeek={league?.current_week || 1}
        />
      )}
    </div>
  )
}

export default App
