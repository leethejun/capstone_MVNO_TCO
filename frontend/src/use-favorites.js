import { useCallback, useEffect, useMemo, useState } from 'react';
import { addFavorite, fetchFavorites, removeFavorite, resolveFavorites } from './api';
import {
  favoriteIdentity, favoriteKey, loadGuestFavorites, saveGuestFavorites, sortFavoritesByTco, toggleGuestFavorite,
} from './favorites';

// 로그인 시 브라우저에 저장된 즐겨찾기를 계정으로 옮긴다. 옮기지 못한 항목은 브라우저에 남긴다.
async function migrateGuestFavorites(targetMonths) {
  const keys = loadGuestFavorites();
  if (!keys.length) return;
  // 재수집으로 바뀐 plan_id를 현재 상품으로 먼저 연결한다.
  const resolved = await resolveFavorites(keys, targetMonths);
  const remaining = [];
  for (const [index, item] of resolved.entries()) {
    try {
      if (!item.plan_id || item.status === 'unavailable') throw new Error('unavailable');
      await addFavorite(item.plan_id, targetMonths);
    } catch {
      remaining.push(keys[index]);
    }
  }
  saveGuestFavorites(remaining);
}

export function useFavorites({ currentUser, targetMonths }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const reload = useCallback(async () => {
    setLoading(true); setError('');
    try {
      if (currentUser) {
        await migrateGuestFavorites(targetMonths);
        setItems(await fetchFavorites(targetMonths));
      } else {
        const keys = loadGuestFavorites();
        setItems(keys.length ? await resolveFavorites(keys, targetMonths) : []);
      }
    } catch (err) {
      setError(err.message || '즐겨찾기 조회 실패');
    } finally {
      setLoading(false);
    }
  }, [currentUser, targetMonths]);

  useEffect(() => { reload(); }, [reload]);

  const identities = useMemo(() => new Set(items.map(favoriteIdentity)), [items]);
  const isFavorite = useCallback((plan) => identities.has(favoriteIdentity(favoriteKey(plan))), [identities]);

  const toggle = useCallback(async (plan) => {
    setError('');
    const identity = favoriteIdentity(favoriteKey(plan));
    try {
      if (!currentUser) {
        saveGuestFavorites(toggleGuestFavorite(loadGuestFavorites(), plan));
      } else {
        const existing = items.find((item) => favoriteIdentity(item) === identity);
        if (existing?.favorite_id) await removeFavorite(existing.favorite_id);
        else await addFavorite(plan.plan_id, targetMonths);
      }
      await reload();
    } catch (err) {
      setError(err.message || '즐겨찾기 저장 실패');
    }
  }, [currentUser, items, reload, targetMonths]);

  const sorted = useMemo(() => sortFavoritesByTco(items), [items]);
  return { items: sorted, loading, error, isFavorite, toggle, reload };
}
