/**
 * Parcel identifiers: TN-<governorate>-<delegation>-<6 characters>
 * e.g. TN-BZ-MTR-7K4Q2X
 * The last part uses Crockford base32 (no I, L, O, U) so it is easy to read
 * aloud or copy by hand without confusing 0/O or 1/I.
 */
const GOVERNORATE_CODES: Record<string, string> = {
  tunis: 'TU', ariana: 'AR', 'ben arous': 'BA', manouba: 'MN', nabeul: 'NB', zaghouan: 'ZG',
  bizerte: 'BZ', beja: 'BJ', jendouba: 'JD', 'le kef': 'KF', kef: 'KF', siliana: 'SL',
  sousse: 'SS', monastir: 'MS', mahdia: 'MH', sfax: 'SF', kairouan: 'KR', kasserine: 'KS',
  'sidi bouzid': 'SB', gabes: 'GB', medenine: 'MD', tataouine: 'TT', gafsa: 'GF',
  tozeur: 'TZ', kebili: 'KB',
};

const ALPHABET = '0123456789ABCDEFGHJKMNPQRSTVWXYZ';

const stripAccents = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '');

export function governorateCode(governorate: string): string {
  const key = stripAccents(governorate).toLowerCase().trim();
  return GOVERNORATE_CODES[key] ?? stripAccents(governorate).replace(/[^A-Za-z]/g, '').slice(0, 2).toUpperCase().padEnd(2, 'X');
}

/** First letter + next two consonants: Mateur → MTR, Regueb → RGB. */
export function delegationCode(delegation: string): string {
  const letters = stripAccents(delegation).toUpperCase().replace(/[^A-Z]/g, '');
  if (!letters) return 'XXX';
  const consonants = letters.slice(1).replace(/[AEIOUY]/g, '');
  return (letters[0] + consonants + letters.slice(1)).slice(0, 3).padEnd(3, 'X');
}

function randomSuffix(length = 6): string {
  const bytes = new Uint8Array(length);
  if (typeof crypto !== 'undefined' && crypto.getRandomValues) crypto.getRandomValues(bytes);
  else for (let i = 0; i < length; i++) bytes[i] = Math.floor(Math.random() * 256);
  return Array.from(bytes, (b) => ALPHABET[b % ALPHABET.length]).join('');
}

/** Generates an ID that is not already in `taken`. */
export function generateParcelId(governorate: string, delegation: string, taken: Set<string>): string {
  const prefix = `TN-${governorateCode(governorate)}-${delegationCode(delegation)}-`;
  for (let attempt = 0; attempt < 50; attempt++) {
    const id = prefix + randomSuffix();
    if (!taken.has(id)) return id;
  }
  return prefix + randomSuffix(8);
}
