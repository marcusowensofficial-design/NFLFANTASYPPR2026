import React, { useState, useRef, useEffect, useCallback } from 'react'
import { createPortal } from 'react-dom'

export interface GlossaryEntry {
  title: string
  acronym?: string
  beginnerDef: string
  proStrategy: string
  category?: 'MATCHUP' | 'VEGAS' | 'STRATEGY' | 'ROSTER' | 'ANALYTICS'
}

export const PPR_GLOSSARY: Record<string, GlossaryEntry> = {
  DVP: {
    title: 'Defense vs. Position (DvP)',
    acronym: 'DvP',
    category: 'MATCHUP',
    beginnerDef:
      'Ranks how many fantasy points the opposing defense gives up to this specific position. 1st is the toughest lockdown defense; 32nd is the softest, most favorable matchup.',
    proStrategy:
      'Target 25th–32nd ranked defenses for streaming flex plays and tight ends. For 8-man leagues, bench borderline starters facing Top-5 pass defenses.',
  },
  ITT: {
    title: 'Vegas Implied Team Total (ITT)',
    acronym: 'ITT',
    category: 'VEGAS',
    beginnerDef:
      'The exact number of points sportsbooks expect this team to score based on the spread and over/under. High totals mean more trips to the red zone.',
    proStrategy:
      'Prioritize players on teams with 24.0+ implied points. A 3-point ITT increase roughly correlates to +1.2 expected touchdowns for the offense.',
  },
  BORIS_TIER: {
    title: 'Boris Chen GMM Tier',
    acronym: 'Tiers',
    category: 'ANALYTICS',
    beginnerDef:
      'Uses statistical clustering (Gaussian Mixture Models) on expert rankings to group players into tiers. Players in the same tier have statistically indistinguishable projections.',
    proStrategy:
      'Never agonize over 0.3 projected points between players in the same tier. When choosing between tier-mates, let high Vegas game totals and weather break the tie.',
  },
  VEGAS_PROPS: {
    title: 'Vegas Sportsbook Player Props',
    acronym: 'Props',
    category: 'VEGAS',
    beginnerDef:
      'Over/Under lines set by sportsbooks with millions of dollars on the line. In PPR leagues, 5.5+ Receptions O/U is the gold standard for weekly floor.',
    proStrategy:
      'Betting prop totals consistently outperform human analyst rankings. In Full PPR, an anytime touchdown with positive juice combined with 5+ receptions guarantees an elite cash floor.',
  },
  WRCB: {
    title: 'WR vs. CB Coverage Matrix',
    acronym: 'WR/CB',
    category: 'MATCHUP',
    beginnerDef:
      'Analyzes individual receiver speed and route alignments (Slot vs Outside) against the opposing cornerbacks, highlighting lockdown shadow coverage.',
    proStrategy:
      'Look for slot receivers facing backup nickels or defenses running heavy Cover 3. Downgrade perimeter WRs shadowed by elite CB1s traveling across formations.',
  },
  SHADOW_CB: {
    title: 'Shadow Coverage Lockdown Alert',
    acronym: 'Shadow CB',
    category: 'MATCHUP',
    beginnerDef:
      'The opposing defense has an elite CB1 who travels across formations to cover this specific wide receiver on 75%+ of routes.',
    proStrategy:
      'Shadow coverage severely caps target ceiling and explosive play rates. When a WR is shadowed by a lockdown corner (e.g. Surtain), pivot to secondary targets or slot options.',
  },
  VORP: {
    title: 'Value Over Replacement Player (VORP)',
    acronym: 'VORP',
    category: 'ROSTER',
    beginnerDef:
      'How many points this player scores compared to the best free agent sitting on your league waiver wire. In 8-man leagues, replacement players are already high caliber.',
    proStrategy:
      'In shallow 8-man formats, depth is plentiful on waivers. Never hoard mediocre bench players with zero VORP—stash high-upside backup running backs with massive contingent ceilings.',
  },
  GAME_SCRIPT: {
    title: 'Vegas Game Script Environment',
    acronym: 'Script',
    category: 'VEGAS',
    beginnerDef:
      'Predicts the flow of the game: high-scoring shootouts, ground-and-pound blowouts where favorites run out the clock, or defensive trench battles.',
    proStrategy:
      'Underdogs in fast-paced games throw heavily in the second half (elevating WR target share). Large favorites produce high-volume 4th-quarter rushing for lead running backs.',
  },
  CEILING_FLOOR: {
    title: 'Boom Ceiling vs. Bust Resistance Floor',
    acronym: 'Range',
    category: 'STRATEGY',
    beginnerDef:
      'Ceiling is the 90th percentile boom score when everything goes right. Floor is the 20th percentile safety net if the player gets game-scripted out.',
    proStrategy:
      'If you are a heavy underdog in your weekly matchup, switch to CEILING mode to chase high-variance boom candidates. If you are favored by 10+, choose FLOOR.',
  },
  FLEX_RISK: {
    title: 'Anti-Early Kickoff FLEX Protection',
    acronym: 'Flex Guard',
    category: 'ROSTER',
    beginnerDef:
      'Never put Thursday night or early Saturday players in your FLEX spot. Always put them in their primary position (RB or WR).',
    proStrategy:
      'Keeping your FLEX open for the Sunday late afternoon and Monday night games gives you maximum flexibility to swap candidates if an injury strikes over the weekend.',
  },
  CONSOLIDATION: {
    title: '2-for-1 Roster Consolidation',
    acronym: 'Trades',
    category: 'ROSTER',
    beginnerDef:
      'Trading two good starters to an opponent to get one elite superstar stud in return.',
    proStrategy:
      'In 8-team leagues, championships are won in starting lineups, not on deep benches. Target teams with losing records and trade your depth for Top-5 overall assets.',
  },
  DVP_BASELINE: {
    title: 'Week 1 DvP Baseline Weighting',
    acronym: 'Baseline',
    category: 'MATCHUP',
    beginnerDef:
      'In Week 1, zero current-season regular games have occurred. Defensive matchup ratings are built from the full 2025-26 regular season, with heavy weighting placed on the final eight games.',
    proStrategy:
      'Early season ratings are informative indicators of defensive scheme and personnel continuity, but still stabilizing. By Week 2 and beyond, ratings automatically incorporate fresh 2026-27 game data.',
  },
  DVP_FPA: {
    title: 'DraftKings Fantasy Points Allowed (FPA)',
    acronym: 'DK FPA',
    category: 'MATCHUP',
    beginnerDef:
      'The exact average fantasy points this defense concedes per game to this position group using official DraftKings PPR scoring, including 100-yard and 300-yard bonuses.',
    proStrategy:
      'Higher FPA indicates a softer, more generous defense. Compare opponent FPA against positional league mean (+/- vs Avg) to quantify matchup leverage.',
  },
  DVP_VS_AVG: {
    title: 'Positional Variance vs. League Average',
    acronym: 'vs Avg',
    category: 'MATCHUP',
    beginnerDef:
      'Shows whether this defense gives up more (+) or fewer (-) fantasy points per game to this position than the NFL league-wide average.',
    proStrategy:
      'A +4.0 or higher differential signals an elite smash matchup for streamers and flex decisions. A -4.0 or lower indicates a lockdown defense that suppresses ceiling.',
  },
  MATCHUP_STARS: {
    title: '5-Star Matchup Rating',
    acronym: 'Stars',
    category: 'MATCHUP',
    beginnerDef:
      'A composite 1-to-5 star rating of how favorable this week\'s matchup is for the player\'s position. 5 stars is an elite smash spot; 1 star is a brutal lockdown matchup.',
    proStrategy:
      'Start 4-star and 5-star matchups with extreme confidence. When deciding between close flex candidates, always favor the player with a 4+ star rating.',
  },
  FP_RANK: {
    title: 'FantasyPros Expert Consensus Rank (ECR)',
    acronym: 'FP ECR',
    category: 'ANALYTICS',
    beginnerDef:
      'The average positional rank given to this player across dozens of verified top fantasy football industry analysts.',
    proStrategy:
      'ECR reflects broad market consensus. If our quantitative model ranks a player significantly higher than ECR, it usually highlights an unpriced Vegas shootout or DvP mismatch.',
  },
  CONSENSUS_RANK: {
    title: 'Multi-Source Bayesian Consensus',
    acronym: 'Consensus',
    category: 'ANALYTICS',
    beginnerDef:
      'Our outlier-protected statistical blend combining our Vegas micro-volume model, FantasyPros ECR, Sleeper, and ESPN projections.',
    proStrategy:
      'Consensus removes human analyst bias and prevents single-source projection errors from skewing your weekly start/sit decisions.',
  },
  SLOT_MISMATCH: {
    title: 'PFF Slot Mismatch Advantage',
    acronym: 'Slot Mismatch',
    category: 'MATCHUP',
    beginnerDef:
      'The wide receiver runs high volume from the slot alignment against an opposing nickel cornerback with vulnerable coverage grades.',
    proStrategy:
      'Slot receivers receive quick, short-yardage PPR targets. In full PPR leagues, slot mismatches generate high reception floors regardless of perimeter defense.',
  },
  SHOOTOUT: {
    title: 'Vegas High-Ceiling Shootout',
    acronym: 'Shootout',
    category: 'VEGAS',
    beginnerDef:
      'Sportsbooks have set a high game total (Over/Under 47.5+), meaning Vegas expects lots of offensive scoring drives and explosive plays.',
    proStrategy:
      'Game total is the #1 correlated variable for weekly ceiling. Stack starters from high-total games for maximum tournament and flex upside.',
  },
  BELLCOW: {
    title: '3-Down Bellcow Touch Share',
    acronym: 'Bellcow',
    category: 'STRATEGY',
    beginnerDef:
      'A lead running back who plays on 1st, 2nd, and 3rd downs, handling both early-down carries and passing-down targets/two-minute drill.',
    proStrategy:
      'Bellcows are the lifeblood of PPR leagues because receiving targets are worth 2.5x more fantasy points than rushing attempts.',
  },
  ALPHA_FUNNEL: {
    title: 'Alpha Target Funnel',
    acronym: 'Alpha',
    category: 'STRATEGY',
    beginnerDef:
      'An elite receiver who commands 25%+ of their team\'s passing targets, serving as the undisputed primary read on dropbacks.',
    proStrategy:
      'Alphas are matchup-proof. Even against top cornerbacks, high target volume protects their PPR floor.',
  },
  STARTSCORE: {
    title: 'Algorithmic StartScore (0-100)',
    acronym: 'StartScore',
    category: 'ANALYTICS',
    beginnerDef:
      'A normalized 0-to-100 composite index that weighs volume, Vegas game script, opponent DvP, weather, and injury status into a single decision score.',
    proStrategy:
      'StartScore of 80+ indicates an elite must-start asset. Scores between 65-75 represent high-leverage flex decisions where ceiling/floor mode matters most.',
  },
}

