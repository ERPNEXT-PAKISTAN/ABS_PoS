import { newCartId } from "../utils/cartIdentity";
/** Preserve one exact checkout across network errors, refreshes and repeated clicks. */
export function checkoutScope() {
  const match = document.cookie.match(/(?:^|;\s*)user_id=([^;]+)/);
  return decodeURIComponent(match?.[1] || 'Guest');
}
const key = () => `abs-checkout:${checkoutScope()}`;
export function checkoutRecord() {
  const saved = localStorage.getItem(key());
  return saved ? JSON.parse(saved) as { id: string; payload: string; completed?: boolean; invoice?: string } : null;
}
export function prepareCheckout(data: Record<string, unknown>) {
  if (checkoutScope() === 'Guest') throw new Error('Please sign in before checkout.');
  const payload = JSON.stringify(data);
  const pending = checkoutRecord();
  if (pending) {
    if (pending.payload === payload) return { ...data, checkoutRequestId: pending.id };
    const original = JSON.parse(pending.payload);
    if (!pending.completed || original.checkoutCartId === data.checkoutCartId) {
      throw new Error('A previous checkout must be resolved first. Use the checkout recovery notice to retry the original request.');
    }
  }
  const id = `abs-${String(data.checkoutCartId || newCartId())}`;
  localStorage.setItem(key(), JSON.stringify({ id, payload }));
  return { ...data, checkoutRequestId: id };
}
export function finishCheckout(invoice: string) {
  const pending = checkoutRecord();
  if (pending) localStorage.setItem(key(), JSON.stringify({ ...pending, completed: true, invoice }));
  window.dispatchEvent(new Event('abs-checkout-changed'));
}
export function rejectCheckout() { localStorage.removeItem(key()); }
