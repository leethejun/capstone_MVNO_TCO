import { authHeaders } from './firebase';
const API_BASE = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");

export async function fetchPlansRank({
  targetMonths = 12,
  minDataGb = 0,
  minDailyDataGb = 0,
  minQosSpeedMbps = 0,
  isUnlimitedData = false,
  unlimitedVoice = false,
  unlimitedSms = false,
  networkType = null,
  limit = 30
} = {}) {
  const params = new URLSearchParams();
  params.append("target_months", targetMonths);
  if (minDataGb > 0) params.append("min_data_gb", minDataGb);
  if (minDailyDataGb > 0) params.append("min_daily_data_gb", minDailyDataGb);
  if (minQosSpeedMbps > 0) params.append("min_qos_speed_mbps", minQosSpeedMbps);
  if (isUnlimitedData) params.append("is_unlimited_data", "true");
  if (unlimitedVoice) params.append("unlimited_voice", "true");
  if (unlimitedSms) params.append("unlimited_sms", "true");
  if (networkType) params.append("network_type", networkType);
  params.append("limit", limit);

  const res = await fetch(`${API_BASE}/plans/rank?${params.toString()}`);
  if (!res.ok) throw new Error("요금제 랭킹 조회 실패");
  return res.json();
}

export async function getMe() {
  const res = await fetch(`${API_BASE}/users/me`, { headers: await authHeaders() });
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error(error.detail || '계정 연결 실패');
  }
  return res.json();
}
export async function updatePreferences(defaultTargetMonths) {
  const res = await fetch(`${API_BASE}/users/me`, { method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...await authHeaders() },
    body: JSON.stringify({ default_target_months: defaultTargetMonths }),
  });
  if (!res.ok) throw new Error('이용 주기 저장 실패');
  return res.json();
}

export async function getUserSubscriptions(userId) {
  const res = await fetch(`${API_BASE}/subscriptions/user/${userId}`, { headers: await authHeaders() });
  if (!res.ok) throw new Error("구독 요금제 조회 실패");
  return res.json();
}

export async function createSubscription({ userId, planId, startDate, targetMonths }) {
  const res = await fetch(`${API_BASE}/subscriptions`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...await authHeaders() },
    body: JSON.stringify({
      user_id: userId,
      plan_id: planId,
      start_date: startDate,
      target_months: targetMonths,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "요금제 개통 등록 실패");
  }
  return res.json();
}

export async function triggerNotificationBatch() {
  const res = await fetch(`${API_BASE}/notifications/trigger-batch`, {
    method: "POST", headers: await authHeaders(),
  });
  if (!res.ok) throw new Error("알림 배치 실행 실패");
  return res.json();
}

export async function getCrawlerStatus() {
  const res = await fetch(`${API_BASE}/crawler/status`);
  if (!res.ok) throw new Error("크롤러 상태 조회 실패");
  return res.json();
}

export async function deleteSubscription({ subscriptionId, userId }) {
  const params = new URLSearchParams({ user_id: userId });
  const res = await fetch(`${API_BASE}/subscriptions/${subscriptionId}?${params}`, { method: "DELETE", headers: await authHeaders() });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "요금제 삭제 실패");
  }
}
