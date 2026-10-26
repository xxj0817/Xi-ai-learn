const BASE64_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'

function toUtf8Bytes(input: string): number[] {
  const bytes: number[] = []
  for (let index = 0; index < input.length; index += 1) {
    const code = input.charCodeAt(index)
    if (code < 0x80) {
      bytes.push(code)
    } else if (code < 0x800) {
      bytes.push(0xc0 | (code >> 6), 0x80 | (code & 0x3f))
    } else {
      bytes.push(0xe0 | (code >> 12), 0x80 | ((code >> 6) & 0x3f), 0x80 | (code & 0x3f))
    }
  }
  return bytes
}

export function toBase64(input: string): string {
  const bytes = toUtf8Bytes(input)
  let output = ''

  for (let index = 0; index < bytes.length; index += 3) {
    const first = bytes[index]
    const second = bytes[index + 1]
    const third = bytes[index + 2]

    output += BASE64_CHARS[first >> 2]
    output += BASE64_CHARS[((first & 0x03) << 4) | (second === undefined ? 0 : second >> 4)]
    output += second === undefined ? '=' : BASE64_CHARS[((second & 0x0f) << 2) | (third === undefined ? 0 : third >> 6)]
    output += third === undefined ? '=' : BASE64_CHARS[third & 0x3f]
  }

  return output
}

export function svgToDataUri(svg: string): string {
  return `data:image/svg+xml;base64,${toBase64(svg)}`
}

export function ringDataUri(percent: number, color: string, size: number, stroke: number): string {
  const safePercent = Math.min(100, Math.max(0, percent))
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference * (1 - safePercent / 100)
  const center = size / 2

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
<circle cx="${center}" cy="${center}" r="${radius}" fill="none" stroke="#ece7de" stroke-width="${stroke}"/>
<circle cx="${center}" cy="${center}" r="${radius}" fill="none" stroke="${color}" stroke-width="${stroke}" stroke-linecap="round" stroke-dasharray="${circumference}" stroke-dashoffset="${offset}" transform="rotate(-90 ${center} ${center})"/>
</svg>`

  return svgToDataUri(svg)
}
