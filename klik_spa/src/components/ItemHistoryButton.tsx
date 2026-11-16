import { useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { History, X } from 'lucide-react';
import { useCartStore } from '../stores/cartStore';
import { useI18n } from '../hooks/useI18n';
import { extractErrorMessage } from '../utils/errorExtraction';
type View = 'sales' | 'purchases' | 'customer_sales';
interface Line { qty: number | null; uom: string | null; net_rate: number | null; net_amount: number | null }
interface Transaction { name: string; route: string; posting_date: string; posting_time: string; party: string; party_name: string; currency: string; is_return: boolean; lines: Line[] }
interface HistoryData { view?: View; customer?: string | null; company: string; permissions: Record<View, boolean>; transactions: Transaction[] }
async function loadHistory(item: string, view: View | 'access', signal: AbortSignal, customer?: string) {
  const params = new URLSearchParams({ item_code: item, view });
  if (customer) params.set('customer', customer);
  const response = await fetch(`/api/method/klik_pos.api.item_history.get_item_history?${params}`, { credentials: 'include', signal });
  const result = await response.json();
  if (!response.ok || !result.message) throw new Error(extractErrorMessage(result, 'Unable to load item history.'));
  return result.message as HistoryData;
}
export default function ItemHistoryButton({ itemCode, itemName, compact = false }: { itemCode: string; itemName: string; compact?: boolean }) {
  const [open, setOpen] = useState(false);
  const { isRTL } = useI18n();
  const trigger = useRef<HTMLButtonElement>(null);
  const label = isRTL ? 'سجل الصنف' : 'Item history';
  return <>
    <button ref={trigger} type="button" title={label} aria-label={`${label}: ${itemName}`} onClick={e => { e.stopPropagation(); setOpen(true); }} className={`inline-flex cursor-pointer items-center gap-1 rounded-md border border-blue-200 dark:border-blue-700 bg-white dark:bg-gray-800 text-blue-700 dark:text-blue-300 hover:bg-blue-50 dark:hover:bg-gray-700 ${compact ? 'p-1.5' : 'px-2 py-1 text-xs'}`}>
      <History size={14} />{!compact && (isRTL ? 'السجل' : 'History')}
    </button>
    {open && createPortal(<ItemHistory itemCode={itemCode} itemName={itemName} onClose={() => { setOpen(false); trigger.current?.focus(); }} />, document.body)}
  </>;
}
function ItemHistory({ itemCode, itemName, onClose }: { itemCode: string; itemName: string; onClose: () => void }) {
  const { isRTL } = useI18n();
  const customer = useCartStore(s => s.selectedCustomer);
  const [access, setAccess] = useState<HistoryData | null>(null);
  const [data, setData] = useState<HistoryData | null>(null);
  const [view, setView] = useState<View>('sales');
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const panel = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const txt = (en: string, ar: string) => isRTL ? ar : en;
  useEffect(() => {
    const controller = new AbortController();
    setBusy(true); setError('');
    loadHistory(itemCode, 'access', controller.signal).then(result => {
      setAccess(result); setView(current => result.permissions[current] ? current : result.permissions.sales ? 'sales' : 'purchases');
    }).catch(e => { if (!controller.signal.aborted) { setError(e.message); setBusy(false); } });
    return () => controller.abort();
  }, [itemCode, retry]);
  useEffect(() => {
    if (!access) return;
    setData(null); setError('');
    if (!access.permissions[view] || (view === 'customer_sales' && !customer?.id)) { setBusy(false); return; }
    const controller = new AbortController();
    setBusy(true);
    loadHistory(itemCode, view, controller.signal, view === 'customer_sales' ? customer?.id : undefined).then(setData).catch(e => { if (!controller.signal.aborted) setError(e.message); }).finally(() => { if (!controller.signal.aborted) setBusy(false); });
    return () => controller.abort();
  }, [access, view, itemCode, customer?.id, retry]);
  useEffect(() => {
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden'; panel.current?.focus();
    const keys = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); onClose(); }
      if (e.key === 'Tab') {
        const nodes = panel.current?.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], [tabindex="0"]');
        if (!nodes?.length) return;
        const first = nodes[0], last = nodes[nodes.length - 1];
        if (e.shiftKey && (document.activeElement === first || document.activeElement === panel.current)) { e.preventDefault(); last?.focus(); }
        else if (!e.shiftKey && (document.activeElement === last || document.activeElement === panel.current)) { e.preventDefault(); first?.focus(); }
      }
    };
    document.addEventListener('keydown', keys, true);
    return () => { document.body.style.overflow = previous; document.removeEventListener('keydown', keys, true); };
  }, [onClose]);
  const format = (value: number | null, currency?: string) => {
    if (value === null || value === undefined) return '—';
    try { return new Intl.NumberFormat(isRTL ? 'ar-SA' : 'en', currency ? { style: 'currency', currency, maximumFractionDigits: 4 } : { maximumFractionDigits: 4 }).format(Number(value)); }
    catch { return `${value} ${currency || ''}`; }
  };
  const transactions = data?.view === view && (view !== 'customer_sales' || data.customer === customer?.id) ? data.transactions : [];
  const tabs: [View, string][] = [['sales', txt('Sales', 'المبيعات')], ['purchases', txt('Purchases', 'المشتريات')], ['customer_sales', txt('Selected customer', 'العميل المحدد')]];
  return <div className="fixed inset-0 z-[150] bg-black/50 p-3 sm:p-8 flex items-center justify-center" onClick={e => { e.stopPropagation(); if (e.target === e.currentTarget) onClose(); }}>
    <div ref={panel} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby={titleId} dir={isRTL ? 'rtl' : 'ltr'} className="w-full max-w-5xl max-h-[90vh] flex flex-col rounded-xl bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 shadow-2xl border border-gray-200 dark:border-gray-700 outline-none" onClick={e => e.stopPropagation()}>
      <header className="p-4 border-b border-gray-200 dark:border-gray-700 flex justify-between gap-3">
        <div><h2 id={titleId} className="text-lg font-semibold">{txt('Item history', 'سجل الصنف')} — {itemName}</h2><p className="text-sm text-gray-500 dark:text-gray-400">{itemCode} · {access?.company}</p></div>
        <button type="button" aria-label={txt('Close history', 'إغلاق السجل')} onClick={onClose} className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"><X size={20} /></button>
      </header>
      <div className="p-4 flex flex-wrap gap-2" role="group" aria-label={txt('History view', 'عرض السجل')}>
        {tabs.map(([key, label]) => <button key={key} type="button" aria-pressed={view === key} disabled={!access?.permissions[key]} onClick={() => setView(key)} className={`rounded-lg px-3 py-2 text-sm border disabled:opacity-40 ${view === key ? 'bg-blue-600 border-blue-600 text-white' : 'border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-800'}`}>{label}</button>)}
      </div>
      <div className="px-4 pb-3 text-sm text-gray-600 dark:text-gray-300">
        {txt('Latest 8 submitted invoices in this company. Drafts and cancelled invoices are excluded. Rates and amounts exclude tax; each line keeps its original UOM and currency.', 'آخر ٨ فواتير معتمدة في هذه الشركة. تُستثنى المسودات والفواتير الملغاة. الأسعار والمبالغ لا تشمل الضريبة، مع عرض وحدة القياس والعملة الأصلية لكل سطر.')}
        {view === 'customer_sales' && <p className="mt-2 font-medium">{customer?.id ? `${txt('Customer', 'العميل')}: ${customer.name}` : txt('Select a customer in the POS cart first.', 'اختر عميلاً في سلة نقاط البيع أولاً.')}</p>}
        {access && !access.permissions.purchases && <p className="mt-2">{txt('Purchase costs require Purchase Invoice read and report permissions.', 'عرض تكلفة الشراء يتطلب صلاحية قراءة وتقارير فواتير الشراء.')}</p>}
      </div>
      <div className="overflow-auto px-4 pb-4" aria-busy={busy}>
        {busy ? <p role="status" className="py-8 text-center">{txt('Loading history…', 'جارٍ تحميل السجل…')}</p> : error ? <div role="alert" className="p-4 text-red-700 dark:text-red-300">{error}<button type="button" className="ms-3 underline" onClick={() => setRetry(v => v + 1)}>{txt('Retry', 'إعادة المحاولة')}</button></div> : transactions.length ? <table className="w-full text-sm text-start">
          <thead className="bg-gray-100 dark:bg-gray-800"><tr>{[txt('Date / invoice', 'التاريخ / الفاتورة'), txt('Party', 'الطرف'), txt('Qty', 'الكمية'), txt('UOM', 'الوحدة'), txt('Net rate', 'السعر الصافي'), txt('Net amount', 'المبلغ الصافي')].map(h => <th className="p-3 text-start whitespace-nowrap" key={h}>{h}</th>)}</tr></thead>
          <tbody>{transactions.flatMap(tx => tx.lines.map((line, index) => <tr key={`${tx.name}:${index}`} className="border-b border-gray-200 dark:border-gray-700">
            <td className="p-3 whitespace-nowrap">{index === 0 && <><div>{tx.posting_date} {String(tx.posting_time || '').slice(0, 8)}</div><a className="text-blue-700 dark:text-blue-300 underline" target="_blank" rel="noopener noreferrer" href={`/desk/${tx.route}/${encodeURIComponent(tx.name)}`}>{tx.name}</a>{tx.is_return && <span className="ms-2 rounded bg-amber-100 text-amber-900 px-1">{txt('Return', 'مرتجع')}</span>}</>}</td>
            <td className="p-3">{index === 0 && (tx.party_name || tx.party)}</td><td className="p-3 whitespace-nowrap" dir="ltr">{format(line.qty)}</td><td className="p-3">{line.uom || '—'}</td><td className="p-3 whitespace-nowrap" dir="ltr">{format(line.net_rate, tx.currency)}</td><td className="p-3 whitespace-nowrap" dir="ltr">{format(line.net_amount, tx.currency)}</td>
          </tr>))}</tbody>
        </table> : <p className="py-8 text-center">{view === 'customer_sales' && !customer?.id ? txt('Choose a customer to see their last purchases of this item.', 'اختر عميلاً لعرض آخر مشترياته من هذا الصنف.') : access && !access.permissions[view] ? txt('No permission to view this report.', 'ليس لديك صلاحية عرض هذا التقرير.') : txt('No submitted invoices found for this item and filter.', 'لا توجد فواتير معتمدة لهذا الصنف وفق هذا الفلتر.')}</p>}
      </div>
    </div>
  </div>;
}
