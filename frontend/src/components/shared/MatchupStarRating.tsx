import React from 'react'

export function getMatchupStars(rankOrStars?: number | null, oppDvpRank?: number | null): number {
  if (typeof rankOrStars === 'number' && rankOrStars >= 1 && rankOrStars <= 5) {
    return rankOrStars
  }
  if (typeof oppDvpRank === 'number' && oppDvpRank >= 1 && oppDvpRank <= 32) {
    if (oppDvpRank <= 6) return 1
    if (oppDvpRank <= 12) return 2
    if (oppDvpRank <= 20) return 3
    if (oppDvpRank <= 26) return 4
    return 5
  }
  return 3
}

export function getMatchupTierInfo(stars: number, position?: string): { label: string; desc: string; dvpRange: string } {
  const isDst = position === 'D/ST' || position === 'DST'
  switch (stars) {
    case 1:
      return { 
        label: 'Brutal Matchup', 
        desc: isDst ? 'Stifling offense rarely concedes sacks or turnovers' : 'Lockdown defense; stingy unit allows minimal fantasy production', 
        dvpRange: 'DvP #1–6' 
      }
    case 2:
      return { 
        label: 'Tough Matchup', 
        desc: isDst ? 'Efficient offense with solid pass protection & ball security' : 'Below average matchup; stiff defensive resistance', 
        dvpRange: 'DvP #7–12' 
      }
    case 3:
      return { 
        label: 'Neutral Matchup', 
        desc: isDst ? 'Average turnover and sack rate expected' : 'Middle of the pack; standard baseline volume', 
        dvpRange: 'DvP #13–20' 
      }
    case 4:
      return { 
        label: 'Favorable Matchup', 
        desc: isDst ? 'Vulnerable offense prone to sacks and stalled drives' : 'Above average matchup; favorable defensive leaks and scoring upside', 
        dvpRange: 'DvP #21–26' 
      }
    case 5:
      return { 
        label: 'Elite Matchup', 
        desc: isDst ? 'Prime streaming smash: High turnover/sack rate & low implied total' : 'Prime smash matchup; porous bottom-6 defense allows league-high ceiling', 
        dvpRange: 'DvP #27–32' 
      }
    default:
      return { label: 'Neutral Matchup', desc: 'Middle of the pack matchup', dvpRange: 'DvP #13–20' }
  }
}

export const MatchupStarRating: React.FC<{
  stars?: number | null
  oppDvpRank?: number | null
  position?: string
}> = ({ stars: propStars, oppDvpRank, position }) => {
  const stars = getMatchupStars(propStars, oppDvpRank)
  const tierInfo = getMatchupTierInfo(stars, position)

  return (
    <span
      className={`matchup-stars-badge tier-${stars}`}
      title={`FantasyPros Matchup Rating: ${stars}/5 Stars (${tierInfo.label})\n${tierInfo.desc}${oppDvpRank ? `\nOpponent DvP: #${oppDvpRank}${position ? ` vs ${position}` : ''}` : ''}`}
    >
      <span className="matchup-stars-row" aria-label={`${stars} of 5 stars`}>
        {[1, 2, 3, 4, 5].map((s) => (
          <span key={s} className={`star-icon ${s <= stars ? 'filled' : 'empty'}`}>
            ★
          </span>
        ))}
      </span>
      <span className="matchup-stars-text">{stars}/5</span>
    </span>
  )
}
