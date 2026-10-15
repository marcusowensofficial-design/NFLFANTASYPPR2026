import React, { useRef, useMemo } from 'react'
import type { VegasGameEnvironment } from '../../types'
import { NFLTeamLogo } from './NFLTeamLogo'
import { formatToMDT } from '../../utils/dateUtils'

interface LiveMarketTickerProps {
  games: VegasGameEnvironment[]
  onSelectGame?: (game: VegasGameEnvironment) => void
}

export const LiveMarketTicker: React.FC<LiveMarketTickerProps> = ({
  games,
  onSelectGame,
}) => {
  const scrollRef = useRef<HTMLDivElement>(null)

  // Sort games: 1st by earliest kickoff time (chronological), 2nd by highest game total (shootouts first)
  const sortedGames = useMemo(() => {
    if (!games || games.length === 0) return []

    return [...games].sort((a, b) => {
      const timeA = a.game_date ? new Date(a.game_date).getTime() : Infinity
      const timeB = b.game_date ? new Date(b.game_date).getTime() : Infinity

      if (timeA !== timeB) {
        return timeA - timeB
      }

      const totalA = a.over_under || (a.home_implied_total + a.away_implied_total) || 0
      const totalB = b.over_under || (b.home_implied_total + b.away_implied_total) || 0

      return totalB - totalA
    })
  }, [games])

  const scroll = (direction: 'left' | 'right') => {
    if (scrollRef.current) {
      const offset = direction === 'left' ? -300 : 300
      scrollRef.current.scrollBy({ left: offset, behavior: 'smooth' })
    }
  }

  return (
    <div className="live-ticker-container">
      {/* Live Indicator Badge */}
      <div className="ticker-live-badge">
        <span className="ticker-pulse-dot" />
        <span className="ticker-live-text">VEGAS ODDS</span>
      </div>

      {/* Nav Arrow Left */}
      <button
        className="ticker-nav-btn left"
        onClick={() => scroll('left')}
        aria-label="Scroll left"
        title="Scroll previous games"
      >
        ‹
      </button>

      {/* Horizontal Games Track */}
      <div className="ticker-track" ref={scrollRef}>
        {sortedGames && sortedGames.length > 0 ? (
          sortedGames.map((g, idx) => {
            const isShootout = g.over_under >= 47.0
            return (
              <div
                key={idx}
                className={`ticker-game-chip ${isShootout ? 'shootout' : ''}`}
                onClick={() => onSelectGame && onSelectGame(g)}
                role="button"
                tabIndex={0}
                title={`Click to view ${g.away_team} @ ${g.home_team} in Vegas Intelligence`}
              >
                {/* Main Matchup & Odds Row */}
                <div className="ticker-chip-top">
                  {/* Matchup */}
                  <div className="ticker-teams">
                    <div className="ticker-team-row">
                      <NFLTeamLogo team={g.away_team} size={15} />
                      <span className="ticker-team-code">{g.away_team}</span>
                      <span className="ticker-team-implied tabular-nums">{g.away_implied_total?.toFixed(1)}</span>
                    </div>
                    <div className="ticker-team-row">
                      <NFLTeamLogo team={g.home_team} size={15} />
                      <span className="ticker-team-code">{g.home_team}</span>
                      <span className="ticker-team-implied tabular-nums">{g.home_implied_total?.toFixed(1)}</span>
                    </div>
                  </div>

                  {/* Divider */}
                  <div className="ticker-divider" />

                  {/* Market Numbers */}
                  <div className="ticker-odds">
                    <div className="ticker-ou-row">
                      <span className="ticker-label">O/U</span>
                      <span className={`ticker-val tabular-nums ${isShootout ? 'high-total' : ''}`}>
                        {g.over_under?.toFixed(1)}
                      </span>
                    </div>
                    <div className="ticker-spread-row">
                      <span className="ticker-spread-fav">
                        {g.spread_magnitude > 0
                          ? `${g.favorite_team} -${g.spread_magnitude}`
                          : 'PK'}
                      </span>
                    </div>
                  </div>

                  {/* Feature Tags */}
                  {isShootout && (
                    <span className="ticker-tag shootout-tag" title="High Projected Total">
                      🔥
                    </span>
                  )}
                  {g.is_dome && (
                    <span className="ticker-tag dome-tag" title="Indoor / Dome Stadium">
                      🏟️
                    </span>
                  )}
                </div>

                {/* Kickoff Date & Time in Mountain Daylight Time (MDT) */}
                <div className="ticker-game-time tabular-nums">
                  {formatToMDT(g.game_date)}
                </div>
              </div>
            )
          })
        ) : (
          /* Sleek Skeleton Loading Ticker */
          <div className="ticker-skeleton-container">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <div key={i} className="ticker-skeleton-chip">
                <div className="skeleton-line short" />
                <div className="skeleton-line mini" />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Nav Arrow Right */}
      <button
        className="ticker-nav-btn right"
        onClick={() => scroll('right')}
        aria-label="Scroll right"
        title="Scroll next games"
      >
        ›
      </button>
    </div>
  )
}
