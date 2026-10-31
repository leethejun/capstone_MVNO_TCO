const TIE_BREAK_LABELS = {
  unlimited: '데이터 무제한(QoS)',
  qos: '소진 후 속도',
  daily_data: '일일 데이터',
  base_data: '기본 데이터',
};

// 서버가 보낸 근거 code와 계산 값을 화면 문구로 바꾼다. 알 수 없는 code는 표시하지 않는다.
export function describeReason(reason, t, locale) {
  const p = reason?.params || {};
  const won = (value) => Number(value ?? 0).toLocaleString(locale === 'en' ? 'en-US' : 'ko-KR');
  switch (reason?.code) {
    case 'lowest_tco':
      return t('조건에 맞는 {{count}}개 요금제 중 {{months}}개월 총비용(TCO)이 가장 낮습니다.', { count: won(p.count), months: p.months });
    case 'rank_position':
      return p.gap_to_top > 0
        ? t('{{count}}개 중 {{rank}}위이며, 1위보다 {{gap}}원 더 듭니다.', { count: won(p.count), rank: p.rank, gap: won(p.gap_to_top) })
        : t('{{count}}개 중 {{rank}}위이며, 1위와 총비용이 같습니다.', { count: won(p.count), rank: p.rank });
    case 'lifetime_discount':
      return t('평생 할인 요금제라 이용 기간 내내 월 {{price}}원이 유지됩니다.', { price: won(p.price) });
    case 'discount_covers_period':
      return t('할인 기간이 {{months}}개월 이용 기간을 모두 포함해 요금 인상이 없습니다. (월 {{price}}원)', { months: p.months, price: won(p.price) });
    case 'price_increase':
      return t('{{after}}개월 동안 월 {{from}}원, 이후 {{normal}}개월은 정상가 월 {{to}}원이 적용됩니다.', { after: p.after_months, from: won(p.from_price), normal: p.normal_months, to: won(p.to_price) });
    case 'below_average':
      return t('비교한 {{count}}개 요금제 평균보다 {{saving}}원({{percent}}%) 저렴합니다.', { count: won(p.count), saving: won(p.saving), percent: p.percent });
    case 'cheaper_than_next':
      return t('바로 다음 순위 요금제보다 {{gap}}원 저렴합니다.', { gap: won(p.gap) });
    case 'tie_break':
      return t('다음 순위와 총비용이 같지만 {{criterion}} 조건이 더 좋아 앞에 배치되었습니다.', { criterion: t(TIE_BREAK_LABELS[p.criterion] || p.criterion) });
    case 'qos_tier':
      return p.speed > 0
        ? t('기본 데이터를 다 써도 {{speed}}Mbps 속도로 계속 사용할 수 있습니다.', { speed: p.speed })
        : t('매일 {{data}}GB 데이터가 추가로 제공됩니다.', { data: p.daily });
    case 'filters_matched': {
      const labels = [];
      if (p.min_qos_speed_mbps) labels.push(t('QoS {{speed}}Mbps 이상', { speed: p.min_qos_speed_mbps }));
      if (p.min_data_gb) labels.push(t('기본 데이터 {{data}}GB 이상', { data: p.min_data_gb }));
      if (p.min_daily_data_gb) labels.push(t('일일 데이터 {{data}}GB 이상', { data: p.min_daily_data_gb }));
      if (p.is_unlimited_data) labels.push(t('데이터 무제한'));
      if (p.unlimited_voice) labels.push(t('음성통화 무제한'));
      if (p.unlimited_sms) labels.push(t('문자 무제한'));
      if (p.network_type) labels.push(p.network_type);
      return labels.length ? t('선택한 조건을 충족합니다: {{conditions}}', { conditions: labels.join(', ') }) : null;
    }
    case 'tco_formula':
      return p.normal_months > 0
        ? t('계산식: {{dp}}원 × {{dm}}개월 + {{np}}원 × {{nm}}개월 = {{tco}}원', { dp: won(p.discount_price), dm: p.discount_months, np: won(p.normal_price), nm: p.normal_months, tco: won(p.tco) })
        : t('계산식: {{dp}}원 × {{dm}}개월 = {{tco}}원', { dp: won(p.discount_price), dm: p.discount_months, tco: won(p.tco) });
    case 'similar_lowest_tco':
      return t('현재 요금제와 비슷한 데이터·QoS 조건의 요금제 중 {{months}}개월 총비용이 가장 낮습니다.', { months: p.months });
    case 'fallback_lowest_tco':
      return t('비슷한 조건의 요금제가 없어 전체 요금제 중 {{months}}개월 총비용이 가장 낮은 상품을 추천했습니다.', { months: p.months });
    case 'keeps_data':
      return t('기본 데이터 {{recommended}}GB로 현재 {{current}}GB의 80% 이상을 제공합니다.', { recommended: p.recommended_gb, current: p.current_gb });
    case 'keeps_qos':
      return t('소진 후 속도 {{recommended}}Mbps로 현재 {{current}}Mbps 이상입니다.', { recommended: p.recommended_speed, current: p.current_speed });
    case 'saving_vs_current':
      return p.saving > 0
        ? t('지금 요금제를 {{months}}개월 더 쓰면 {{current}}원, 환승하면 {{recommended}}원으로 {{saving}}원을 아낄 수 있습니다.', { months: p.months, current: won(p.current_cost), recommended: won(p.recommended_cost), saving: won(p.saving) })
        : t('환승 시 {{months}}개월 총비용은 {{recommended}}원이며, 현재 요금제 유지 시 {{current}}원입니다.', { months: p.months, current: won(p.current_cost), recommended: won(p.recommended_cost) });
    default:
      return null;
  }
}
