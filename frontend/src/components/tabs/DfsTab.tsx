import { useState, useEffect, useMemo, useRef } from 'react'
import type {
  DFSSlateInfo,
  DFSLineupResponse,
  DFSSlateDataResponse,
  DFSUploadResponse,
} from '../../types'
import { DfsRosterBoard } from './DfsRosterBoard'
import { NFLTeamLogo } from '../shared/NFLTeamLogo'
import './DfsTab.css'

export type ProjectionSourceType = 'MODEL' | 'CONSENSUS' | 'FANTASYPROS' | 'SLEEPER' | 'ESPN'

interface DfsTabProps {
  projectionSource?: ProjectionSourceType
  onProjectionSourceChange?: (source: ProjectionSourceType) => void
}

export function DfsTab({
  projectionSource: propSource,
  onProjectionSourceChange: propOnChange,
}: DfsTabProps = {}) {
  // Slate state
  const [slates, setSlates] = useState<DFSSlateInfo[]>([])
  const [selectedSlate, setSelectedSlate] = useState<string>('main')
  const [slateData, setSlateData] = useState<DFSSlateDataResponse | null>(null)
  const [uploadResult, setUploadResult] = useState<DFSUploadResponse | null>(null)
  const [isUploading, setIsUploading] = useState<boolean>(false)
  const [isDragging, setIsDragging] = useState<boolean>(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Projection source state (synced with parent prop or localStorage fallback)
  const [internalSource, setInternalSource] = useState<ProjectionSourceType>(() => {
    const saved = localStorage.getItem('agy_projection_source')
    if (saved === 'MODEL' || saved === 'CONSENSUS' || saved === 'FANTASYPROS' || saved === 'SLEEPER' || saved === 'ESPN') {
      return saved as ProjectionSourceType
    }
    return 'MODEL'
  })

  const currentSource = propSource || internalSource

  const handleSourceChange = (src: ProjectionSourceType) => {
    if (propOnChange) {
      propOnChange(src)
    } else {
      setInternalSource(src)
    }
    try {
      localStorage.setItem('agy_projection_source', src)
    } catch {}
  }

  // Optimizer configuration
  const [strategyMode, setStrategyMode] = useState<'SINGLE_ENTRY_GPP' | 'CASH'>('SINGLE_ENTRY_GPP')
  const [numLineups, setNumLineups] = useState<number>(1)
  const [randomness, setRandomness] = useState<number>(0.0)
  const [minSalary, setMinSalary] = useState<number>(58000)
  const [maxSalary] = useState<number>(60000)
  const [stackQb, setStackQb] = useState<string>('')

  // Interactive constraints
  const [lockPlayers, setLockPlayers] = useState<string[]>([])
  const [excludePlayers, setExcludePlayers] = useState<string[]>([])
  const [customProjections, setCustomProjections] = useState<Record<string, number>>({})

  // Lineup generation state
  const [lineup, setLineup] = useState<DFSLineupResponse | null>(null)
  const [activeLineupIndex, setActiveLineupIndex] = useState<number>(0)
  const [isLoadingLineup, setIsLoadingLineup] = useState<boolean>(false)
  const [isLoadingSlate, setIsLoadingSlate] = useState<boolean>(false)
  const [isExporting, setIsExporting] = useState<boolean>(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  // Sub-views & Filters (defaults to 'pool' - Player Pool & Projections)
  const [activeSubView, setActiveSubView] = useState<'lineup' | 'stacks' | 'leverage' | 'pool' | 'exposure'>('pool')
  const [positionFilter, setPositionFilter] = useState<string>('ALL')
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [sortColumn, setSortColumn] = useState<string>('salary')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc')
  const [exposurePosFilter, setExposurePosFilter] = useState<string>('ALL')
  const [lineupViewMode, setLineupViewMode] = useState<'card' | 'table'>('card')

  // Selected player for DvP detail tooltip modal
  const [selectedDvpPlayer, setSelectedDvpPlayer] = useState<{
    name: string
    position: string
    team: string
    opponent: string
    opp_soft_rank: number
    opp_tier?: string
    opp_tier_label?: string
    opp_fd_fpa?: number
  } | null>(null)

  // Overall DvP explainer modal
  const [showDvpLegendModal, setShowDvpLegendModal] = useState<boolean>(false)

  // Load available slates on mount
  useEffect(() => {
    loadSlates()
  }, [])

  // Load slate data when selected slate or projection source changes
  useEffect(() => {
    if (selectedSlate) {
      loadSlateData(selectedSlate, currentSource)
    }
  }, [selectedSlate, currentSource])

  const loadSlates = async () => {
    try {
      const res = await fetch('/api/dfs/slates')
      if (res.ok) {
        const data: DFSSlateInfo[] = await res.json()
        setSlates(data)
        if (data.length > 0 && !selectedSlate) {
          setSelectedSlate(data[0].id)
        }
      }
    } catch (err) {
      console.error('Failed to load slates:', err)
    }
  }

  const loadSlateData = async (slateId: string, source: ProjectionSourceType = currentSource) => {
    setIsLoadingSlate(true)
    setErrorMsg(null)
    try {
      const res = await fetch(`/api/dfs/slate-data?slate_id=${slateId}&projection_source=${source}`)
      if (res.ok) {
        const data: DFSSlateDataResponse = await res.json()
        setSlateData(data)
      } else {
        const err = await res.json()
        setErrorMsg(err.detail || 'Failed to load slate catalog.')
      }
    } catch (err: any) {
      setErrorMsg(err?.message || 'Network error fetching slate data.')
    } finally {
      setIsLoadingSlate(false)
    }
  }

  // Handle CSV file upload
  const handleFileUpload = async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.csv')) {
      setErrorMsg('Please upload a valid .csv file exported from FanDuel.')
      return
    }

    setIsUploading(true)
    setErrorMsg(null)
    setSuccessMsg(null)

    try {
      const text = await file.text()
      const res = await fetch('/api/dfs/upload-slate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename: file.name,
          csv_text: text,
        }),
      })

      if (res.ok) {
        const data: DFSUploadResponse = await res.json()
        setUploadResult(data)
        setSuccessMsg(`Successfully parsed ${data.total_players} players from ${file.name}!`)

        // Add to slates list if not already present
        const uploadedSlateObj: DFSSlateInfo = {
          id: 'uploaded',
          name: `Uploaded (${file.name})`,
          games_count: data.games_count,
          platform: 'FanDuel ($60k Cap)',
          is_available: true,
        }

        setSlates((prev) => {
          const filtered = prev.filter((s) => s.id !== 'uploaded')
          return [...filtered, uploadedSlateObj]
        })

        // Automatically select the uploaded slate and load its data
        setSelectedSlate('uploaded')
        await loadSlateData('uploaded')
      } else {
        const err = await res.json()
        setErrorMsg(err.detail || 'Failed to parse FanDuel CSV.')
      }
    } catch (err: any) {
      setErrorMsg(err?.message || 'Error reading CSV file.')
    } finally {
      setIsUploading(false)
    }
  }

  // One-click test with early-only sample CSV
  const handleLoadSampleEarlyCsv = async () => {
    setIsUploading(true)
    setErrorMsg(null)
    try {
      // Fetch the earlyonlysalariesandrosters.csv directly from server root or api
      const sampleRes = await fetch('/earlyonlysalariesandrosters.csv')
      let csvContent = ''
      if (sampleRes.ok) {
        csvContent = await sampleRes.text()
      }

      const res = await fetch('/api/dfs/upload-slate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename: 'earlyonlysalariesandrosters.csv',
          csv_text: csvContent || 'placeholder',
        }),
      })

      if (res.ok) {
        const data: DFSUploadResponse = await res.json()
        setUploadResult(data)
        setSuccessMsg(`Loaded sample FanDuel Early Slate (${data.total_players} players)!`)
        setSlates((prev) => {
          const filtered = prev.filter((s) => s.id !== 'uploaded')
          return [
            ...filtered,
            {
              id: 'uploaded',
              name: 'Uploaded: earlyonlysalariesandrosters.csv',
              games_count: data.games_count,
              platform: 'FanDuel ($60k Cap)',
              is_available: true,
            },
          ]
        })
        setSelectedSlate('uploaded')
        await loadSlateData('uploaded')
      } else {
        const err = await res.json()
        setErrorMsg(err.detail || 'Failed to load sample early CSV.')
      }
    } catch (err: any) {
      setErrorMsg('Could not load sample CSV: ' + err?.message)
    } finally {
      setIsUploading(false)
    }
  }

  // Solve Lineup(s)
  const solveLineup = async () => {
    setIsLoadingLineup(true)
    setErrorMsg(null)
    try {
      const payload = {
        slate_id: selectedSlate,
        mode: strategyMode,
        num_lineups: numLineups,
        randomness: randomness,
        projection_source: currentSource,
        stack_qb: stackQb || null,
        lock_players: lockPlayers,
        exclude_players: excludePlayers,
        custom_projections: customProjections,
        min_salary: minSalary,
        max_salary: maxSalary,
      }

      const res = await fetch('/api/dfs/optimize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (res.ok) {
        const data: DFSLineupResponse = await res.json()
        setLineup(data)
        setActiveLineupIndex(0)
        setActiveSubView('lineup')
      } else {
        const err = await res.json()
        setErrorMsg(err.detail || 'Optimization failed to find feasible lineup under current constraints.')
      }
    } catch (err: any) {
      setErrorMsg(err?.message || 'Optimization request failed.')
    } finally {
      setIsLoadingLineup(false)
    }
  }

  // Export solved lineups to FanDuel CSV
  const exportLineupsToFanDuel = async () => {
    const lineupsToExport = lineup?.lineups && lineup.lineups.length > 0 ? lineup.lineups : lineup ? [lineup] : []
    if (lineupsToExport.length === 0) {
      setErrorMsg('No lineups available to export. Run optimizer first!')
      return
    }

    setIsExporting(true)
    try {
      const res = await fetch('/api/dfs/export-lineups', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lineups: lineupsToExport }),
      })

      if (res.ok) {
        const data = await res.json()
        const blob = new Blob([data.csv_content], { type: 'text/csv;charset=utf-8;' })
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.setAttribute('download', data.filename || 'fanduel_lineup_import.csv')
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        URL.revokeObjectURL(url)
      } else {
        const err = await res.json()
        setErrorMsg(err.detail || 'Failed to export FanDuel CSV.')
      }
    } catch (err: any) {
      setErrorMsg(err?.message || 'Export error.')
    } finally {
      setIsExporting(false)
    }
  }

  // Player Lock / Exclude Handlers
  const toggleLock = (playerName: string) => {
    if (lockPlayers.includes(playerName)) {
      setLockPlayers(lockPlayers.filter((p) => p !== playerName))
    } else {
      if (lockPlayers.length >= 9) {
        setErrorMsg('Maximum of 9 players can be locked.')
        return
      }
      setLockPlayers([...lockPlayers, playerName])
      setExcludePlayers(excludePlayers.filter((p) => p !== playerName))
    }
  }

  const toggleExclude = (playerName: string) => {
    if (excludePlayers.includes(playerName)) {
      setExcludePlayers(excludePlayers.filter((p) => p !== playerName))
    } else {
      setExcludePlayers([...excludePlayers, playerName])
      setLockPlayers(lockPlayers.filter((p) => p !== playerName))
    }
  }

  const updateCustomProjection = (playerName: string, val: number) => {
    setCustomProjections((prev) => ({
      ...prev,
      [playerName]: val,
    }))
  }

  const clearAllLocks = () => setLockPlayers([])
  const clearAllExcludes = () => setExcludePlayers([])
  const resetCustomProjections = () => setCustomProjections({})

  // Current lineup being displayed
  const currentDisplayedLineup = useMemo(() => {
    if (!lineup) return null
    if (lineup.lineups && lineup.lineups.length > activeLineupIndex) {
      return lineup.lineups[activeLineupIndex]
    }
    return lineup
  }, [lineup, activeLineupIndex])

  // Available QBs for stacking selector
  const availableQBs = useMemo(() => {
    if (!slateData?.players) return []
    return slateData.players
      .filter((p) => p.position === 'QB')
      .sort((a, b) => b.proj - a.proj)
  }, [slateData])

  // Sorted and filtered player pool
  const filteredAndSortedPlayers = useMemo(() => {
    if (!slateData?.players) return []
    let list = slateData.players.filter((p) => {
      if (positionFilter === 'LOCKED') return lockPlayers.includes(p.name)
      if (positionFilter === 'EXCLUDED') return excludePlayers.includes(p.name)
      if (positionFilter === 'CUSTOM') return customProjections[p.name] !== undefined
      if (positionFilter === 'VALUE') return p.value_ratio >= 2.5
      if (positionFilter !== 'ALL' && p.position !== positionFilter) return false

      if (searchQuery) {
        const query = searchQuery.toLowerCase()
        const matchesName = p.name.toLowerCase().includes(query)
        const matchesTeam = p.team.toLowerCase().includes(query)
        const matchesOpp = p.opponent.toLowerCase().includes(query)
        return matchesName || matchesTeam || matchesOpp
      }
      return true
    })

    list.sort((a, b) => {
      let aVal = (a as any)[sortColumn] ?? 0
      let bVal = (b as any)[sortColumn] ?? 0

      // Use custom projection if present
      if (sortColumn === 'proj') {
        aVal = customProjections[a.name] ?? a.proj
        bVal = customProjections[b.name] ?? b.proj
      }

      if (aVal < bVal) return sortDirection === 'asc' ? -1 : 1
      if (aVal > bVal) return sortDirection === 'asc' ? 1 : -1
      return 0
    })

    return list
  }, [slateData, positionFilter, searchQuery, sortColumn, sortDirection, lockPlayers, excludePlayers, customProjections])

  const handleSort = (col: string) => {
    if (sortColumn === col) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      setSortColumn(col)
      setSortDirection('desc')
    }
  }

  // Exposure items grouped/filtered
  const exposureList = useMemo(() => {
    if (!lineup?.exposure) return []
    const list = Object.values(lineup.exposure)
    if (exposurePosFilter === 'ALL') return list
    return list.filter((item) => item.position === exposurePosFilter)
  }, [lineup, exposurePosFilter])

  return (
    <div className="dfs-container">
      {/* 1. Header Banner & Slate Selector */}
      <div className="dfs-header-card">
        <div className="dfs-title-area">
          <div className="dfs-title-row">
            <span style={{ fontSize: '26px' }}>⚡</span>
            <h2 className="dfs-title">FanDuel DFS Institutional Quant Engine</h2>
            <span className="dfs-badge dfs-badge-emerald">FanDuel $60,000 Cap</span>
            <span className="dfs-badge dfs-badge-cyan">0.5 PPR Scoring</span>
          </div>
          <p className="dfs-subtitle">
            Mixed-Integer Linear Programming (MILP) with correlation firewalls, 90th% ceiling tournament optimization, and portfolio exposure management.
          </p>
        </div>

        {/* Slate Switcher Pills */}
        <div className="dfs-slate-selector">
          {slates.map((s) => (
            <button
              key={s.id}
              onClick={() => setSelectedSlate(s.id)}
              className={`dfs-slate-btn ${selectedSlate === s.id ? 'active' : ''}`}
            >
              <span>{s.id === 'main' ? '🏈' : s.id === 'early' ? '🌅' : '📂'}</span>
              <span>{s.name}</span>
            </button>
          ))}
          {isLoadingSlate && (
            <span className="dfs-badge dfs-badge-cyan" style={{ fontSize: '10px' }}>
              <span className="status-dot"></span> Loading...
            </span>
          )}
        </div>
      </div>

      {/* 2. Drag-and-Drop FanDuel CSV Upload Section */}
      <div
        className={`dfs-upload-section ${isDragging ? 'dragover' : ''}`}
        onDragOver={(e) => {
          e.preventDefault()
          setIsDragging(true)
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setIsDragging(false)
          if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            handleFileUpload(e.dataTransfer.files[0])
          }
        }}
      >
        <input
          type="file"
          ref={fileInputRef}
          accept=".csv"
          style={{ display: 'none' }}
          onChange={(e) => {
            if (e.target.files && e.target.files.length > 0) {
              handleFileUpload(e.target.files[0])
            }
          }}
        />

        <div className="dfs-upload-content">
          <div className="dfs-upload-icon-circle">
            <span>📁</span>
          </div>
          <div>
            <div className="dfs-upload-title">Upload Official FanDuel Salaries CSV</div>
            <div className="dfs-upload-desc">
              Ensure all player salaries, game slates, and rosters are 100% up to date. Drag & drop your FanDuel CSV export (e.g. <code>earlyonlysalariesandrosters.csv</code>) or select a file to ingest.
            </div>
          </div>

          <div className="dfs-upload-actions">
            <button
              className="dfs-upload-btn"
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
            >
              {isUploading ? (
                <>
                  <span className="status-dot"></span>
                  <span>Ingesting & Enriching Slate...</span>
                </>
              ) : (
                <>
                  <span>⬆️</span>
                  <span>Browse & Upload FanDuel CSV</span>
                </>
              )}
            </button>

            <button
              className="dfs-sample-btn"
              onClick={handleLoadSampleEarlyCsv}
              disabled={isUploading}
            >
              <span>⚡ Load Early-Only Sample CSV</span>
            </button>
          </div>
        </div>
      </div>

      {/* Upload Success Card Banner */}
      {uploadResult && (
        <div className="dfs-upload-success-card">
          <div className="dfs-upload-success-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '18px' }}>✅</span>
              <div>
                <strong style={{ color: '#ffffff', fontSize: '14px' }}>
                  {uploadResult.filename} Ingested Successfully
                </strong>
                <span className="dfs-badge dfs-badge-emerald" style={{ marginLeft: '10px' }}>
                  Active Slate
                </span>
              </div>
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
              {uploadResult.games_count} Games Detected
            </div>
          </div>

          <div className="dfs-upload-meta-grid">
            <div className="dfs-upload-meta-item">
              <div className="dfs-upload-meta-label">Total Players</div>
              <div className="dfs-upload-meta-val">{uploadResult.total_players}</div>
            </div>
            <div className="dfs-upload-meta-item">
              <div className="dfs-upload-meta-label">Teams Active</div>
              <div className="dfs-upload-meta-val">{uploadResult.teams.length}</div>
            </div>
            <div className="dfs-upload-meta-item">
              <div className="dfs-upload-meta-label">Salary Range</div>
              <div className="dfs-upload-meta-val">
                ${uploadResult.salary_min.toLocaleString()} - ${uploadResult.salary_max.toLocaleString()}
              </div>
            </div>
            <div className="dfs-upload-meta-item">
              <div className="dfs-upload-meta-label">Cap System</div>
              <div className="dfs-upload-meta-val">$60,000</div>
            </div>
          </div>

          {/* Top Stars Ingested */}
          {uploadResult.top_stars && uploadResult.top_stars.length > 0 && (
            <div>
              <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '6px' }}>
                ⭐ TOP SALARY STARS DETECTED:
              </div>
              <div className="dfs-stars-preview">
                {uploadResult.top_stars.map((star, idx) => (
                  <div key={idx} className="dfs-star-pill">
                    <span style={{ color: '#ffffff', fontWeight: 700 }}>{star.name}</span>
                    <span style={{ color: 'var(--text-muted)' }}>({star.position})</span>
                    <span style={{ color: 'var(--accent-emerald)', fontWeight: 800 }}>${star.salary.toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Messages */}
      {errorMsg && (
        <div style={{ padding: '12px 16px', background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: 'var(--radius-md)', color: '#fca5a5', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span>⚠️</span>
          <span>{errorMsg}</span>
        </div>
      )}
      {successMsg && !uploadResult && (
        <div style={{ padding: '12px 16px', background: 'rgba(16, 185, 129, 0.15)', border: '1px solid rgba(16, 185, 129, 0.3)', borderRadius: 'var(--radius-md)', color: '#6ee7b7', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span>✓</span>
          <span>{successMsg}</span>
        </div>
      )}

      {/* Projection Source Engine Selector */}
      <div className="dfs-source-selector-bar">
        <div className="dfs-source-meta">
          <span style={{ fontSize: '22px' }}>📊</span>
          <div>
            <div className="dfs-source-title">
              Projection Source Engine:
              <span style={{ color: 'var(--accent-cyan)', marginLeft: '8px' }}>
                {currentSource === 'MODEL'
                  ? '⚡ Quant Model (Vegas Script + DvP Calibrated)'
                  : currentSource === 'CONSENSUS'
                  ? '⭐ Multi-Source Consensus (Bayesian Ensemble)'
                  : currentSource === 'FANTASYPROS'
                  ? '🌐 FantasyPros (PPR / ECR)'
                  : currentSource === 'SLEEPER'
                  ? '📱 Sleeper / RotoWire'
                  : '🏈 ESPN Official'}
              </span>
            </div>
            <div className="dfs-source-desc">
              Selects player projection baseline for all slate athletes, value ratios, ceiling equity, and optimal lineups.
            </div>
          </div>
        </div>

        <div className="dfs-source-pills">
          <button
            className={`dfs-source-btn ${currentSource === 'MODEL' ? 'active' : ''}`}
            onClick={() => handleSourceChange('MODEL')}
            title="Our quantitative Vegas micro-volume script projection engine"
          >
            <span>⚡ Quant Model</span>
          </button>
          <button
            className={`dfs-source-btn ${currentSource === 'CONSENSUS' ? 'active' : ''}`}
            onClick={() => handleSourceChange('CONSENSUS')}
            title="Outlier-Protected Bayesian Consensus (Model + FP + Sleeper + ESPN)"
          >
            <span>⭐ Consensus</span>
          </button>
          <button
            className={`dfs-source-btn ${currentSource === 'FANTASYPROS' ? 'active' : ''}`}
            onClick={() => handleSourceChange('FANTASYPROS')}
            title="FantasyPros Multi-Expert ECR Consensus Projections"
          >
            <span>🌐 FantasyPros</span>
          </button>
          <button
            className={`dfs-source-btn ${currentSource === 'SLEEPER' ? 'active' : ''}`}
            onClick={() => handleSourceChange('SLEEPER')}
            title="Sleeper / RotoWire Official Weekly Projections"
          >
            <span>📱 Sleeper</span>
          </button>
          <button
            className={`dfs-source-btn ${currentSource === 'ESPN' ? 'active' : ''}`}
            onClick={() => handleSourceChange('ESPN')}
            title="ESPN Official NFL Projections"
          >
            <span>🏈 ESPN</span>
          </button>
        </div>
      </div>

      {/* 3. Optimization Control Center */}
      <div className="dfs-controls-card">
        <div className="dfs-controls-top-row">
          {/* Strategy Mode Switcher */}
          <div className="dfs-mode-group">
            <button
              onClick={() => setStrategyMode('SINGLE_ENTRY_GPP')}
              className={`dfs-mode-btn gpp ${strategyMode === 'SINGLE_ENTRY_GPP' ? 'active' : ''}`}
            >
              <div className="dfs-mode-title">
                <span>🏆 Tournament (Single-Entry GPP)</span>
                {strategyMode === 'SINGLE_ENTRY_GPP' && <span style={{ color: 'var(--accent-amber)' }}>●</span>}
              </div>
              <div className="dfs-mode-desc">
                75% 90th% ceiling objective + mandatory QB-WR stack & bring-back. Solves for maximum tournament win equity.
              </div>
            </button>

            <button
              onClick={() => setStrategyMode('CASH')}
              className={`dfs-mode-btn cash ${strategyMode === 'CASH' ? 'active' : ''}`}
            >
              <div className="dfs-mode-title">
                <span>🛡️ Cash Game (50-50 / Double-Up)</span>
                {strategyMode === 'CASH' && <span style={{ color: 'var(--accent-emerald)' }}>●</span>}
              </div>
              <div className="dfs-mode-desc">
                70% safety floor + high-touch bellcow RBs. Solves for median baseline reliability and low variance.
              </div>
            </button>
          </div>

          {/* Action CTAs */}
          <div className="dfs-cta-area">
            <button
              className="dfs-optimize-btn"
              onClick={solveLineup}
              disabled={isLoadingLineup}
            >
              {isLoadingLineup ? (
                <>
                  <span className="status-dot"></span>
                  <span>Solving Globally Optimal MILP...</span>
                </>
              ) : (
                <>
                  <span>⚡</span>
                  <span>Optimize {numLineups > 1 ? `${numLineups} Lineups` : 'Optimal Lineup'}</span>
                </>
              )}
            </button>

            {lineup && (
              <button
                className="dfs-export-btn"
                onClick={exportLineupsToFanDuel}
                disabled={isExporting}
              >
                <span>📥</span>
                <span>{isExporting ? 'Generating CSV...' : 'Export to FanDuel CSV'}</span>
              </button>
            )}
          </div>
        </div>

        {/* Advanced Portfolio Parameters Grid */}
        <div className="dfs-params-grid">
          {/* Number of Lineups */}
          <div className="dfs-param-box">
            <div className="dfs-param-label">
              <span>Portfolio Size</span>
              <span style={{ color: 'var(--accent-cyan)' }}>{numLineups} Lineup{numLineups > 1 ? 's' : ''}</span>
            </div>
            <div className="dfs-lineup-pill-group">
              {[1, 3, 5, 10, 20].map((n) => (
                <button
                  key={n}
                  onClick={() => setNumLineups(n)}
                  className={`dfs-lineup-pill ${numLineups === n ? 'active' : ''}`}
                >
                  {n}
                </button>
              ))}
            </div>
          </div>

          {/* Randomness / Variance */}
          <div className="dfs-param-box">
            <div className="dfs-param-label">
              <span>Projection Variance</span>
              <span style={{ color: 'var(--accent-cyan)' }}>{Math.round(randomness * 100)}%</span>
            </div>
            <div className="dfs-range-row">
              <input
                type="range"
                min="0"
                max="0.25"
                step="0.05"
                value={randomness}
                onChange={(e) => setRandomness(parseFloat(e.target.value))}
                className="dfs-range-input"
              />
            </div>
          </div>

          {/* QB Stacking */}
          <div className="dfs-param-box">
            <div className="dfs-param-label">
              <span>Primary QB Stack</span>
              <span style={{ color: 'var(--text-muted)' }}>{stackQb || 'Auto Game Stack'}</span>
            </div>
            <select
              value={stackQb}
              onChange={(e) => setStackQb(e.target.value)}
              className="dfs-select-input"
            >
              <option value="">🤖 Auto-Detect Optimal Game Stack</option>
              {availableQBs.map((qb) => (
                <option key={qb.player_id} value={qb.name}>
                  {qb.name} ({qb.team} vs {qb.opponent}) - ${qb.salary.toLocaleString()}
                </option>
              ))}
            </select>
          </div>

          {/* Minimum Salary Bounds */}
          <div className="dfs-param-box">
            <div className="dfs-param-label">
              <span>Min Salary Cap Usage</span>
              <span style={{ color: 'var(--accent-emerald)' }}>${minSalary.toLocaleString()}</span>
            </div>
            <div className="dfs-range-row">
              <input
                type="range"
                min="55000"
                max="60000"
                step="500"
                value={minSalary}
                onChange={(e) => setMinSalary(parseInt(e.target.value))}
                className="dfs-range-input"
              />
            </div>
          </div>
        </div>

        {/* Active Constraints Summary Bar */}
        {(lockPlayers.length > 0 || excludePlayers.length > 0 || Object.keys(customProjections).length > 0) && (
          <div className="dfs-action-tags-bar">
            <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)' }}>Active Rules:</span>

            {lockPlayers.length > 0 && (
              <button onClick={clearAllLocks} className="dfs-tag-btn dfs-badge-emerald" title="Click to clear locks">
                <span>🔒 {lockPlayers.length} Locked</span>
                <span>✕</span>
              </button>
            )}

            {excludePlayers.length > 0 && (
              <button onClick={clearAllExcludes} className="dfs-tag-btn dfs-badge-rose" title="Click to clear excludes">
                <span>🚫 {excludePlayers.length} Excluded</span>
                <span>✕</span>
              </button>
            )}

            {Object.keys(customProjections).length > 0 && (
              <button onClick={resetCustomProjections} className="dfs-tag-btn dfs-badge-cyan" title="Click to reset custom projections">
                <span>✏️ {Object.keys(customProjections).length} Custom Proj</span>
                <span>✕</span>
              </button>
            )}
          </div>
        )}
      </div>

      {/* 4. Sub-View Navigation Tabs */}
      <div className="dfs-subtabs-bar">
        <button
          onClick={() => setActiveSubView('pool')}
          className={`dfs-subtab-btn ${activeSubView === 'pool' ? 'active' : ''}`}
        >
          <span>📊</span>
          <span>Player Pool & Projections ({slateData?.total_players || 0})</span>
        </button>

        <button
          onClick={() => setActiveSubView('lineup')}
          className={`dfs-subtab-btn ${activeSubView === 'lineup' ? 'active' : ''}`}
        >
          <span>📋</span>
          <span>
            {lineup?.lineups && lineup.lineups.length > 1
              ? `Portfolio Lineups (${lineup.lineups.length})`
              : 'Optimal Lineup'}
          </span>
        </button>

        {lineup?.exposure && Object.keys(lineup.exposure).length > 0 && (
          <button
            onClick={() => setActiveSubView('exposure')}
            className={`dfs-subtab-btn ${activeSubView === 'exposure' ? 'active' : ''}`}
          >
            <span>📈</span>
            <span>Portfolio Exposure ({Object.keys(lineup.exposure).length})</span>
          </button>
        )}

        <button
          onClick={() => setActiveSubView('stacks')}
          className={`dfs-subtab-btn ${activeSubView === 'stacks' ? 'active' : ''}`}
        >
          <span>🔥</span>
          <span>Top Game Stacks ({slateData?.top_stacks?.length || 0})</span>
        </button>

        <button
          onClick={() => setActiveSubView('leverage')}
          className={`dfs-subtab-btn ${activeSubView === 'leverage' ? 'active' : ''}`}
        >
          <span>🎯</span>
          <span>Leverage & Chalk Radar</span>
        </button>
      </div>

      {/* 5. SUB-VIEW: SOLVED LINEUP SHOWCASE / DRAFT BOARD */}
      {activeSubView === 'lineup' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Visual Interactive Draft Board & Roster Card */}
          <DfsRosterBoard
            currentDisplayedLineup={currentDisplayedLineup}
            lineup={lineup}
            activeLineupIndex={activeLineupIndex}
            setActiveLineupIndex={setActiveLineupIndex}
            slateData={slateData}
            lockPlayers={lockPlayers}
            toggleLock={toggleLock}
            clearAllLocks={clearAllLocks}
            customProjections={customProjections}
            solveLineup={solveLineup}
            isLoadingLineup={isLoadingLineup}
            exportLineupsToFanDuel={exportLineupsToFanDuel}
            isExporting={isExporting}
            onSelectPoolPosition={(pos) => {
              setPositionFilter(pos)
              setActiveSubView('pool')
            }}
            onResetLineup={() => {
              setLineup(null)
              setActiveLineupIndex(0)
            }}
            viewMode={lineupViewMode}
            setViewMode={setLineupViewMode}
            setSelectedDvpPlayer={setSelectedDvpPlayer}
            stackQb={stackQb}
            setStackQb={setStackQb}
          />

          {/* If Solved & User Toggles to Forensic Table View */}
          {currentDisplayedLineup && lineupViewMode === 'table' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {/* Active Stacking Summary */}
              {currentDisplayedLineup.active_stack && (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 16px', background: 'rgba(6, 182, 212, 0.08)', border: '1px solid rgba(6, 182, 212, 0.25)', borderRadius: 'var(--radius-md)', fontSize: '12px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ color: 'var(--accent-cyan)', fontWeight: 800 }}>🎯 Primary Correlation Stack:</span>
                    <span style={{ color: '#ffffff', fontWeight: 700 }}>{currentDisplayedLineup.active_stack.qb}</span>
                    <span style={{ color: 'var(--text-muted)', display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
                      (<NFLTeamLogo team={currentDisplayedLineup.active_stack.team} size={16} />
                      <span>{currentDisplayedLineup.active_stack.team} vs</span>
                      <NFLTeamLogo team={currentDisplayedLineup.active_stack.opponent} size={16} />
                      <span>{currentDisplayedLineup.active_stack.opponent}</span>)
                    </span>
                  </div>
                  <span className="dfs-badge dfs-badge-cyan">Opposing Bring-Back Enforced</span>
                </div>
              )}

              {/* Roster Table */}
              <div className="dfs-table-wrapper">
                <div className="dfs-table-scroll">
                  <table className="dfs-table">
                    <thead>
                      <tr>
                        <th>Slot</th>
                        <th>Player</th>
                        <th>Team</th>
                        <th>Opp</th>
                        <th style={{ textAlign: 'right' }}>Salary</th>
                        <th style={{ textAlign: 'right' }}>Proj Pts</th>
                        <th style={{ textAlign: 'right' }}>90th% Ceiling</th>
                        <th style={{ textAlign: 'right' }}>Implied</th>
                        <th style={{ textAlign: 'right' }}>
                          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', justifyContent: 'flex-end' }}>
                            <span>DvP Rank</span>
                            <button
                              type="button"
                              className="dfs-dvp-help-icon"
                              onClick={(e) => {
                                e.stopPropagation()
                                setShowDvpLegendModal(true)
                              }}
                              title="What is DvP Rank? Click to see explanation."
                            >
                              ?
                            </button>
                          </div>
                        </th>
                        <th style={{ textAlign: 'center' }}>Ownership</th>
                        <th style={{ textAlign: 'right' }}>Leverage</th>
                        <th style={{ textAlign: 'center' }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {currentDisplayedLineup.roster.map((item, idx) => {
                        const isLocked = lockPlayers.includes(item.name)
                        const isExcluded = excludePlayers.includes(item.name)
                        return (
                          <tr key={idx} className={isLocked ? 'locked-row' : isExcluded ? 'excluded-row' : ''}>
                            <td style={{ fontWeight: 800, color: 'var(--accent-amber)' }}>{item.slot}</td>
                            <td>
                              <div className="dfs-player-cell">
                                <span className={`dfs-pos-pill ${item.position.toLowerCase()}`}>
                                  {item.position}
                                </span>
                                <div className="dfs-player-meta">
                                  <span className="dfs-player-name">{item.name}</span>
                                </div>
                              </div>
                            </td>
                            <td>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <NFLTeamLogo team={item.team} size={18} />
                                <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>{item.team}</span>
                              </div>
                            </td>
                            <td>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <NFLTeamLogo team={item.opponent} size={16} />
                                <span style={{ color: 'var(--text-muted)' }}>{item.opponent}</span>
                              </div>
                            </td>
                            <td style={{ textAlign: 'right', fontWeight: 800, color: '#ffffff' }}>
                              ${item.salary.toLocaleString()}
                            </td>
                            <td style={{ textAlign: 'right', fontWeight: 700, color: 'var(--accent-cyan)' }}>
                              {item.proj.toFixed(2)}
                            </td>
                            <td style={{ textAlign: 'right', fontWeight: 700, color: 'var(--accent-amber)' }}>
                              {item.ceiling.toFixed(2)}
                            </td>
                            <td style={{ textAlign: 'right', color: 'var(--text-secondary)' }}>
                              {item.team_implied.toFixed(1)}
                            </td>
                            <td style={{ textAlign: 'right' }}>
                              <button
                                type="button"
                                onClick={() =>
                                  setSelectedDvpPlayer({
                                    name: item.name,
                                    position: item.position,
                                    team: item.team,
                                    opponent: item.opponent,
                                    opp_soft_rank: item.opp_soft_rank,
                                    opp_tier: item.opp_tier,
                                    opp_tier_label: item.opp_tier_label,
                                    opp_fd_fpa: item.opp_fd_fpa,
                                  })
                                }
                                className="dfs-dvp-badge-btn"
                                style={{
                                  background:
                                    item.opp_soft_rank <= 8
                                      ? 'rgba(16, 185, 129, 0.15)'
                                      : item.opp_soft_rank <= 20
                                      ? 'rgba(255, 255, 255, 0.05)'
                                      : 'rgba(239, 68, 68, 0.15)',
                                  color:
                                    item.opp_soft_rank <= 8
                                      ? 'var(--accent-emerald)'
                                      : item.opp_soft_rank <= 20
                                      ? 'var(--text-secondary)'
                                      : 'var(--accent-rose)',
                                  border: `1px solid ${
                                    item.opp_soft_rank <= 8
                                      ? 'rgba(16, 185, 129, 0.35)'
                                      : item.opp_soft_rank <= 20
                                      ? 'rgba(255, 255, 255, 0.12)'
                                      : 'rgba(239, 68, 68, 0.35)'
                                  }`,
                                }}
                                title={`Opponent DvP #${item.opp_soft_rank}: ${
                                  item.opp_soft_rank <= 8
                                    ? 'Bad Defense (Soft Matchup - Concedes high fantasy points)'
                                    : item.opp_soft_rank <= 20
                                    ? 'Average Defense (Neutral Matchup)'
                                    : 'Good Defense (Tough Matchup - Very stingy)'
                                }. Click for full matchup breakdown.`}
                              >
                                #{item.opp_soft_rank}
                                <span style={{ fontSize: '9px' }}>
                                  {item.opp_soft_rank <= 8 ? '🟢' : item.opp_soft_rank <= 20 ? '⚪' : '🔴'}
                                </span>
                              </button>
                            </td>
                            <td style={{ textAlign: 'center', color: '#d8b4fe', fontWeight: 600 }}>
                              {item.proj_ownership.toFixed(1)}%
                            </td>
                            <td style={{ textAlign: 'right', fontWeight: 700, color: 'var(--accent-emerald)' }}>
                              {item.leverage_score.toFixed(2)}x
                            </td>
                            <td style={{ textAlign: 'center' }}>
                              <div className="dfs-action-btn-group" style={{ justifyContent: 'center' }}>
                                <button
                                  onClick={() => toggleLock(item.name)}
                                  className={`dfs-icon-action-btn ${isLocked ? 'active-lock' : ''}`}
                                  title={isLocked ? 'Unlock player' : 'Lock into roster'}
                                >
                                  🔒
                                </button>
                                <button
                                  onClick={() => toggleExclude(item.name)}
                                  className={`dfs-icon-action-btn ${isExcluded ? 'active-exclude' : ''}`}
                                  title={isExcluded ? 'Un-exclude player' : 'Exclude from roster'}
                                >
                                  🚫
                                </button>
                              </div>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* Forensic Audit Section */}
          {currentDisplayedLineup?.audit && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '16px' }}>
              {/* Stadium Weather Audit */}
              <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '16px' }}>
                <div style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '12px' }}>
                  <span>🌦️</span> Stadium Game-Day Weather
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {currentDisplayedLineup.audit.weather.map((w, i) => (
                    <div
                      key={i}
                      style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 12px', background: 'rgba(15, 23, 42, 0.6)', borderRadius: 'var(--radius-sm)', fontSize: '12px' }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <NFLTeamLogo team={w.team} size={18} />
                        <strong style={{ color: '#ffffff' }}>{w.team}</strong>
                      </div>
                      <span style={{ color: 'var(--text-secondary)' }}>
                        {w.is_dome ? '🏟️ Climate Dome' : `🌡️ ${w.temp}°F | 💨 ${w.wind_mph} mph`}
                      </span>
                      <span style={{ fontWeight: 700, color: w.concern === 'NONE' ? 'var(--accent-emerald)' : 'var(--accent-amber)' }}>
                        {w.concern}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Injury / Practice Status Alerts */}
              <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '16px' }}>
                <div style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '12px' }}>
                  <span>🏥</span> Roster Injury & Practice Status
                </div>
                {currentDisplayedLineup.audit.injury_alerts.length === 0 ? (
                  <div style={{ padding: '12px', background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.25)', borderRadius: 'var(--radius-sm)', color: 'var(--accent-emerald)', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span>✓</span> All 9 starters are fully active with zero injury tags!
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {currentDisplayedLineup.audit.injury_alerts.map((inj, i) => (
                      <div
                        key={i}
                        style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 12px', background: 'rgba(15, 23, 42, 0.6)', borderRadius: 'var(--radius-sm)', fontSize: '12px' }}
                      >
                        <div>
                          <strong style={{ color: '#ffffff' }}>{inj.player}</strong>
                          <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginLeft: '8px' }}>{inj.headline}</span>
                        </div>
                        <span className="dfs-badge dfs-badge-amber">
                          {inj.status} ({inj.practice})
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 6. SUB-VIEW: INTERACTIVE PLAYER POOL & PROJECTIONS */}
      {activeSubView === 'pool' && slateData && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Filter Bar */}
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '12px', background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '12px 16px' }}>
            {/* Position Pills */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
              {['ALL', 'QB', 'RB', 'WR', 'TE', 'D', 'LOCKED', 'EXCLUDED', 'CUSTOM', 'VALUE'].map((pos) => {
                const label =
                  pos === 'D'
                    ? 'D/ST'
                    : pos === 'LOCKED'
                    ? `🔒 Locked (${lockPlayers.length})`
                    : pos === 'EXCLUDED'
                    ? `🚫 Excluded (${excludePlayers.length})`
                    : pos === 'CUSTOM'
                    ? `✏️ Custom (${Object.keys(customProjections).length})`
                    : pos === 'VALUE'
                    ? '⭐ Value (>2.5x)'
                    : pos
                return (
                  <button
                    key={pos}
                    onClick={() => setPositionFilter(pos)}
                    style={{
                      padding: '6px 12px',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: '11px',
                      fontWeight: 700,
                      border: '1px solid',
                      cursor: 'pointer',
                      background: positionFilter === pos ? 'var(--accent-cyan)' : 'rgba(15, 23, 42, 0.7)',
                      color: positionFilter === pos ? '#080c14' : 'var(--text-secondary)',
                      borderColor: positionFilter === pos ? 'var(--accent-cyan)' : 'var(--border-subtle)',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    {label}
                  </button>
                )
              })}
            </div>

            {/* Search Input */}
            <div style={{ position: 'relative', width: '240px' }}>
              <input
                type="text"
                placeholder="Search player or team..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  width: '100%',
                  background: 'rgba(15, 23, 42, 0.9)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '7px 12px',
                  fontSize: '12px',
                  color: '#ffffff',
                  outline: 'none',
                }}
              />
            </div>
          </div>

          {/* Player Table */}
          <div className="dfs-table-wrapper">
            <div className="dfs-table-scroll">
              <table className="dfs-table">
                <thead>
                  <tr>
                    <th>Pos</th>
                    <th className="sortable" onClick={() => handleSort('name')}>Player</th>
                    <th className="sortable" onClick={() => handleSort('team')}>Team</th>
                    <th>Opp</th>
                    <th className="sortable" onClick={() => handleSort('salary')} style={{ textAlign: 'right' }}>Salary</th>
                    <th className="sortable" onClick={() => handleSort('proj')} style={{ textAlign: 'right' }}>Proj Pts</th>
                    <th className="sortable" onClick={() => handleSort('ceiling_proj')} style={{ textAlign: 'right' }}>Ceiling</th>
                    <th className="sortable" onClick={() => handleSort('value_ratio')} style={{ textAlign: 'right' }}>Value</th>
                    <th className="sortable" onClick={() => handleSort('opp_soft_rank')} style={{ textAlign: 'right' }}>
                      <div style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', justifyContent: 'flex-end' }}>
                        <span>DvP Rank</span>
                        <button
                          type="button"
                          className="dfs-dvp-help-icon"
                          onClick={(e) => {
                            e.stopPropagation()
                            setShowDvpLegendModal(true)
                          }}
                          title="What is DvP Rank? Click to see explanation."
                        >
                          ?
                        </button>
                      </div>
                    </th>
                    <th className="sortable" onClick={() => handleSort('proj_ownership')} style={{ textAlign: 'center' }}>Own %</th>
                    <th className="sortable" onClick={() => handleSort('leverage_score')} style={{ textAlign: 'right' }}>Leverage</th>
                    <th style={{ textAlign: 'center' }}>Lock / Exclude</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredAndSortedPlayers.map((p, idx) => {
                    const isLocked = lockPlayers.includes(p.name)
                    const isExcluded = excludePlayers.includes(p.name)
                    const hasCustomProj = customProjections[p.name] !== undefined
                    const displayProj = hasCustomProj ? customProjections[p.name] : p.proj

                    return (
                      <tr key={idx} className={isLocked ? 'locked-row' : isExcluded ? 'excluded-row' : ''}>
                        <td>
                          <span className={`dfs-pos-pill ${p.position.toLowerCase()}`}>
                            {p.position}
                          </span>
                        </td>
                        <td>
                          <div className="dfs-player-meta">
                            <span className="dfs-player-name">{p.name}</span>
                          </div>
                        </td>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <NFLTeamLogo team={p.team} size={18} />
                            <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>{p.team}</span>
                          </div>
                        </td>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <NFLTeamLogo team={p.opponent} size={16} />
                            <span style={{ color: 'var(--text-muted)' }}>{p.opponent}</span>
                          </div>
                        </td>
                        <td style={{ textAlign: 'right', fontWeight: 800, color: '#ffffff' }}>
                          ${p.salary.toLocaleString()}
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          <div className="dfs-editable-proj-cell">
                            <input
                              type="number"
                              step="0.1"
                              value={hasCustomProj ? displayProj : Number(displayProj).toFixed(1)}
                              onChange={(e) => updateCustomProjection(p.name, parseFloat(e.target.value) || 0)}
                              className={`dfs-proj-input ${hasCustomProj ? 'custom' : ''}`}
                              title="Click to edit custom projection for this player"
                            />
                          </div>
                        </td>
                        <td style={{ textAlign: 'right', fontWeight: 700, color: 'var(--accent-amber)' }}>
                          {p.ceiling_proj.toFixed(2)}
                        </td>
                        <td style={{ textAlign: 'right', fontWeight: 700, color: 'var(--accent-emerald)' }}>
                          {p.value_ratio.toFixed(2)}x
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          <button
                            type="button"
                            onClick={() =>
                              setSelectedDvpPlayer({
                                name: p.name,
                                position: p.position,
                                team: p.team,
                                opponent: p.opponent,
                                opp_soft_rank: p.opp_soft_rank,
                                opp_tier: p.opp_tier,
                                opp_tier_label: p.opp_tier_label,
                                opp_fd_fpa: p.opp_fd_fpa,
                              })
                            }
                            className="dfs-dvp-badge-btn"
                            style={{
                              background:
                                p.opp_soft_rank <= 8
                                  ? 'rgba(16, 185, 129, 0.15)'
                                  : p.opp_soft_rank <= 20
                                  ? 'rgba(255, 255, 255, 0.05)'
                                  : 'rgba(239, 68, 68, 0.15)',
                              color:
                                p.opp_soft_rank <= 8
                                  ? 'var(--accent-emerald)'
                                  : p.opp_soft_rank <= 20
                                  ? 'var(--text-secondary)'
                                  : 'var(--accent-rose)',
                              border: `1px solid ${
                                p.opp_soft_rank <= 8
                                  ? 'rgba(16, 185, 129, 0.35)'
                                  : p.opp_soft_rank <= 20
                                  ? 'rgba(255, 255, 255, 0.12)'
                                  : 'rgba(239, 68, 68, 0.35)'
                              }`,
                            }}
                            title={`Opponent DvP #${p.opp_soft_rank}: ${
                              p.opp_soft_rank <= 8
                                ? 'Bad Defense (Soft Matchup - Concedes high fantasy points)'
                                : p.opp_soft_rank <= 20
                                ? 'Average Defense (Neutral Matchup)'
                                : 'Good Defense (Tough Matchup - Very stingy)'
                            }. Click for full matchup breakdown.`}
                          >
                            #{p.opp_soft_rank}
                            <span style={{ fontSize: '9px' }}>
                              {p.opp_soft_rank <= 8 ? '🟢' : p.opp_soft_rank <= 20 ? '⚪' : '🔴'}
                            </span>
                          </button>
                        </td>
                        <td style={{ textAlign: 'center', color: '#d8b4fe', fontWeight: 600 }}>
                          {p.proj_ownership.toFixed(1)}%
                        </td>
                        <td style={{ textAlign: 'right', fontWeight: 700, color: 'var(--accent-emerald)' }}>
                          {p.leverage_score.toFixed(2)}x
                        </td>
                        <td style={{ textAlign: 'center' }}>
                          <div className="dfs-action-btn-group" style={{ justifyContent: 'center' }}>
                            <button
                              onClick={() => toggleLock(p.name)}
                              className={`dfs-icon-action-btn ${isLocked ? 'active-lock' : ''}`}
                              title={isLocked ? 'Unlock player' : 'Lock player'}
                            >
                              🔒
                            </button>
                            <button
                              onClick={() => toggleExclude(p.name)}
                              className={`dfs-icon-action-btn ${isExcluded ? 'active-exclude' : ''}`}
                              title={isExcluded ? 'Un-exclude player' : 'Exclude player'}
                            >
                              🚫
                            </button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* 7. SUB-VIEW: PORTFOLIO EXPOSURE BREAKDOWN */}
      {activeSubView === 'exposure' && lineup?.exposure && (
        <div className="dfs-exposure-card">
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '12px' }}>
            <div>
              <h3 style={{ fontSize: '15px', fontWeight: 800, color: '#ffffff' }}>Portfolio Player Exposure Analysis</h3>
              <p style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                Percentage of solved lineups each player appears in across your portfolio.
              </p>
            </div>

            {/* Position filter */}
            <div style={{ display: 'flex', gap: '6px' }}>
              {['ALL', 'QB', 'RB', 'WR', 'TE', 'D'].map((pos) => (
                <button
                  key={pos}
                  onClick={() => setExposurePosFilter(pos)}
                  style={{
                    padding: '4px 10px',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '11px',
                    fontWeight: 700,
                    border: '1px solid var(--border-subtle)',
                    background: exposurePosFilter === pos ? 'var(--accent-cyan)' : 'transparent',
                    color: exposurePosFilter === pos ? '#080c14' : 'var(--text-secondary)',
                    cursor: 'pointer',
                  }}
                >
                  {pos === 'D' ? 'D/ST' : pos}
                </button>
              ))}
            </div>
          </div>

          <div className="dfs-exposure-grid">
            {exposureList.map((exp, i) => (
              <div key={i} className="dfs-exposure-item">
                <div className="dfs-exposure-top">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span className={`dfs-pos-pill ${exp.position.toLowerCase()}`}>{exp.position}</span>
                    <strong style={{ color: '#ffffff' }}>{exp.name}</strong>
                    <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>({exp.team})</span>
                  </div>
                  <strong style={{ color: exp.pct >= 75 ? 'var(--accent-emerald)' : exp.pct >= 40 ? 'var(--accent-cyan)' : 'var(--text-secondary)' }}>
                    {exp.pct.toFixed(0)}% ({exp.count}/{exp.total_lineups})
                  </strong>
                </div>
                <div className="dfs-exposure-bar-bg">
                  <div
                    className="dfs-exposure-bar-fill"
                    style={{ width: `${Math.min(100, Math.max(5, exp.pct))}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 8. SUB-VIEW: TOP GAME STACKS */}
      {activeSubView === 'stacks' && slateData && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
            Ranked by combined projection, shootout equity, pace, and correlation multiplier (QB + Primary Pass Catcher + Opposing Bring-Back).
          </div>

          <div className="dfs-stacks-grid">
            {slateData.top_stacks.map((st, i) => (
              <div key={i} className="dfs-stack-card">
                <div className="dfs-stack-header">
                  <div>
                    <span className="dfs-badge dfs-badge-amber">Stack #{i + 1}</span>
                    <h3 style={{ fontSize: '16px', fontWeight: 800, color: '#ffffff', marginTop: '4px' }}>
                      {st.game}
                    </h3>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Vegas Total</div>
                    <div style={{ fontSize: '14px', fontWeight: 800, color: 'var(--accent-emerald)' }}>
                      {st.game_ou} O/U
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div className="dfs-stack-row">
                    <span style={{ color: 'var(--text-muted)' }}>Quarterback:</span>
                    <strong style={{ color: '#ffffff' }}>{st.qb}</strong>
                  </div>
                  <div className="dfs-stack-row">
                    <span style={{ color: 'var(--text-muted)' }}>Primary Target:</span>
                    <strong style={{ color: 'var(--accent-cyan)' }}>{st.target}</strong>
                  </div>
                  <div className="dfs-stack-row">
                    <span style={{ color: 'var(--text-muted)' }}>Opposing Bring-Back:</span>
                    <strong style={{ color: 'var(--accent-amber)' }}>{st.bring_back}</strong>
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', textAlign: 'center', paddingTop: '10px', borderTop: '1px solid var(--border-subtle)', fontSize: '12px' }}>
                  <div>
                    <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Cost</div>
                    <strong style={{ color: '#ffffff' }}>${st.total_salary.toLocaleString()}</strong>
                  </div>
                  <div>
                    <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Combined Proj</div>
                    <strong style={{ color: 'var(--accent-cyan)' }}>{st.total_proj.toFixed(1)} pts</strong>
                  </div>
                  <div>
                    <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Value Rate</div>
                    <strong style={{ color: 'var(--accent-emerald)' }}>{st.avg_value.toFixed(2)}x</strong>
                  </div>
                </div>

                <button
                  className="dfs-stack-action-btn"
                  onClick={() => {
                    const qbName = st.qb.split(' (')[0]
                    setStackQb(qbName)
                    setStrategyMode('SINGLE_ENTRY_GPP')
                    setSuccessMsg(`Target stack set to ${qbName}! Click Optimize to generate.`)
                  }}
                >
                  ⚡ Target & Stack This Game
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 9. SUB-VIEW: LEVERAGE & CHALK RADAR */}
      {activeSubView === 'leverage' && slateData && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '20px' }}>
          {/* Tournament Leverage */}
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-lg)', padding: '20px', display: 'flex', flexDirection: 'column', gap: '14px', boxShadow: 'var(--shadow-card)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '20px' }}>🎯</span>
                <h3 style={{ fontSize: '14px', fontWeight: 800, color: '#ffffff', textTransform: 'uppercase' }}>
                  Top Tournament Leverage
                </h3>
              </div>
              <span className="dfs-badge dfs-badge-emerald">&lt;14% Own</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {slateData.leverage_plays.map((p, i) => (
                <div
                  key={i}
                  style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', background: 'rgba(15, 23, 42, 0.6)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', fontSize: '12px' }}
                >
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <strong style={{ color: '#ffffff' }}>{p.name}</strong>
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>({p.position} - {p.team})</span>
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                      ${p.salary.toLocaleString()} | Proj: {p.proj.toFixed(1)} | Ceiling: {p.ceiling_proj.toFixed(1)}
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ color: 'var(--accent-emerald)', fontWeight: 800 }}>{p.leverage_score.toFixed(2)}x Lev</div>
                      <div style={{ color: '#d8b4fe', fontSize: '11px' }}>{p.proj_ownership.toFixed(1)}% Own</div>
                    </div>
                    <button
                      onClick={() => toggleLock(p.name)}
                      className={`dfs-icon-action-btn ${lockPlayers.includes(p.name) ? 'active-lock' : ''}`}
                      title="Lock as tournament leverage"
                    >
                      🔒
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Chalk Radar */}
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-lg)', padding: '20px', display: 'flex', flexDirection: 'column', gap: '14px', boxShadow: 'var(--shadow-card)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '20px' }}>🔥</span>
                <h3 style={{ fontSize: '14px', fontWeight: 800, color: '#ffffff', textTransform: 'uppercase' }}>
                  Consensus Chalk Radar
                </h3>
              </div>
              <span className="dfs-badge dfs-badge-amber">High Field Exposure</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {slateData.chalk_plays.map((p, i) => (
                <div
                  key={i}
                  style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', background: 'rgba(15, 23, 42, 0.6)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', fontSize: '12px' }}
                >
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <strong style={{ color: '#ffffff' }}>{p.name}</strong>
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>({p.position} - {p.team})</span>
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                      ${p.salary.toLocaleString()} | Proj: {p.proj.toFixed(1)} | Value: {p.value_ratio.toFixed(2)}x
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ color: 'var(--accent-amber)', fontWeight: 800 }}>{p.proj_ownership.toFixed(1)}% Own</div>
                      <div style={{ color: 'var(--text-muted)', fontSize: '11px' }}>{p.ownership_tier}</div>
                    </div>
                    <button
                      onClick={() => toggleExclude(p.name)}
                      className={`dfs-icon-action-btn ${excludePlayers.includes(p.name) ? 'active-exclude' : ''}`}
                      title="Exclude chalk player to pivot"
                    >
                      🚫
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ==========================================================================
          MODAL: Player-Specific DvP Matchup Breakdown
          ========================================================================== */}
      {selectedDvpPlayer && (
        <div className="modal-overlay" onClick={() => setSelectedDvpPlayer(null)}>
          <div className="dfs-dvp-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <div className="modal-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span>🛡️ Defense vs. Position (DvP)</span>
                  <span className={`dfs-pos-pill ${selectedDvpPlayer.position.toLowerCase()}`}>
                    {selectedDvpPlayer.position}
                  </span>
                </div>
                <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <NFLTeamLogo team={selectedDvpPlayer.team} size={18} />
                  <strong style={{ color: '#ffffff' }}>{selectedDvpPlayer.name}</strong> ({selectedDvpPlayer.team}) vs. <NFLTeamLogo team={selectedDvpPlayer.opponent} size={18} /> <strong style={{ color: 'var(--accent-cyan)' }}>{selectedDvpPlayer.opponent}</strong>
                </div>
              </div>
              <button className="modal-close-btn" onClick={() => setSelectedDvpPlayer(null)}>✕</button>
            </div>

            <div className="modal-body" style={{ padding: '20px' }}>
              {/* Dynamic Verdict Callout */}
              <div className={`dfs-dvp-verdict-box ${
                selectedDvpPlayer.opp_soft_rank <= 8
                  ? 'smash'
                  : selectedDvpPlayer.opp_soft_rank <= 15
                  ? 'favorable'
                  : selectedDvpPlayer.opp_soft_rank <= 20
                  ? 'neutral'
                  : 'tough'
              }`}>
                <div className="dfs-dvp-verdict-title">
                  {selectedDvpPlayer.opp_soft_rank <= 8 ? (
                    <>
                      <span>🟢</span>
                      <span style={{ color: 'var(--accent-emerald)' }}>
                        OPPONENT DEFENSE IS BAD VS {selectedDvpPlayer.position}s (SMASH SPOT)
                      </span>
                    </>
                  ) : selectedDvpPlayer.opp_soft_rank <= 15 ? (
                    <>
                      <span>🟢</span>
                      <span style={{ color: 'var(--accent-cyan)' }}>
                        OPPONENT DEFENSE IS BELOW AVERAGE (FAVORABLE)
                      </span>
                    </>
                  ) : selectedDvpPlayer.opp_soft_rank <= 20 ? (
                    <>
                      <span>⚪</span>
                      <span style={{ color: 'var(--text-primary)' }}>
                        OPPONENT DEFENSE IS LEAGUE AVERAGE (NEUTRAL)
                      </span>
                    </>
                  ) : (
                    <>
                      <span>🔴</span>
                      <span style={{ color: 'var(--accent-rose)' }}>
                        OPPONENT DEFENSE IS VERY GOOD (TOUGH / LOCKDOWN)
                      </span>
                    </>
                  )}
                </div>
                <div className="dfs-dvp-verdict-desc">
                  {['D', 'DEF', 'DST', 'D/ST'].includes(selectedDvpPlayer.position.toUpperCase()) ? (
                    selectedDvpPlayer.opp_soft_rank <= 8 ? (
                      <>The <strong>{selectedDvpPlayer.opponent}</strong> offense turns the ball over and surrenders sacks at one of the highest rates in the NFL (ranked <strong>#{selectedDvpPlayer.opp_soft_rank}</strong> in generosity). This creates immense sack and turnover upside for the <strong>{selectedDvpPlayer.team}</strong> defense.</>
                    ) : selectedDvpPlayer.opp_soft_rank <= 20 ? (
                      <>The <strong>{selectedDvpPlayer.opponent}</strong> offense has typical league-average sack and turnover numbers. Matchup is neutral.</>
                    ) : (
                      <>The <strong>{selectedDvpPlayer.opponent}</strong> offense is disciplined, elite at ball security, and rarely concedes sacks or turnovers (ranked <strong>#{selectedDvpPlayer.opp_soft_rank}</strong> in difficulty). A lower-ceiling spot for <strong>{selectedDvpPlayer.team}</strong> D/ST.</>
                    )
                  ) : (
                    selectedDvpPlayer.opp_soft_rank <= 8 ? (
                      <>The <strong>{selectedDvpPlayer.opponent}</strong> defense struggles mightily against {selectedDvpPlayer.position}s, conceding the <strong>#{selectedDvpPlayer.opp_soft_rank} most fantasy points</strong> in the entire NFL{selectedDvpPlayer.opp_fd_fpa ? ` (~${selectedDvpPlayer.opp_fd_fpa.toFixed(1)} FPPG)` : ''}. This is an elite scoring spot for <strong>{selectedDvpPlayer.name}</strong>.</>
                    ) : selectedDvpPlayer.opp_soft_rank <= 15 ? (
                      <>The <strong>{selectedDvpPlayer.opponent}</strong> defense allows above-average fantasy production to {selectedDvpPlayer.position}s (rank <strong>#{selectedDvpPlayer.opp_soft_rank}</strong> of 32 in softness). Good ceiling potential for <strong>{selectedDvpPlayer.name}</strong>.</>
                    ) : selectedDvpPlayer.opp_soft_rank <= 20 ? (
                      <>The <strong>{selectedDvpPlayer.opponent}</strong> defense is middle-of-the-pack against {selectedDvpPlayer.position}s (rank <strong>#{selectedDvpPlayer.opp_soft_rank}</strong> of 32). Performance will depend primarily on team game script and individual volume rather than defensive vulnerability.</>
                    ) : (
                      <>The <strong>{selectedDvpPlayer.opponent}</strong> defense is <strong>lockdown and stingy</strong> against {selectedDvpPlayer.position}s, allowing only the <strong>#{33 - selectedDvpPlayer.opp_soft_rank} fewest fantasy points</strong> in the NFL. Expect tough coverage, crowded boxes, and lower touchdown efficiency for <strong>{selectedDvpPlayer.name}</strong>.</>
                    )
                  )}
                </div>
              </div>

              {/* 3-Column Key Metric Highlights */}
              <div className="dfs-dvp-grid">
                <div className="dfs-dvp-stat-card">
                  <span className="label">Softness Rank</span>
                  <span className="value" style={{
                    color: selectedDvpPlayer.opp_soft_rank <= 8 ? 'var(--accent-emerald)' : selectedDvpPlayer.opp_soft_rank <= 20 ? '#ffffff' : 'var(--accent-rose)'
                  }}>
                    #{selectedDvpPlayer.opp_soft_rank} of 32
                  </span>
                </div>

                <div className="dfs-dvp-stat-card">
                  <span className="label">Opponent Quality</span>
                  <span className="value" style={{
                    fontSize: '13px',
                    color: selectedDvpPlayer.opp_soft_rank <= 8 ? 'var(--accent-emerald)' : selectedDvpPlayer.opp_soft_rank <= 20 ? 'var(--text-secondary)' : 'var(--accent-rose)'
                  }}>
                    {selectedDvpPlayer.opp_soft_rank <= 8 ? 'Weak Defense' : selectedDvpPlayer.opp_soft_rank <= 15 ? 'Below Average' : selectedDvpPlayer.opp_soft_rank <= 20 ? 'Average' : 'Elite Defense'}
                  </span>
                </div>

                <div className="dfs-dvp-stat-card">
                  <span className="label">Fantasy Matchup</span>
                  <span className="value" style={{
                    fontSize: '13px',
                    color: selectedDvpPlayer.opp_soft_rank <= 8 ? 'var(--accent-emerald)' : selectedDvpPlayer.opp_soft_rank <= 20 ? 'var(--text-secondary)' : 'var(--accent-rose)'
                  }}>
                    {selectedDvpPlayer.opp_tier_label || (selectedDvpPlayer.opp_soft_rank <= 8 ? 'Smash Spot' : selectedDvpPlayer.opp_soft_rank <= 20 ? 'Neutral' : 'Tough Matchup')}
                  </span>
                </div>
              </div>

              {/* Visual Spectrum Meter */}
              <div className="dfs-dvp-spectrum-wrap">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '12px', fontWeight: 700, color: '#ffffff' }}>Matchup Spectrum</span>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    Position: <strong style={{ color: 'var(--accent-cyan)' }}>#{selectedDvpPlayer.opp_soft_rank}</strong>
                  </span>
                </div>

                <div className="dfs-dvp-spectrum-bar">
                  <div
                    className="dfs-dvp-spectrum-pin"
                    style={{ left: `${Math.max(4, Math.min(96, ((selectedDvpPlayer.opp_soft_rank - 1) / 31) * 100))}%` }}
                    title={`Rank #${selectedDvpPlayer.opp_soft_rank}`}
                  >
                    {selectedDvpPlayer.opp_soft_rank}
                  </div>
                </div>

                <div className="dfs-dvp-spectrum-labels">
                  <span style={{ color: 'var(--accent-emerald)' }}>#1 Softest (Opponent is Bad)</span>
                  <span style={{ color: 'var(--text-muted)' }}>#16 Average</span>
                  <span style={{ color: 'var(--accent-rose)' }}>#32 Toughest (Opponent is Good)</span>
                </div>
              </div>

              {/* Quick Cheatsheet Guide */}
              <div className="dfs-dvp-legend-rows">
                <div className="dfs-dvp-legend-item">
                  <span style={{ fontSize: '16px' }}>🟢</span>
                  <div>
                    <strong style={{ color: 'var(--accent-emerald)' }}>Ranks #1–8 (Green) = Bad Defense (Easy Matchup):</strong> The opponent concedes high yardage and touchdowns. Prime target for cash games and tournament ceilings.
                  </div>
                </div>
                <div className="dfs-dvp-legend-item">
                  <span style={{ fontSize: '16px' }}>⚪</span>
                  <div>
                    <strong style={{ color: 'var(--text-secondary)' }}>Ranks #9–20 (Gray) = Neutral Matchup:</strong> Standard league defense. Rely on Vegas team implied totals and target share.
                  </div>
                </div>
                <div className="dfs-dvp-legend-item">
                  <span style={{ fontSize: '16px' }}>🔴</span>
                  <div>
                    <strong style={{ color: 'var(--accent-rose)' }}>Ranks #21–32 (Red) = Good Defense (Tough Matchup):</strong> Opponent is stout and limits explosive plays. Consider under-weighting or fading in tournaments unless price heavily discounts risk.
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ==========================================================================
          MODAL: Overall DvP Explainer Guide
          ========================================================================== */}
      {showDvpLegendModal && (
        <div className="modal-overlay" onClick={() => setShowDvpLegendModal(false)}>
          <div className="dfs-dvp-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <div className="modal-title">📖 What is DvP (Defense vs. Position) Rank?</div>
                <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                  How to read and interpret DvP ranks on this DFS Optimizer
                </div>
              </div>
              <button className="modal-close-btn" onClick={() => setShowDvpLegendModal(false)}>✕</button>
            </div>

            <div className="modal-body" style={{ padding: '20px' }}>
              <div style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: '20px' }}>
                <strong>Defense vs. Position (DvP)</strong> measures how many fantasy points the opposing defense allows to a specific position (QB, RB, WR, TE, or D/ST) across all 32 NFL teams.
              </div>

              {/* Visual Spectrum */}
              <div className="dfs-dvp-spectrum-wrap">
                <div style={{ fontSize: '12px', fontWeight: 700, color: '#ffffff', marginBottom: '8px' }}>
                  The 1 to 32 Softness Scale
                </div>
                <div className="dfs-dvp-spectrum-bar" style={{ margin: '14px 0 10px 0' }}></div>
                <div className="dfs-dvp-spectrum-labels">
                  <span style={{ color: 'var(--accent-emerald)' }}>#1 Softest (Defense is BAD)</span>
                  <span style={{ color: 'var(--text-muted)' }}>#16 Neutral (Average)</span>
                  <span style={{ color: 'var(--accent-rose)' }}>#32 Toughest (Defense is GOOD)</span>
                </div>
              </div>

              {/* Legend Cards */}
              <div className="dfs-dvp-legend-rows">
                <div className="dfs-dvp-legend-item" style={{ borderLeft: '3px solid var(--accent-emerald)' }}>
                  <span style={{ fontSize: '18px' }}>🟢</span>
                  <div>
                    <div style={{ fontWeight: 800, color: 'var(--accent-emerald)', marginBottom: '2px' }}>
                      Rank #1–8: Soft Matchup (Opposing Defense is BAD)
                    </div>
                    <div style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>
                      The opposing defense concedes the most fantasy points and yardage to this position. Highly favorable environment that boosts player projections and ceiling upside.
                    </div>
                  </div>
                </div>

                <div className="dfs-dvp-legend-item" style={{ borderLeft: '3px solid var(--text-muted)' }}>
                  <span style={{ fontSize: '18px' }}>⚪</span>
                  <div>
                    <div style={{ fontWeight: 800, color: '#ffffff', marginBottom: '2px' }}>
                      Rank #9–20: Neutral Matchup (League Average)
                    </div>
                    <div style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>
                      The defense is middle-of-the-road. Fantasy outcomes will depend heavily on individual usage, team implied totals, and pace of play.
                    </div>
                  </div>
                </div>

                <div className="dfs-dvp-legend-item" style={{ borderLeft: '3px solid var(--accent-rose)' }}>
                  <span style={{ fontSize: '18px' }}>🔴</span>
                  <div>
                    <div style={{ fontWeight: 800, color: 'var(--accent-rose)', marginBottom: '2px' }}>
                      Rank #21–32: Tough Matchup (Opposing Defense is GOOD)
                    </div>
                    <div style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>
                      The opponent is a lockdown defense that gives up very few fantasy points and limits touchdowns. Difficult spot that lowers safety floors.
                    </div>
                  </div>
                </div>
              </div>

              <div style={{ marginTop: '20px', padding: '12px 16px', background: 'rgba(6, 182, 212, 0.08)', borderRadius: 'var(--radius-sm)', border: '1px solid rgba(6, 182, 212, 0.25)', fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                💡 <strong style={{ color: 'var(--accent-cyan)' }}>Pro Tip:</strong> Click directly on any player's <strong>#DvP badge</strong> in the table at any time to see their specific matchup breakdown, points allowed, and game script analysis!
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
