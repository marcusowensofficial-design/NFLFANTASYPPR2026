/**
 * Date and Kickoff formatting utilities for NFL Games.
 * Converts game timestamps into Mountain Daylight Time (MDT) / Mountain Time (America/Denver).
 *
 * Target Format: "Wed 9-9-26 6:20 P.M. MDT"
 */

export function formatToMDT(dateStr?: string | null): string {
  if (!dateStr) return 'TBD'
  try {
    const d = new Date(dateStr)
    if (isNaN(d.getTime())) return String(dateStr)

    // Format with America/Denver (MDT / MST)
    const formatter = new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/Denver',
      weekday: 'short',
      month: 'numeric',
      day: 'numeric',
      year: '2-digit',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    })

    const parts = formatter.formatToParts(d)
    const get = (type: string) => parts.find((p: Intl.DateTimeFormatPart) => p.type === type)?.value || ''

    const weekday = get('weekday') // e.g. "Wed"
    const month = get('month') // e.g. "9"
    const day = get('day') // e.g. "9"
    const year = get('year') // e.g. "26"
    const hour = get('hour') // e.g. "6"
    const minute = get('minute') // e.g. "20"
    const rawPeriod = get('dayPeriod').toUpperCase()
    const period = rawPeriod.includes('P') ? 'P.M.' : 'A.M.'

    return `${weekday} ${month}-${day}-${year} ${hour}:${minute} ${period} MDT`
  } catch {
    return String(dateStr)
  }
}
