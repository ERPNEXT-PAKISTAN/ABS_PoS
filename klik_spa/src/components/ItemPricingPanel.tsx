import { useEffect, useState } from 'react';
import { useI18n } from '../hooks/useI18n';
import { extractErrorMessage } from '../utils/errorExtraction';
type Basis = 'Latest purchase' | 'Weighted average' | 'Manual';
interface Pricing {
  item_code: string; company: string; profile: string; currency: string; stock_uom: string; uom: string; factor: string;
  uoms: { uom: string; factor: string }[]; price_list: string; price_list_currency: string;
  purchases: { latest: { cost: string; invoice: string; date: string } | null; weighted_average: string | null; invoice_count: number; stock_quantity: string };
  policy: { markup_percentage: number; cost_basis: Basis; manual_cost: number } | null;
  current_price: { name: string; price_list_rate: number; currency: string } | null;
  can_save: boolean; blockers: string[]; tax: { inclusive: boolean; supported: boolean; rate: string | null; message: string };
  quote?: { unit_cost: string; net_selling_price: string; markup_amount: string; tax_amount: string; selling_price: string; gross_margin_percentage: string; snapshot: string } | null;
}
async function readPricing(method: string, params: Record<string, string>, signal?: AbortSignal) {
  const response = await fetch(`/api/method/klik_pos.api.item_pricing.${method}?${new URLSearchParams(params)}`, { credentials: 'include', signal });
  const result = await response.json();
  if (!response.ok || !result.message) throw new Error(extractErrorMessage(result, 'Unable to load pricing.'));
  return result.message as Pricing;
}
export default function ItemPricingPanel({ itemCode, initialUom }: { itemCode: string; initialUom?: string }) {
  const { isRTL } = useI18n();
  const t = (en: string, ar: string) => isRTL ? ar : en;
  const [data, setData] = useState<Pricing | null>(null);
  const [uom, setUom] = useState('');
  const [basis, setBasis] = useState<Basis>('Latest purchase');
  const [percentage, setPercentage] = useState('30');
  const [manual, setManual] = useState('0');
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [revision, setRevision] = useState(0);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    setReady(false); setBusy(true); setError(''); setData(null);
    readPricing('get_item_pricing', { item_code: itemCode, ...(initialUom ? { uom: initialUom } : {}) }, controller.signal).then(r => {
      setData(r); setUom(r.uom); setPercentage(String(r.policy?.markup_percentage ?? 30));
      setBasis(r.policy?.cost_basis ?? 'Latest purchase'); setManual(String(r.policy?.manual_cost ?? 0)); setReady(true);
    }).catch(e => { if (!controller.signal.aborted) { setError(e.message); setBusy(false); } });
    return () => controller.abort();
  }, [itemCode, initialUom, revision]);
  useEffect(() => {
    if (!ready || !uom) return;
    const controller = new AbortController();
    setBusy(true); setError('');
    const timer = window.setTimeout(() => {
      readPricing('preview_item_price', { item_code: itemCode, uom, cost_basis: basis, markup_percentage: percentage, manual_cost: manual }, controller.signal)
        .then(setData).catch(e => { if (!controller.signal.aborted) setError(e.message); }).finally(() => { if (!controller.signal.aborted) setBusy(false); });
    }, 350);
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [ready, itemCode, uom, basis, percentage, manual]);
  const money = (value: string | number | null | undefined, currency = data?.currency) => {
    if (value === null || value === undefined) return '—';
    try { return new Intl.NumberFormat(isRTL ? 'ar-SA' : 'en', { style: 'currency', currency: currency || 'SAR', maximumFractionDigits: 4 }).format(Number(value)); }
    catch { return `${value} ${currency}`; }
  };
  async function save() {
    if (!data?.quote || busy) return;
    setSaving(true); setError(''); setStatus('');
    try {
      const response = await fetch('/api/method/klik_pos.api.item_pricing.save_item_price', { method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': window.csrf_token },
        body: JSON.stringify({ item_code: itemCode, uom, cost_basis: basis, markup_percentage: percentage, manual_cost: manual, snapshot: data.quote.snapshot }) });
      const result = await response.json();
      if (!response.ok || !result.message) throw new Error(extractErrorMessage(result, 'Unable to save selling price.'));
      window.dispatchEvent(new CustomEvent('abs-item-price-changed', { detail: { item_code: itemCode, uom, price: Number(result.message.selling_price), currency: result.message.currency } }));
      setStatus(t('Selling price and markup saved. The selected UOM price is updated for future sales; review existing carts before payment.', 'تم حفظ سعر البيع ونسبة الربح. تم تحديث سعر الوحدة المحددة للمبيعات المستقبلية؛ راجع السلال الحالية قبل الدفع.'));
      setData(result.message.pricing);
    } catch (e) { setError(e instanceof Error ? e.message : 'Unable to save selling price.'); }
    finally { setSaving(false); }
  }
  const input = 'w-full p-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100';
  const roundedMoney = (value: string | number, currency = data?.currency) => {
    try { return new Intl.NumberFormat(isRTL ? 'ar-SA' : 'en', { style: 'currency', currency: currency || 'SAR', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(Number(value)); }
    catch { return `${value} ${currency || ''}`; }
  };
  const q = !busy && !error ? data?.quote : null;
  return <section className="space-y-4" aria-busy={busy}>
    <div className="text-sm text-gray-600 dark:text-gray-300">{t('Purchase costs exclude tax, freight and landed-cost adjustments. The average is weighted by quantity across the last 8 submitted, non-return purchase invoices, using their recorded company-currency amounts and stock quantities.', 'تكلفة الشراء لا تشمل الضريبة والشحن وتعديلات التكلفة الإضافية. المتوسط مرجح بالكمية لآخر ٨ فواتير شراء معتمدة غير مرتجعة، باستخدام المبالغ بعملة الشركة وكميات وحدة المخزون.')}</div>
    {status && <p role="status" className="rounded-lg bg-green-50 dark:bg-green-950 p-3 text-green-800 dark:text-green-200">{status}</p>}
    {error && <p role="alert" className="rounded-lg bg-red-50 dark:bg-red-950 p-3 text-red-800 dark:text-red-200">{error}<button className="ms-3 underline" onClick={() => setRevision(v => v+1)}>{t('Refresh', 'تحديث')}</button></p>}
    {data && <>
      <div className="grid sm:grid-cols-3 gap-3">
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 text-blue-950 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-100"><p className="text-sm font-medium">{t('Latest invoice unit cost', 'تكلفة الوحدة في آخر فاتورة')}</p><p className="text-xl font-bold" dir="ltr">{money(data.purchases.latest?.cost)}</p><p className="text-xs">{t('Per', 'لكل')} {data.stock_uom}</p>{data.purchases.latest && <a target="_blank" rel="noopener noreferrer" className="text-xs text-blue-700 dark:text-blue-300 underline" href={`/desk/purchase-invoice/${encodeURIComponent(data.purchases.latest.invoice)}`}>{data.purchases.latest.date} · {data.purchases.latest.invoice}</a>}</div>
        <div className="rounded-xl border border-violet-200 bg-violet-50 p-4 text-violet-950 dark:border-violet-800 dark:bg-violet-950 dark:text-violet-100"><p className="text-sm font-medium">{t('Weighted average purchase cost', 'متوسط تكلفة الشراء المرجح')}</p><p className="text-xl font-bold" dir="ltr">{money(data.purchases.weighted_average)}</p><p className="text-xs">{data.purchases.invoice_count} {t('invoices', 'فواتير')} · {Number(data.purchases.stock_quantity).toLocaleString()} {data.stock_uom}</p></div>
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-emerald-950 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-100"><p className="text-sm font-medium">{t('Current selling price', 'سعر البيع الحالي')}</p><p className="text-xl font-bold" dir="ltr">{money(data.current_price?.price_list_rate, data.price_list_currency)}</p><p className="text-xs">{data.price_list} · {data.uom}</p></div>
      </div>
      <div className="grid sm:grid-cols-3 gap-3">
        <label className="text-sm">{t('Cost basis', 'أساس التكلفة')}<select disabled={saving} className={input} value={basis} onChange={e => { setStatus(''); setBasis(e.target.value as Basis); }}><option value="Latest purchase">{t('Latest purchase', 'آخر شراء')}</option><option value="Weighted average">{t('Weighted average', 'المتوسط المرجح')}</option><option value="Manual">{t('Manual cost', 'تكلفة يدوية')}</option></select></label>
        <label className="text-sm">{t('Selling UOM', 'وحدة البيع')}<select disabled={saving} className={input} value={uom} onChange={e => { setStatus(''); setUom(e.target.value); }}>{data.uoms.map(row => <option key={row.uom} value={row.uom}>{row.uom} (×{row.factor} {data.stock_uom})</option>)}</select></label>
        <label className="text-sm">{t('Profit / markup %', 'الربح / الزيادة ٪')}<input disabled={saving} type="number" min="0" step="0.1" className={input} value={percentage} onChange={e => { setStatus(''); setPercentage(e.target.value); }} /></label>
      </div>
      {data.policy && <p className="text-sm">{t('Saved markup for this UOM', 'النسبة المحفوظة لهذه الوحدة')}: {data.policy.markup_percentage}% <button type="button" disabled={saving} className="underline ms-2" onClick={() => { setPercentage(String(data.policy!.markup_percentage)); setBasis(data.policy!.cost_basis); setManual(String(data.policy!.manual_cost || 0)); }}>{t('Load saved rule', 'تحميل القاعدة المحفوظة')}</button></p>}
      {basis === 'Manual' && <label className="block text-sm">{t('Manual purchase cost per', 'تكلفة الشراء اليدوية لكل')} {data.stock_uom} ({data.currency})<input disabled={saving} type="number" min="0" step="0.0001" className={input} value={manual} onChange={e => { setStatus(''); setManual(e.target.value); }} /></label>}
      {busy ? <p role="status">{t('Calculating…', 'جارٍ الحساب…')}</p> : q ? <div className="rounded-xl bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 p-4 space-y-2">
        <p>{t('Cost', 'التكلفة')} {money(q.unit_cost)} × (1 + {percentage}% / 100)</p>
        <p className="text-lg font-semibold">{t('Rounded selling price to save', 'سعر البيع المقرب للحفظ')}: <span dir="ltr">{roundedMoney(q.selling_price)}</span> / {uom}</p>
        {data.tax.inclusive && data.tax.supported && <p>{t('Includes tax', 'يشمل الضريبة')}: {data.tax.rate}% · {t('Net price before tax', 'السعر الصافي قبل الضريبة')}: <strong dir="ltr">{money(q.net_selling_price)}</strong></p>}
        <p className="text-sm">{t('Unit profit before overheads and tax', 'ربح الوحدة قبل المصاريف والضريبة')}: {money(q.markup_amount)} · {t('Gross margin', 'هامش الربح الإجمالي')}: {Number(q.gross_margin_percentage).toFixed(2)}%</p>
        <p className="text-xs">{t('This is markup on cost. The saved selling price is rounded to the nearest whole unit; the effective margin may change.', 'هذه زيادة على التكلفة. يُقرب سعر البيع المحفوظ إلى أقرب وحدة كاملة وقد يتغير هامش الربح الفعلي.')}</p>
      </div> : !error && <p>{t('No purchase cost is available. Choose Manual cost to calculate a price.', 'لا تتوفر تكلفة شراء. اختر تكلفة يدوية لحساب السعر.')}</p>}
      <div className="text-sm space-y-2">
        <p>{t('Saving updates the generic Item Price for this item/UOM in the shared selling price list below. It affects future sales across counters using that list. Customer-specific prices and pricing rules may override it.', 'الحفظ يحدث سعر الصنف العام لهذه الوحدة في قائمة البيع المشتركة أدناه، ويؤثر على المبيعات المستقبلية للنقاط التي تستخدمها. قد تتجاوز أسعار العملاء وقواعد التسعير هذا السعر.')}</p>
        {data.blockers.map(message => <p className="text-amber-800 dark:text-amber-200" key={message}>{message}</p>)}
        {!data.can_save && !data.blockers.length && <p>{t('Only a System Manager with Item Price and pricing-policy permissions can save. You can still use this preview.', 'الحفظ متاح لمدير النظام الذي يملك صلاحيات أسعار الأصناف وسياسة التسعير. يمكنك استخدام المعاينة.')}</p>}
        <button type="button" disabled={!data.can_save || !q || busy || saving} onClick={save} className="rounded-lg bg-blue-600 text-white px-4 py-2 disabled:opacity-40">{saving ? t('Saving…', 'جارٍ الحفظ…') : `${t('Save price to', 'حفظ السعر في')} ${data.price_list || '—'}`}</button>
      </div>
    </>}
  </section>;
}
