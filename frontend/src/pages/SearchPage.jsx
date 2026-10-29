import React, { useState } from 'react';
import { Search, SlidersHorizontal, Wifi, Phone, ChevronRight } from 'lucide-react';
import { searchPlans } from '../api';
import { useI18n } from '../i18n/hooks';

const money = value => Number(value || 0).toLocaleString('ko-KR');
const defaultFilters = { carrier:'', min_price:0, max_price:100000, network_type:'', min_data_gb:0, min_daily_data_gb:0, min_qos_speed_mbps:0, min_voice_minutes:0, min_sms_count:0, unlimited_voice:false, unlimited_sms:false, min_discount_months:0, permanent_discount:false };
const options = (items, t) => items.map(([value,label]) => <option key={value} value={value}>{t(label)}</option>);
const selectClass = 'w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm';

function PriceRange({ min, max, onChange, t }) {
  const low = Math.max(0,Math.min(100000,Number(min)||0));
  const high = Math.max(low,Math.min(100000,Number(max)||0));
  return <div className="space-y-3">
    <div className="flex justify-between text-sm font-semibold"><span>{t("할인 월 요금")}</span><span className="text-indigo-600">{money(low)} ~ {money(high)}{t('원')}</span></div>
    <div className="relative h-10 flex items-center" aria-label={t("월 요금 범위")}>
      <div className="absolute inset-x-1 h-1.5 rounded-full bg-slate-200" />
      <div className="absolute h-1.5 rounded-full bg-indigo-500" style={{left:`${low/1000}%`,right:`${100-high/1000}%`}} />
      <input aria-label={t("최소 월 요금 슬라이더")} type="range" min="0" max="100000" step="500" value={low} onChange={e=>onChange(Math.min(Number(e.target.value),high),high)} className="price-range-input absolute w-full" style={{zIndex:low>90000?5:3}} />
      <input aria-label={t("최대 월 요금 슬라이더")} type="range" min="0" max="100000" step="500" value={high} onChange={e=>onChange(low,Math.max(Number(e.target.value),low))} className="price-range-input absolute w-full" style={{zIndex:4}} />
    </div>
    <div className="grid grid-cols-2 gap-3">
      <label className="text-xs text-slate-500">{t("최소 금액 (원)")}<input className={selectClass} type="number" min="0" max="100000" value={min} onChange={e=>onChange(Math.max(0,Math.min(100000,Number(e.target.value)||0)),high)} /></label>
      <label className="text-xs text-slate-500">{t("최대 금액 (원)")}<input className={selectClass} type="number" min="0" max="100000" value={max} onChange={e=>onChange(low,Math.max(low,Math.min(100000,Number(e.target.value)||0)))} /></label>
    </div>
  </div>;
}

