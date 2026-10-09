import React, { useState, useEffect } from 'react';
import { fetchPlansRank } from '../api';
import { Filter, Zap, Wifi, Phone, ChevronRight } from 'lucide-react';

export default function RankPage({ onSelectPlanForSubscribe }) {
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [targetMonths, setTargetMonths] = useState(12);
  const [minQosSpeed, setMinQosSpeed] = useState(0);
  const [unlimitedSms, setUnlimitedSms] = useState(false);
  const [unlimitedVoice, setUnlimitedVoice] = useState(false);
  const [networkType, setNetworkType] = useState('');
  const [showFilters, setShowFilters] = useState(false);

  const loadRank = async () => {
    setLoading(true);
    try {
      const data = await fetchPlansRank({
        targetMonths,
        minQosSpeedMbps: minQosSpeed,
        unlimitedSms,
        unlimitedVoice,
        networkType: networkType || null,
        limit: 30,
      });
      setPlans(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('요금제 랭킹 로드 실패:', err);
      setPlans([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRank();
  }, [targetMonths, minQosSpeed, unlimitedSms, unlimitedVoice, networkType]);

  const qosPresets = [
    { label: '전체 QoS', value: 0 },
    { label: '1Mbps 실속', value: 1.0 },
    { label: '3Mbps 고속', value: 3.0 },
    { label: '5Mbps 초고속', value: 5.0 },
  ];

  return (
    <div className="pb-24 pt-2 px-4 space-y-4 max-w-md mx-auto">
      {/* 상단 타겟 이용 기간 선택 바 */}
      <div className="bg-white p-3.5 rounded-2xl border border-slate-200 shadow-xs">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
            <Zap className="w-3.5 h-3.5 text-indigo-600" />
            환승 이용 주기 (TCO 기준)
          </span>
          <span className="text-[11px] font-semibold text-indigo-600">{targetMonths}개월 총비용 최적화</span>
        </div>
        <select
          aria-label="환승 이용 주기"
          value={targetMonths}
          onChange={(e) => setTargetMonths(Number(e.target.value))}
          className="w-full py-2 px-3 text-xs rounded-xl border border-slate-200 bg-slate-50 text-slate-700 focus:border-indigo-500"
        >
          {[6, 12, 24, 36, 48].map((m) => <option key={m} value={m}>{m}개월</option>)}
        </select>
      </div>

      {/* QoS 무제한 필터 칩 */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold text-slate-700">QoS 속도제어 무제한 선택</span>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="text-[11px] text-slate-500 flex items-center gap-1 hover:text-indigo-600 font-medium"
          >
            <Filter className="w-3 h-3" />
            {showFilters ? '필터 접기' : '상세 필터'}
          </button>
        </div>

        <div className="flex gap-1.5 overflow-x-auto no-scrollbar pb-1">
          {qosPresets.map((preset) => (
            <button
              key={preset.value}
              onClick={() => setMinQosSpeed(preset.value)}
              className={`whitespace-nowrap px-3 py-1.5 rounded-full text-xs font-medium border transition shrink-0 ${
                minQosSpeed === preset.value
                  ? 'bg-indigo-50 border-indigo-500 text-indigo-700 font-bold shadow-xs'
                  : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
              }`}
            >
              {preset.label}
            </button>
          ))}
        </div>

        {/* 상세 필터 */}
        {showFilters && (
          <div className="p-3 bg-white rounded-2xl border border-slate-200 shadow-xs space-y-2.5 animate-in fade-in duration-200">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-600 font-medium">문자 무제한</span>
              <button
                role="switch"
                aria-label="문자 무제한"
                aria-checked={unlimitedSms}
                onClick={() => setUnlimitedSms(!unlimitedSms)}
                className={`w-9 h-5 rounded-full transition relative ${unlimitedSms ? 'bg-indigo-600' : 'bg-slate-200'}`}
              >
                <div className={`w-4 h-4 rounded-full bg-white transition absolute top-0.5 ${unlimitedSms ? 'left-4.5' : 'left-0.5'}`} />
              </button>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-600 font-medium">음성통화 무제한</span>
              <button
                onClick={() => setUnlimitedVoice(!unlimitedVoice)}
                className={`w-9 h-5 rounded-full transition relative ${unlimitedVoice ? 'bg-indigo-600' : 'bg-slate-200'}`}
              >
                <div className={`w-4 h-4 rounded-full bg-white transition absolute top-0.5 ${unlimitedVoice ? 'left-4.5' : 'left-0.5'}`} />
              </button>
            </div>

            <div className="flex items-center justify-between pt-1">
              <span className="text-xs text-slate-600 font-medium">통신망 규격</span>
              <div className="flex gap-1">
                {['', 'LTE', '5G'].map((type) => (
                  <button
                    key={type}
                    onClick={() => setNetworkType(type)}
                    className={`px-2.5 py-1 text-[11px] rounded-lg border font-medium ${
                      networkType === type ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-slate-50 text-slate-600 border-slate-200'
                    }`}
                  >
                    {type || '전체'}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 랭킹 결과 리스트 */}
      <div className="space-y-3">
        <div className="flex justify-between items-center px-1">
          <span className="text-xs font-bold text-slate-700">
            TCO 최저가 랭킹 <span className="text-indigo-600">({plans.length}건)</span>
          </span>
          <span className="text-[10px] text-slate-400">조건: TCO 순 정렬</span>
        </div>

        {loading ? (
          <div className="py-16 text-center text-slate-400 text-xs">
            <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
            TCO 최적 요금제 계산 중...
          </div>
        ) : plans.length === 0 ? (
          <div className="py-12 bg-white rounded-2xl border border-slate-200 text-center text-slate-500 text-xs p-6">
            선택한 조건에 맞는 요금제가 없습니다.<br />필터를 조정해보세요.
          </div>
        ) : (
          plans.map((p, idx) => {
            const rank = idx + 1;
            const telecomName = p.telecom?.name || p.telecom_name || '알뜰폰';
            const discountPrice = Number(p.discount_price || 0);
            const normalPrice = p.normal_price == null ? null : Number(p.normal_price);
            const tco = Number(p.tco ?? 0);
            const monthlyAvg = Number(p.monthly_avg_price ?? (targetMonths > 0 ? Math.round(tco / targetMonths) : discountPrice));

            return (
              <div
                key={p.plan_id || idx}
                onClick={() => onSelectPlanForSubscribe({ ...p, telecom_name: telecomName })}
                className="bg-white rounded-2xl border border-slate-200/80 p-4 shadow-xs hover:border-indigo-300 hover:shadow-md transition cursor-pointer relative group"
              >
                {/* 랭킹 뱃지 & 통신사 */}
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-xs font-black px-2 py-0.5 rounded-lg ${
                        rank === 1
                          ? 'bg-amber-400 text-amber-950 shadow-xs'
                          : rank === 2
                          ? 'bg-slate-200 text-slate-800'
                          : rank === 3
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-slate-100 text-slate-500'
                      }`}
                    >
                      {rank}위
                    </span>
                    <span className="text-xs font-semibold text-slate-600 truncate max-w-[120px]">{telecomName}</span>
                    <span className="text-[10px] px-1.5 py-0.2 rounded-sm bg-slate-100 text-slate-500 font-medium">
                      {p.network_type || 'LTE'}
                    </span>
                  </div>

                  {/* QoS 체감 무제한 등급 태그 */}
                  {p.qos_speed_mbps > 0 && (
                    <span className="text-[10px] font-semibold text-indigo-700 bg-indigo-50 border border-indigo-100 px-2 py-0.5 rounded-full flex items-center gap-1">
                      <Wifi className="w-2.5 h-2.5" />
                      {p.qos_speed_mbps}Mbps 무제한
                    </span>
                  )}
                </div>

                {/* 요금제 타이틀 */}
                <h4 className="font-bold text-sm text-slate-900 group-hover:text-indigo-600 transition line-clamp-1 mb-2">
                  {p.title}
                </h4>

                {/* 기본 스펙 */}
                <div className="flex items-center gap-3 text-xs text-slate-600 mb-3 bg-slate-50/80 p-2 rounded-xl">
                  <div className="flex items-center gap-1 font-semibold text-slate-800">
                    <Wifi className="w-3.5 h-3.5 text-indigo-500" />
                    <span>
                      {p.base_data_gb || 0}GB
                      {p.daily_data_gb > 0 && `+일${p.daily_data_gb}GB`}
                    </span>
                  </div>
                  <div className="text-slate-300">|</div>
                  <div className="flex items-center gap-1">
                    <Phone className="w-3.5 h-3.5 text-slate-400" />
                    <span>{p.voice_minutes === -1 ? '통화무제한' : `${p.voice_minutes || 0}분`}</span>
                  </div>
                  <div className="text-slate-300">|</div>
                  <div>문자 {p.sms_count === -1 ? '무제한' : `${p.sms_count || 0}건`}</div>
                </div>

                {/* 가격 정보: 월 할인가, 정상가, TCO 총비용 */}
                <div className="flex items-end justify-between pt-2 border-t border-slate-100">
                  <div>
                    <span className="text-[11px] text-slate-400">월 할인가 ({p.discount_months === -1 ? '평생 할인' : `${p.discount_months}개월간`})</span>
                    <div className="text-base font-black text-slate-900 leading-tight">
                      {discountPrice.toLocaleString()}
                      <span className="text-xs font-normal text-slate-500 ml-0.5">원/월</span>
                    </div>
                    <div className="mt-1 text-[11px] text-slate-500">
                      {p.discount_months > 0 ? '할인 종료 후 정상가' : '정상가'}{' '}
                      <span className="font-semibold text-slate-700">
                        {normalPrice == null ? '미확인' : `${normalPrice.toLocaleString()}원/월`}
                      </span>
                    </div>
                  </div>

                  <div className="text-right">
                    <span className="text-[11px] text-indigo-600 font-semibold">{targetMonths}개월 총비용 (TCO)</span>
                    <div className="text-base font-black text-indigo-600 leading-tight">
                      {tco.toLocaleString()}
                      <span className="text-xs font-normal text-slate-500 ml-0.5">원</span>
                    </div>
                    <span className="text-[10px] text-slate-400">
                      (월평균 {monthlyAvg.toLocaleString()}원)
                    </span>
                  </div>
                </div>

                {/* 개통 버튼 */}
                <div className="mt-2.5 pt-2 flex items-center justify-end text-[11px] text-indigo-600 font-semibold gap-0.5 opacity-90">
                  <span>이 요금제로 개통 등록</span>
                  <ChevronRight className="w-3 h-3" />
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
