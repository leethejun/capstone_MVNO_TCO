// 가입일 기준으로 지금까지 지난 '완전한' 개월 수. 할인 기간 중 이미 사용한 부분을 빼기 위해 쓴다.
export function elapsedWholeMonths(startDate, today = new Date()) {
  if (!startDate) return 0;
  const start = new Date(`${String(startDate).slice(0, 10)}T00:00:00`);
  if (Number.isNaN(start.getTime())) return 0;
  let months = (today.getFullYear() - start.getFullYear()) * 12 + today.getMonth() - start.getMonth();
  if (today.getDate() < start.getDate()) months--;
  return Math.max(0, months);
}

// 앞으로 targetMonths 동안의 예상 총비용.
// elapsedMonths는 이미 지난 개월 수로, 남은 할인 기간만 할인가로 계산하고 나머지는 정상가로 계산한다.
export function calculatePlanTco(plan, targetMonths, elapsedMonths = 0) {
  if (!plan) return null;

  const months = Number(targetMonths);
  const elapsed = Number(elapsedMonths);
  const discountMonths = Number(plan.discount_months);
  const discountPrice = Number(plan.discount_price);
  const normalPrice = Number(plan.normal_price);

  // 유효하지 않은 가격이나 기간은 계산하지 않는다.
  if (
    !Number.isFinite(months) ||
    months <= 0 ||
    !Number.isFinite(elapsed) ||
    elapsed < 0 ||
    !Number.isFinite(discountMonths) ||
    discountMonths < -1 ||
    !Number.isFinite(discountPrice) ||
    !Number.isFinite(normalPrice) ||
    discountPrice < 0 ||
    normalPrice <= 0 ||
    normalPrice < discountPrice
  ) {
    return null;
  }

  // -1은 평생 할인으로 처리한다.
  if (discountMonths === -1) {
    return discountPrice * months;
  }

  // 이미 지난 할인 기간을 빼고, 남은 할인 기간과 정상가 적용 기간을 분리한다.
  const remainingDiscountMonths = Math.max(0, discountMonths - elapsed);
  const discountedMonths = Math.min(months, remainingDiscountMonths);
  const normalMonths = months - discountedMonths;

  return discountPrice * discountedMonths + normalPrice * normalMonths;
}

// 현재 구독을 유지할 때와 추천 요금제로 새로 개통할 때의 예상 비용 비교.
export function calculateSubscriptionSavings(sub, recommendedPlan, today = new Date()) {
  const currentTco = calculatePlanTco(sub?.plan, sub?.target_months, elapsedWholeMonths(sub?.start_date, today));
  // 추천 요금제는 새로 개통하므로 할인 기간을 처음부터 적용한다.
  const recommendedTco = calculatePlanTco(recommendedPlan, sub?.target_months);
  if (currentTco === null || recommendedTco === null) return null;
  return { currentTco, recommendedTco, savings: currentTco - recommendedTco };
}