export default function SearchPage({ onSelectPlanForSubscribe }) {
  const { t, locale } = useI18n();
  const [mode,setMode]=useState('name');
  const [keyword,setKeyword]=useState('');
  const [filters,setFilters]=useState(defaultFilters);
  const [targetMonths,setTargetMonths]=useState(12);
  const [sort,setSort]=useState('tco');
  const [plans,setPlans]=useState([]);
  const [searched,setSearched]=useState(false);
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState('');
  const [page,setPage]=useState(0);
  const [more,setMore]=useState(false);
  const set=(field,value)=>setFilters(prev=>({...prev,[field]:value}));
  const changeMode=value=>{setMode(value);setSearched(false);setPlans([]);setPage(0);};
  const run=async (nextPage=0)=>{
    setLoading(true);setError('');
    try {
      const params=mode==='name'?{mode,keyword:keyword.trim(),target_months:targetMonths,offset:nextPage*30,limit:30}:{mode,...filters,target_months:targetMonths,sort,offset:nextPage*30,limit:30};
      const data=await searchPlans(params);
      setPlans(prev=>nextPage===0?data:[...prev,...data]);
      setMore(data.length===30);setPage(nextPage);setSearched(true);
    }catch(e){setError(e.message);if(nextPage===0)setPlans([]);}
    finally{setLoading(false);}
  };
  const field=(title,key,choices)=> <label className="block text-xs font-medium text-slate-600">{t(title)}<select className={`${selectClass} mt-1`} value={filters[key]} onChange={e=>set(key,Number.isNaN(Number(e.target.value))?e.target.value:Number(e.target.value))}>{options(choices,t)}</select></label>;
  return <div className="px-4 pt-4 pb-24 space-y-4 max-w-md mx-auto">
    <h2 className="text-lg font-black text-slate-900">{t("요금제 검색")}</h2>
    <div className="flex bg-slate-200 rounded-xl p-1 gap-1">{[['name','요금제명 검색'],['conditions','조건 검색']].map(([id,label])=><button key={id} onClick={()=>changeMode(id)} className={`flex-1 py-2.5 text-sm rounded-lg font-bold ${mode===id?'bg-white text-indigo-700 shadow-sm':'text-slate-500'}`}>{t(label)}</button>)}</div>
    <div className="bg-white border border-slate-200 rounded-2xl p-4 space-y-4">
      {mode==='name'?<><label className="block text-sm font-semibold">{t("찾으려는 요금제명")}<input className={`${selectClass} mt-2`} placeholder={t("예: 모두다 맘껏, 11GB")} value={keyword} onChange={e=>setKeyword(e.target.value)} onKeyDown={e=>e.key==='Enter'&&keyword.trim()&&run(0)} /></label><p className="text-xs text-slate-500">{t("이름에 검색어가 포함된 상품을 찾습니다. 선택하면 상세정보가 열립니다.")}</p></>:<>
        <label className="block text-sm font-semibold">{t("통신사명 (선택)")}<input className={`${selectClass} mt-2`} placeholder={t("입력하지 않으면 전체 통신사")} value={filters.carrier} onChange={e=>set('carrier',e.target.value)} /></label>
        <PriceRange t={t} min={filters.min_price} max={filters.max_price} onChange={(a,b)=>setFilters(p=>({...p,min_price:a,max_price:b}))}/>
        <div className="grid grid-cols-2 gap-3">
          {field('LTE / 5G','network_type',[['','전체'],['LTE','LTE'],['5G','5G']])}
          {field('기본 데이터','min_data_gb',[[0,'전체'],[1,'1GB 이상'],[5,'5GB 이상'],[10,'10GB 이상'],[20,'20GB 이상'],[100,'100GB 이상']])}
          {field('일일 추가 데이터','min_daily_data_gb',[[0,'전체'],[1,'1GB 이상'],[2,'2GB 이상'],[5,'5GB 이상']])}
          {field('소진 후 QoS','min_qos_speed_mbps',[[0,'전체'],[1,'1Mbps 이상'],[3,'3Mbps 이상'],[5,'5Mbps 이상'],[10,'10Mbps 이상']])}
          {field('통화','min_voice_minutes',[[0,'전체'],[100,'100분 이상'],[300,'300분 이상']])}
          {field('문자','min_sms_count',[[0,'전체'],[100,'100건 이상'],[300,'300건 이상']])}
          {field('할인 기간','min_discount_months',[[0,'전체'],[3,'3개월 이상'],[6,'6개월 이상'],[7,'7개월 이상'],[12,'12개월 이상']])}
        </div>
        <div className="flex gap-4 text-sm"><label className="flex gap-1.5 items-center"><input type="checkbox" checked={filters.unlimited_voice} onChange={e=>set('unlimited_voice',e.target.checked)}/>{t("통화 무제한")}</label><label className="flex gap-1.5 items-center"><input type="checkbox" checked={filters.unlimited_sms} onChange={e=>set('unlimited_sms',e.target.checked)}/>{t("문자 무제한")}</label></div>
        <label className="flex gap-2 text-sm items-center"><input type="checkbox" checked={filters.permanent_discount} onChange={e=>set('permanent_discount',e.target.checked)}/>{t("기간 제한 없는 할인만")}</label>
        <button className="text-xs text-slate-500 underline" onClick={()=>setFilters(defaultFilters)}>{t("조건 초기화")}</button>
      </>}
      <button disabled={loading||(mode==='name'&&!keyword.trim())} onClick={()=>run(0)} className="w-full bg-indigo-600 text-white py-3 rounded-xl font-bold disabled:opacity-50 flex gap-2 justify-center items-center"><Search size={17}/>{loading?t('검색 중...'):t('검색하기')}</button>
    </div>
    {error&&<p role="alert" className="text-sm text-rose-600">{error}</p>}
    {searched&&<section className="space-y-3"><div className="flex items-center justify-between"><h3 className="font-bold text-sm">{mode==='name'?t('요금제명 검색 결과'):t('조건별 요금제 순위')}</h3>{mode==='conditions'&&<select className="text-xs border rounded-lg p-2" value={sort} onChange={e=>setSort(e.target.value)}><option value="tco">{t("TCO 낮은 순")}</option><option value="price">{t("월 요금 낮은 순")}</option></select>}</div>
      <label className="flex items-center gap-2 text-xs text-slate-500">{t("이용 기간")}<select className="border rounded-lg p-1" value={targetMonths} onChange={e=>setTargetMonths(Number(e.target.value))}>{[6,12,24,36,48].map(n=><option key={n} value={n}>{n}{t("개월")}</option>)}</select><button className="underline text-indigo-600" onClick={()=>run(0)}>{t("적용")}</button></label>
      {!plans.length&&!loading&&<div className="bg-white rounded-2xl p-8 text-center text-sm text-slate-500">{t("일치하는 요금제가 없습니다.")}</div>}
      {plans.map((p,i)=><button key={`${p.plan_id}-${i}`} onClick={()=>onSelectPlanForSubscribe({...p,telecom_name:p.telecom?.name||p.telecom_name,target_months:targetMonths})} className="w-full text-left bg-white border border-slate-200 rounded-2xl p-4 space-y-2 shadow-sm">
        <div className="flex gap-2 items-center"><span className="bg-indigo-50 text-indigo-700 rounded-lg px-2 py-1 text-xs font-bold">{mode==='conditions'?`${i+1}${t('위')}`:t('검색 결과')}</span><span className="text-xs text-slate-500">{p.telecom?.name||p.telecom_name||t('통신사 미확인')}</span></div>
        <h4 className="text-sm font-bold text-slate-900">{p.title}</h4>
        <div className="text-xs text-slate-500 flex flex-wrap gap-3"><span className="flex gap-1 items-center"><Wifi size={12}/>{p.base_data_gb||0}GB{Number(p.daily_data_gb)>0?` + ${t('일')}${p.daily_data_gb}GB`:''}</span><span className="flex gap-1 items-center"><Phone size={12}/>{p.voice_minutes===-1?t('통화 무제한'):`${p.voice_minutes||0}${t('분')}`}</span>{Number(p.qos_speed_mbps)>0&&<span>QoS {p.qos_speed_mbps}Mbps</span>}</div>
        <div className="border-t pt-2 flex justify-between items-end"><div><span className="text-[11px] text-slate-400">{t("할인 월 요금")}</span><div className="font-black">{money(p.discount_price)}{t('원')}</div><div className="text-[11px] text-slate-500">{t("할인 종료 후")} {p.normal_price==null?t('미확인'):`${money(p.normal_price)}${t('원')}`}</div></div><div className="text-right"><span className="text-[11px] text-indigo-600">{targetMonths}{t("개월")} TCO</span><div className="font-black text-indigo-600">{money(p.tco)}{t('원')}</div><span className="text-xs text-indigo-500 flex items-center justify-end">상세 보기 <ChevronRight size={13}/></span></div></div>
      </button>)}
      {more&&<button disabled={loading} className="w-full bg-white border rounded-xl py-3 text-sm font-semibold text-indigo-600" onClick={()=>run(page+1)}>{loading?t('불러오는 중...'):t('더 보기')}</button>}
    </section>}
  </div>;
}
