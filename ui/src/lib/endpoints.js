export function endpointHref(ip, scheme = "http") {
  if (!ip) return null;
  if (/^https?:\/\//i.test(ip)) return ip;
  const host = ip.includes(":") ? `[${ip}]` : ip;
  return `${scheme}://${host}`;
}
