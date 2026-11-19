import { useState } from 'react';
import { CheckCircle2, XCircle } from 'lucide-react';
import { extractErrorMessage } from '../utils/errorExtraction';
import { newCartId } from '../utils/cartIdentity';

type Warehouse = { warehouse: string; actual_qty: number };
type Props = { itemCode: string; itemName: string; company: string; user: string; uom: string; warehouses: Warehouse[]; hasBatch: boolean; hasSerial: boolean; rtl: boolean; onComplete: () => void };

export default function StockTransfer({ itemCode, itemName, company, user, uom, warehouses, hasBatch, hasSerial, rtl, onComplete }: Props) {
  const t = (en: string, ar: string) => rtl ? ar : en;
  const [open, setOpen] = useState(false);
  const [source, setSource] = useState('');
  const [target, setTarget] = useState('');
  const [qty, setQty] = useState('');
  const [batch, setBatch] = useState('');
  const [serial, setSerial] = useState('');
  const [remarks, setRemarks] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [entry, setEntry] = useState('');
  const storageKey = `abs-stock-transfer:${user}:${company}:${itemCode}`;
  const [pending, setPending] = useState<{ request_id: string; item_code: string; source_warehouse: string; target_warehouse: string; qty: string; batch_no: string; serial_no: string; remarks?: string } | null>(() => {
    try { return JSON.parse(sessionStorage.getItem(storageKey) || 'null'); } catch { return null; }
  });

  async function submit() {
    const payload = pending || { request_id: newCartId(), item_code: itemCode, source_warehouse: source, target_warehouse: target, qty, batch_no: batch, serial_no: serial, remarks };
    if (!payload.source_warehouse || !payload.target_warehouse || payload.source_warehouse === payload.target_warehouse || !Number.isFinite(Number(payload.qty)) || Number(payload.qty) <= 0 || (hasBatch && !payload.batch_no.trim()) || (hasSerial && !payload.serial_no.trim())) {
      setError(t('Choose different warehouses and enter a positive quantity and any required batch or serial numbers.', 'اختر مستودعين مختلفين وأدخل كمية موجبة ورقم التشغيلة أو الأرقام التسلسلية المطلوبة.'));
      return;
    }
    setBusy(true); setError(''); setPending(payload); sessionStorage.setItem(storageKey, JSON.stringify(payload));
    try {
      const response = await fetch('/api/method/klik_pos.api.item_history.transfer_stock', {
        method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': window.csrf_token }, body: JSON.stringify(payload),
      });
      const result = await response.json();
      if (!response.ok || !result.message?.success) {
        if (!pending && response.status >= 400 && response.status < 500) { setPending(null); sessionStorage.removeItem(storageKey); }
        throw new Error(extractErrorMessage(result, 'Unable to submit the transfer.'));
      }
      setEntry(result.message.name); setPending(null); sessionStorage.removeItem(storageKey);
    } catch (e) { setError(e instanceof Error ? e.message : t('Transfer could not be confirmed.', 'تعذر تأكيد التحويل.')); }
    finally { setBusy(false); }
  }

  const field = 'mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-slate-900 focus:border-blue-500 focus:ring-2 focus:ring-blue-100 disabled:opacity-60 dark:bg-gray-800 dark:text-white dark:border-gray-600';
  return <>
    <button type="button" onClick={() => setOpen(true)} className="mb-4 rounded-lg bg-blue-600 px-4 py-2 font-medium text-white shadow-sm hover:bg-blue-700">{t('Transfer stock', 'تحويل المخزون')}</button>
    {open && <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/60 p-4" role="dialog" aria-modal="true" aria-labelledby="stock-transfer-title" dir={rtl ? 'rtl' : 'ltr'}>
      <div className="w-full max-w-xl max-h-[90vh] overflow-auto rounded-xl bg-white p-5 shadow-xl dark:bg-gray-900">
        <div className="rounded-xl bg-gradient-to-r from-blue-700 to-indigo-600 p-4 text-white"><h3 id="stock-transfer-title" className="text-lg font-semibold">{t('Material Transfer', 'تحويل المواد')}</h3>
        <p className="mt-1 text-sm text-blue-100">{itemName} ({itemCode}) · {company}</p></div>
        {entry ? <div className="mt-4 space-y-4"><div role="status" className="flex items-start gap-3 rounded-lg border border-green-300 bg-green-50 p-4 text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-200"><CheckCircle2 className="shrink-0" size={24} aria-hidden="true" /><div><p className="font-semibold">{t('Transfer submitted successfully', 'تم اعتماد التحويل بنجاح')}</p><p className="mt-1 text-sm">{t('Stock Entry:', 'حركة المخزون:')} <a target="_blank" rel="noopener noreferrer" className="underline" href={`/desk/stock-entry/${encodeURIComponent(entry)}`}>{entry}</a></p></div></div><button type="button" onClick={() => { setOpen(false); setEntry(''); onComplete(); }} className="rounded border px-4 py-2">{t('Close', 'إغلاق')}</button></div> : <div className="mt-4 space-y-3">
          <label className="block text-sm">{t('From warehouse', 'من المستودع')}<select className={field} value={source} disabled={busy || !!pending} onChange={e => setSource(e.target.value)}><option value="">{t('Select warehouse', 'اختر المستودع')}</option>{warehouses.map(w => <option key={w.warehouse} value={w.warehouse}>{w.warehouse} ({w.actual_qty} {uom})</option>)}</select></label>
          <label className="block text-sm">{t('To warehouse', 'إلى المستودع')}<select className={field} value={target} disabled={busy || !!pending} onChange={e => setTarget(e.target.value)}><option value="">{t('Select warehouse', 'اختر المستودع')}</option>{warehouses.map(w => <option key={w.warehouse} value={w.warehouse}>{w.warehouse}</option>)}</select></label>
          <label className="block text-sm">{t('Quantity', 'الكمية')} ({uom})<input type="number" min="0" step="any" className={field} value={qty} disabled={busy || !!pending} onChange={e => setQty(e.target.value)} /></label>
          {hasBatch && <label className="block text-sm">{t('Batch number', 'رقم التشغيلة')}<input className={field} value={batch} disabled={busy || !!pending} onChange={e => setBatch(e.target.value)} /></label>}
          {hasSerial && <label className="block text-sm">{t('Serial numbers, one per line', 'الأرقام التسلسلية، رقم في كل سطر')}<textarea className={field} rows={3} value={serial} disabled={busy || !!pending} onChange={e => setSerial(e.target.value)} /></label>}
          <label className="block rounded-lg bg-blue-50 p-3 text-sm font-medium text-blue-900 dark:bg-blue-950 dark:text-blue-100">{t('Remarks (optional)', 'ملاحظات (اختياري)')}<textarea className={field} rows={3} maxLength={2000} value={remarks} disabled={busy || !!pending} onChange={e => setRemarks(e.target.value)} placeholder={t('Reason or notes for this transfer', 'سبب التحويل أو ملاحظات')} /></label>
          {error && <div role="alert" className="flex items-start gap-3 rounded-lg border border-red-300 bg-red-50 p-3 text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200"><XCircle className="shrink-0" size={22} aria-hidden="true" /><div><p className="font-semibold">{pending ? t('Submission not confirmed', 'لم يتم تأكيد الاعتماد') : t('Transfer not submitted', 'لم يتم اعتماد التحويل')}</p><p className="mt-1 text-sm">{error}</p></div></div>}
          {pending && <p className="text-sm text-amber-700">{t('The result is unconfirmed. Retry the same request to check safely.', 'النتيجة غير مؤكدة. أعد محاولة الطلب نفسه للتحقق بأمان.')}</p>}
          {pending && <p className="text-sm">{pending.source_warehouse} → {pending.target_warehouse}: {pending.qty} {uom}{pending.batch_no ? ` · ${pending.batch_no}` : ''}{pending.serial_no ? ` · ${pending.serial_no}` : ''}{pending.remarks ? ` · ${pending.remarks}` : ''}</p>}
          <div className="flex gap-3"><button type="button" onClick={submit} disabled={busy} className="rounded bg-blue-600 px-4 py-2 text-white disabled:opacity-50">{busy ? t('Submitting…', 'جارٍ الاعتماد…') : pending ? t('Retry transfer', 'إعادة محاولة التحويل') : t('Create and submit transfer', 'إنشاء التحويل واعتماده')}</button><button type="button" onClick={() => setOpen(false)} disabled={busy} className="rounded border px-4 py-2">{t('Close', 'إغلاق')}</button></div>
        </div>}
      </div>
    </div>}
  </>;
}
