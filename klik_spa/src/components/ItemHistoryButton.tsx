import ItemPricingPanel from "./ItemPricingPanel";
import StockTransfer from "./StockTransfer";
import { useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { History, X } from 'lucide-react';
import { useCartStore } from '../stores/cartStore';
import { useI18n } from '../hooks/useI18n';
import { extractErrorMessage } from '../utils/errorExtraction';
type View = 'sales' | 'purchases' | 'customer_sales' | 'pricing' | 'stock';
interface Line { qty: number | null; uom: string | null; net_rate: number | null; net_amount: number | null }
interface Transaction { name: string; route: string; posting_date: string; posting_time: string; party: string; party_name: string; currency: string; is_return: boolean; lines: Line[] }
interface HistoryData { view?: View; customer?: string | null; company: string; user?: string; permissions: Record<View, boolean> & { transfer: boolean }; transactions: Transaction[]; stock_uom?: string; is_stock_item?: boolean; has_batch_no?: boolean; has_serial_no?: boolean; warehouses?: { warehouse: string; warehouse_name: string; actual_qty: number }[] }
async function loadHistory(item: string, view: View | 'access', signal: AbortSignal, customer?: string) {
  const params = new URLSearchParams({ item_code: item, view });
  if (customer) params.set('customer', customer);
  const response = await fetch(`/api/method/klik_pos.api.item_history.get_item_history?${params}`, { credentials: 'include', signal });
  const result = await response.json();
  if (!response.ok || !result.message) throw new Error(extractErrorMessage(result, 'Unable to load item history.'));
  return result.message as HistoryData;
}
export default function ItemHistoryButton({ itemCode, itemName, itemUom, compact = false }: { itemCode: string; itemName: string; itemUom?: string; compact?: boolean }) {
  const [open, setOpen] = useState(false);
  const { isRTL } = useI18n();
  const trigger = useRef<HTMLButtonElement>(null);
  const label = isRTL ? 'سجل الصنف' : 'Item history';
  return <>
    <button ref={trigger} type="button" title={label} aria-label={`${label}: ${itemName}`} onClick={e => { e.stopPropagation(); setOpen(true); }} className={`inline-flex cursor-pointer items-center gap-1 rounded-md border border-blue-200 dark:border-blue-700 bg-white dark:bg-gray-800 text-blue-700 dark:text-blue-300 hover:bg-blue-50 dark:hover:bg-gray-700 ${compact ? 'p-1.5' : 'px-2 py-1 text-xs'}`}>
      <History size={14} />{!compact && (isRTL ? 'السجل' : 'History')}
    </button>
    {open && createPortal(<ItemHistory itemCode={itemCode} itemName={itemName} itemUom={itemUom} onClose={() => { setOpen(false); trigger.current?.focus(); }} />, document.body)}
  </>;
}
function ItemHistory({ itemCode, itemName, itemUom, onClose }: { itemCode: string; itemName: string; itemUom?: string; onClose: () => void }) {
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
      setAccess(result); setView(current => result.permissions[current] ? current : result.permissions.sales ? 'sales' : result.permissions.stock ? 'stock' : 'purchases');
    }).catch(e => { if (!controller.signal.aborted) { setError(e.message); setBusy(false); } });
    return () => controller.abort();
  }, [itemCode, retry]);
  useEffect(() => {
    if (!access) return;
    setData(null); setError('');
    if (view === 'pricing' || !access.permissions[view] || (view === 'customer_sales' && !customer?.id)) { setBusy(false); return; }
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
        const nodes = panel.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href], [tabindex="0"]');
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
  const tabs: [View, string][] = [['sales', txt('Sales', 'المبيعات')], ['purchases', txt('Purchases', 'المشتريات')], ['customer_sales', txt('Selected customer', 'العميل المحدد')], ['pricing', txt('Pricing / profit', 'التسعير / الربح')], ['stock', txt('Stock', 'المخزون')]];
  const tabColors: Record<View, { active: string; idle: string }> = {
    sales: { active: 'bg-blue-600 border-blue-600 text-white shadow-md shadow-blue-200 dark:shadow-none', idle: 'bg-blue-50 border-blue-200 text-blue-800 hover:bg-blue-100 dark:bg-blue-950 dark:border-blue-800 dark:text-blue-200 dark:hover:bg-blue-900' },
    purchases: { active: 'bg-violet-600 border-violet-600 text-white shadow-md shadow-violet-200 dark:shadow-none', idle: 'bg-violet-50 border-violet-200 text-violet-800 hover:bg-violet-100 dark:bg-violet-950 dark:border-violet-800 dark:text-violet-200 dark:hover:bg-violet-900' },
    customer_sales: { active: 'bg-teal-700 border-teal-700 text-white shadow-md shadow-teal-200 dark:shadow-none', idle: 'bg-teal-50 border-teal-200 text-teal-800 hover:bg-teal-100 dark:bg-teal-950 dark:border-teal-800 dark:text-teal-200 dark:hover:bg-teal-900' },
    pricing: { active: 'bg-amber-700 border-amber-700 text-white shadow-md shadow-amber-200 dark:shadow-none', idle: 'bg-amber-50 border-amber-200 text-amber-900 hover:bg-amber-100 dark:bg-amber-950 dark:border-amber-800 dark:text-amber-200 dark:hover:bg-amber-900' },
    stock: { active: 'bg-emerald-700 border-emerald-700 text-white shadow-md shadow-emerald-200 dark:shadow-none', idle: 'bg-emerald-50 border-emerald-200 text-emerald-800 hover:bg-emerald-100 dark:bg-emerald-950 dark:border-emerald-800 dark:text-emerald-200 dark:hover:bg-emerald-900' },
  };
  return <div className="fixed inset-0 z-[150] bg-black/50 p-3 sm:p-8 flex items-center justify-center" onClick={e => { e.stopPropagation(); if (e.target === e.currentTarget) onClose(); }}>
    <div ref={panel} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby={titleId} dir={isRTL ? 'rtl' : 'ltr'} className="w-full max-w-5xl max-h-[90vh] flex flex-col rounded-xl bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 shadow-2xl border border-gray-200 dark:border-gray-700 outline-none" onClick={e => e.stopPropagation()}>
      <header className="p-4 border-b border-gray-200 dark:border-gray-700 flex justify-between gap-3">
        <div><h2 id={titleId} className="text-lg font-semibold">{txt('Item history', 'سجل الصنف')} — {itemName}</h2><p className="text-sm text-gray-500 dark:text-gray-400">{itemCode} · {access?.company}</p></div>
        <button type="button" aria-label={txt('Close history', 'إغلاق السجل')} onClick={onClose} className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"><X size={20} /></button>
      </header>
      <div className="p-4 flex flex-wrap gap-2" role="group" aria-label={txt('History view', 'عرض السجل')}>
        {tabs.map(([key, label]) => <button key={key} type="button" aria-pressed={view === key} disabled={!access?.permissions[key]} onClick={() => setView(key)} className={`rounded-lg px-3 py-2 text-sm font-semibold border transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:opacity-40 disabled:cursor-not-allowed ${view === key ? tabColors[key].active : tabColors[key].idle}`}>{label}</button>)}
      </div>
      <div className="px-4 pb-3 text-sm text-gray-600 dark:text-gray-300">
        {view !== 'pricing' && view !== 'stock' && txt('Latest 8 submitted invoices in this company. Drafts and cancelled invoices are excluded. Rates and amounts exclude tax; each line keeps its original UOM and currency.', 'آخر ٨ فواتير معتمدة في هذه الشركة. تُستثنى المسودات والفواتير الملغاة. الأسعار والمبالغ لا تشمل الضريبة، مع عرض وحدة القياس والعملة الأصلية لكل سطر.')}
        {view === 'stock' && txt('Current on-hand balance in accessible warehouses of this company, in the stock UOM.', 'الرصيد الحالي في المستودعات المسموح بها في هذه الشركة بوحدة المخزون.')}
        {view === 'customer_sales' && <p className="mt-2 font-medium">{customer?.id ? `${txt('Customer', 'العميل')}: ${customer.name}` : txt('Select a customer in the POS cart first.', 'اختر عميلاً في سلة نقاط البيع أولاً.')}</p>}
        {access && !access.permissions.purchases && <p className="mt-2">{txt('Purchase costs require Purchase Invoice read and report permissions.', 'عرض تكلفة الشراء يتطلب صلاحية قراءة وتقارير فواتير الشراء.')}</p>}
      </div>
      <div className="overflow-auto px-4 pb-4" aria-busy={busy}>
        {view === 'stock' && !busy && !error && data?.view === 'stock' && data.is_stock_item && access?.permissions.transfer && <StockTransfer itemCode={itemCode} itemName={itemName} company={data.company} user={data.user || ''} uom={data.stock_uom || ''} warehouses={data.warehouses || []} hasBatch={!!data.has_batch_no} hasSerial={!!data.has_serial_no} rtl={isRTL} onComplete={() => setRetry(v => v + 1)} />}
        {view === 'pricing' ? <ItemPricingPanel itemCode={itemCode} initialUom={itemUom} /> : busy ? <p role="status" className="py-8 text-center">{txt('Loading history…', 'جارٍ تحميل السجل…')}</p> : error ? <div role="alert" className="p-4 text-red-700 dark:text-red-300">{error}<button type="button" className="ms-3 underline" onClick={() => setRetry(v => v + 1)}>{txt('Retry', 'إعادة المحاولة')}</button></div> : view === 'stock' ? !data?.is_stock_item ? <p className="py-8 text-center">{txt('This is not a stock item.', 'هذا الصنف غير مخزني.')}</p> : data.warehouses?.length ? <table className="w-full text-sm text-start"><thead className="bg-gray-100 dark:bg-gray-800"><tr><th className="p-3 text-start">{txt('Warehouse', 'المستودع')}</th><th className="p-3 text-start">{txt('Closing stock', 'المخزون الختامي')}</th><th className="p-3 text-start">{txt('UOM', 'الوحدة')}</th></tr></thead><tbody>{data.warehouses.map(row => <tr key={row.warehouse} className="border-b border-gray-200 dark:border-gray-700"><td className="p-3">{row.warehouse}</td><td className="p-3" dir="ltr">{format(row.actual_qty)}</td><td className="p-3">{data.stock_uom}</td></tr>)}</tbody><tfoot><tr className="font-semibold"><td className="p-3">{txt('Total', 'المجموع')}</td><td className="p-3" dir="ltr">{format(data.warehouses.reduce((sum, row) => sum + Number(row.actual_qty || 0), 0))}</td><td className="p-3">{data.stock_uom}</td></tr></tfoot></table> : <p className="py-8 text-center">{txt('No accessible warehouses found.', 'لا توجد مستودعات متاحة.')}</p> : transactions.length ? <table className="w-full text-sm text-start">
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
