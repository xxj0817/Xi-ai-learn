export type IconName =
  | 'coin'
  | 'checkCircle'
  | 'closeCircle'
  | 'checkBadge'
  | 'checkBadgeOrange'
  | 'closeBadge'
  | 'clock'
  | 'warning'
  | 'share'
  | 'home'
  | 'book'
  | 'user'
  | 'arrowRight'
  | 'arrowLeft'
  | 'close'
  | 'star'
  | 'trendDown'

const STROKE_ICONS: Record<string, string> = {
  checkCircle: '<circle cx="12" cy="12" r="9"/><path d="M8 12L11 15L16 9"/>',
  closeCircle: '<circle cx="12" cy="12" r="9"/><path d="M9 9L15 15"/><path d="M15 9L9 15"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7V12L15 14"/>',
  warning: '<path d="M12 3L21 19H3Z"/><path d="M12 9V13"/><circle cx="12" cy="16.5" r="0.6"/>',
  share:
    '<circle cx="18" cy="5" r="2"/><circle cx="6" cy="12" r="2"/><circle cx="18" cy="19" r="2"/><path d="M8 11L16 6"/><path d="M8 13L16 18"/>',
  home: '<path d="M3 11L12 4L21 11"/><path d="M6 10V20H18V10"/>',
  book: '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M8 9H16"/><path d="M8 13H16"/>',
  user: '<circle cx="12" cy="8" r="3"/><path d="M5 20C5 16 8 14 12 14C16 14 19 16 19 20"/>',
  arrowRight: '<path d="M5 12H19"/><path d="M13 6L19 12L13 18"/>',
  arrowLeft: '<path d="M19 12H5"/><path d="M11 18L5 12L11 6"/>',
  close: '<path d="M6 6L18 18"/><path d="M18 6L6 18"/>',
  star: '<path d="M12 3L14.6 8.2L20 9L16 13L17 19L12 16L7 19L8 13L4 9L9.4 8.2Z"/>',
  trendDown: '<path d="M4 7L10 13L14 9L20 15"/><path d="M20 9V15H14"/>'
}

const FILLED_ICONS: Record<string, string> = {
  coin: `<circle cx="16" cy="16" r="15" fill="#ffd36e" stroke="#ffb124" stroke-width="2"/>
<path d="M16 9L18 14L23 14L19 17L21 22L16 19L11 22L13 17L9 14L14 14Z" fill="#ff8a2b"/>`,
  checkBadge: `<circle cx="12" cy="12" r="11" fill="#2fb778"/>
<path d="M6.8 12.5L10.2 16L17.2 8.7" fill="none" stroke="#ffffff" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"/>`,
  checkBadgeOrange: `<circle cx="12" cy="12" r="11" fill="#ff7a2f"/>
<path d="M6.8 12.5L10.2 16L17.2 8.7" fill="none" stroke="#ffffff" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"/>`,
  closeBadge: `<circle cx="12" cy="12" r="11" fill="#ff6f5d"/>
<path d="M8.4 8.4L15.6 15.6" fill="none" stroke="#ffffff" stroke-width="2.8" stroke-linecap="round"/>
<path d="M15.6 8.4L8.4 15.6" fill="none" stroke="#ffffff" stroke-width="2.8" stroke-linecap="round"/>`
}

export function iconSvg(name: IconName, color = '#cb6326'): string {
  const filled = FILLED_ICONS[name]
  if (filled) {
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">${filled}</svg>`
  }

  const body = STROKE_ICONS[name] ?? ''
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${body}</svg>`
}

export function mascotSvg(): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<circle cx="32" cy="32" r="28" fill="#fff1e2" stroke="#ffd4b4" stroke-width="2"/>
<circle cx="24" cy="28" r="4" fill="#2f324a"/>
<circle cx="40" cy="28" r="4" fill="#2f324a"/>
<path d="M23 40C26 44 38 44 41 40" stroke="#2f324a" stroke-width="4" fill="none" stroke-linecap="round"/>
<path d="M19 20L24 16" stroke="#ff9a56" stroke-width="3" stroke-linecap="round"/>
<path d="M45 20L40 16" stroke="#ff9a56" stroke-width="3" stroke-linecap="round"/>
</svg>`
}

export function levelAvatarSvg(index: number): string {
  if (index % 2 === 1) {
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40">
<circle cx="20" cy="20" r="18" fill="#5eb5ff"/>
<path d="M10 28L16 18L21 28Z" fill="#ff7a5f"/>
<path d="M20 28L25 14L31 28Z" fill="#f7db63"/>
</svg>`
  }

  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40">
<circle cx="20" cy="20" r="18" fill="#8a7bff"/>
<path d="M10 23L20 11L30 23V30H10Z" fill="#ffd36e"/>
</svg>`
}