export interface TooltipProps {
  term?: keyof typeof PPR_GLOSSARY | string
  title?: string
  quickDef?: string
  proStrategy?: string
  children?: React.ReactNode
  position?: 'top' | 'bottom' | 'left' | 'right'
  className?: string
}

const CLOSE_ALL_TOOLTIPS_EVENT = 'fantasy-close-all-tooltips'

export const Tooltip: React.FC<TooltipProps> = ({
  term,
  title: customTitle,
  quickDef: customDef,
  proStrategy: customStrategy,
  children,
  className = '',
}) => {
  const [isVisible, setIsVisible] = useState<boolean>(false)
  const [coords, setCoords] = useState<{ top: number; left: number; placement: 'top' | 'bottom' | 'center' }>({
    top: 0,
    left: 0,
    placement: 'bottom',
  })

  const triggerRef = useRef<HTMLSpanElement>(null)
  const idRef = useRef<string>(`tooltip-${Math.random().toString(36).slice(2, 9)}`)

  // Look up glossary data if term is recognized
  const glossaryData = term ? PPR_GLOSSARY[term.toUpperCase()] : undefined
  const displayTitle = glossaryData?.title || customTitle || term || 'Metric Intelligence'
  const quickDef = customDef || glossaryData?.beginnerDef
  const proStrategy = customStrategy || glossaryData?.proStrategy
  const acronym = glossaryData?.acronym || (term ? String(term).toUpperCase() : 'PPR')
  const category = glossaryData?.category || 'ANALYTICS'

  // Position calculation clamped to viewport
  const updatePosition = useCallback(() => {
    if (!triggerRef.current) return
    const rect = triggerRef.current.getBoundingClientRect()
    const cardWidth = Math.min(360, window.innerWidth - 24)
    const cardEstimatedHeight = 250

    // On narrow screens (< 640px), center in viewport
    if (window.innerWidth < 640) {
      setCoords({
        top: Math.max(16, (window.innerHeight - cardEstimatedHeight) / 2),
        left: Math.max(12, (window.innerWidth - cardWidth) / 2),
        placement: 'center',
      })
      return
    }

    // On desktop, place below or above trigger
    const spaceBelow = window.innerHeight - rect.bottom
    const spaceAbove = rect.top
    const placeBelow = spaceBelow >= cardEstimatedHeight || spaceBelow >= spaceAbove

    const top = placeBelow ? rect.bottom + 8 : Math.max(16, rect.top - cardEstimatedHeight - 8)
    const idealLeft = rect.left + rect.width / 2 - cardWidth / 2
    const left = Math.max(16, Math.min(window.innerWidth - cardWidth - 16, idealLeft))

    setCoords({
      top,
      left,
      placement: placeBelow ? 'bottom' : 'top',
    })
  }, [])

  // Handle click on trigger
  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()

    if (isVisible) {
      setIsVisible(false)
    } else {
      // Close other open tooltips
      window.dispatchEvent(
        new CustomEvent(CLOSE_ALL_TOOLTIPS_EVENT, { detail: { exceptId: idRef.current } })
      )
      updatePosition()
      setIsVisible(true)
    }
  }

  // Handle keyboard trigger
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      e.stopPropagation()
      handleClick(e as unknown as React.MouseEvent)
    }
  }

  // Close event listener & Escape key
  useEffect(() => {
    const handleCloseAll = (e: Event) => {
      const customEv = e as CustomEvent<{ exceptId?: string }>
      if (customEv.detail?.exceptId !== idRef.current) {
        setIsVisible(false)
      }
    }

    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isVisible) {
        setIsVisible(false)
      }
    }

    const handleWindowResize = () => {
      if (isVisible) {
        updatePosition()
      }
    }

    window.addEventListener(CLOSE_ALL_TOOLTIPS_EVENT, handleCloseAll)
    window.addEventListener('keydown', handleGlobalKeyDown)
    window.addEventListener('resize', handleWindowResize)

    return () => {
      window.removeEventListener(CLOSE_ALL_TOOLTIPS_EVENT, handleCloseAll)
      window.removeEventListener('keydown', handleGlobalKeyDown)
      window.removeEventListener('resize', handleWindowResize)
    }
  }, [isVisible, updatePosition])

  return (
    <>
      {/* Interactive Trigger Element */}
      <span
        ref={triggerRef}
        onClick={handleClick}
        onKeyDown={handleKeyDown}
        className={`tooltip-clickable-container inline-flex items-center align-middle ${className}`}
        role="button"
        tabIndex={0}
        aria-expanded={isVisible}
        title="Click to learn what this means"
      >
        {children ? (
          <span className={`tooltip-trigger-wrap ${isVisible ? 'tooltip-trigger-active' : ''}`}>
            {children}
          </span>
        ) : (
          <span
            className={`tooltip-info-bubble ${isVisible ? 'tooltip-trigger-active' : ''}`}
            aria-label="Explain metric"
          >
            ?
          </span>
        )}
      </span>

      {/* Portal Explainer Card */}
      {isVisible &&
        typeof document !== 'undefined' &&
        createPortal(
          <>
            {/* Soft transparent backdrop for outside-click dismissal */}
            <div
              className="metric-intel-backdrop"
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                setIsVisible(false)
              }}
            />

            {/* Explainer Card */}
            <div
              className={`metric-intel-flyout ${coords.placement === 'center' ? 'is-centered' : ''}`}
              style={{
                top: `${coords.top}px`,
                left: `${coords.left}px`,
              }}
              onClick={(e) => e.stopPropagation()}
            >
              {/* Header */}
              <div className="metric-intel-header">
                <div className="metric-intel-title-wrap">
                  <span className="metric-intel-indicator"></span>
                  <span className="metric-intel-title">{displayTitle}</span>
                </div>
                <div className="metric-intel-actions">
                  <span className={`metric-intel-category-pill cat-${category.toLowerCase()}`}>
                    {acronym}
                  </span>
                  <button
                    type="button"
                    className="metric-intel-close-btn"
                    onClick={(e) => {
                      e.preventDefault()
                      e.stopPropagation()
                      setIsVisible(false)
                    }}
                    aria-label="Close"
                  >
                    ✕
                  </button>
                </div>
              </div>

              {/* Active Context Value (if customTitle provided and differs from dictionary title) */}
              {customTitle && customTitle !== glossaryData?.title && (
                <div className="metric-intel-active-context">
                  <span className="context-label">📌 Current Value:</span>
                  <span className="context-val">{customTitle}</span>
                </div>
              )}

              {/* Body: What It Means */}
              {quickDef && (
                <div className="metric-intel-section">
                  <div className="metric-intel-section-title">
                    <span>💡</span> WHAT IT MEANS
                  </div>
                  <p className="metric-intel-text">{quickDef}</p>
                </div>
              )}

              {/* Body: Pro Strategy */}
              {proStrategy && (
                <div className="metric-intel-section strategy">
                  <div className="metric-intel-section-title strategy">
                    <span>🎯</span> WINNING EDGE (PRO STRATEGY)
                  </div>
                  <p className="metric-intel-text strategy">{proStrategy}</p>
                </div>
              )}

              {/* Card Footer with Got It confirmation */}
              <div className="metric-intel-footer">
                <button
                  type="button"
                  className="metric-intel-gotit-btn"
                  onClick={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    setIsVisible(false)
                  }}
                >
                  Got it
                </button>
              </div>
            </div>
          </>,
          document.body
        )}
    </>
  )
}
