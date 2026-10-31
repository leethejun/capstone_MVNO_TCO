// 즐겨찾기 식별자: 월간 재수집으로 plan_id가 바뀌므로 통신사·요금제명·망으로 구분한다.
export const guestFavoritesKey = 'alddle_favorites';

export function favoriteKey(plan) {
  return {
    telecom_name: plan?.telecom?.name || plan?.telecom_name || '알뜰폰',
    title: String(plan?.title || '').trim(),
    network_type: plan?.network_type || 'LTE',
    plan_id: plan?.plan_id ?? null,
  };
}

export function favoriteIdentity(item) {
  const key = item?.title ? favoriteKey(item) : item;
  return [key.telecom_name, key.title, String(key.network_type || 'LTE').toUpperCase()].join('|');
}

export function loadGuestFavorites(storage = globalThis.localStorage) {
  try {
    const parsed = JSON.parse(storage?.getItem(guestFavoritesKey) || '[]');
    return Array.isArray(parsed) ? parsed.filter((item) => item?.title && item?.telecom_name) : [];
  } catch {
    return [];
  }
}

export function saveGuestFavorites(items, storage = globalThis.localStorage) {
  try { storage?.setItem(guestFavoritesKey, JSON.stringify(items)); }
  catch { /* 사생활 보호 모드 등 저장 불가 시 현재 화면에서만 유지 */ }
}

export function toggleGuestFavorite(items, plan) {
  const identity = favoriteIdentity(favoriteKey(plan));
  return items.some((item) => favoriteIdentity(item) === identity)
    ? items.filter((item) => favoriteIdentity(item) !== identity)
    : [favoriteKey(plan), ...items];
}

// 즐겨찾기 탭 정렬: TCO 계산 가능한 상품을 총비용 순으로, 나머지는 저장 순서대로 뒤에 둔다.
export function sortFavoritesByTco(items) {
  return [...items].sort((a, b) => {
    if (a.plan && b.plan) return a.plan.tco - b.plan.tco;
    return (a.plan ? 0 : 1) - (b.plan ? 0 : 1);
  });
}
