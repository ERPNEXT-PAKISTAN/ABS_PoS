import { newCartId } from "../utils/cartIdentity";
import { useEffect, useState, type ReactNode } from 'react';
import { useAuth } from '../hooks/useAuth';
import { useCartStore } from '../stores/cartStore';
import { checkoutRecord } from '../services/checkoutIdentity';
import { createSalesInvoice } from '../services/salesInvoice';
export default function CartRecovery({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const [profileVersion, setProfileVersion] = useState(0);
  useEffect(() => {
    const changed = () => setProfileVersion(v => v + 1);
    window.addEventListener('abs-profile-changed', changed);
    return () => window.removeEventListener('abs-profile-changed', changed);
  }, []);
  const [ready, setReady] = useState(false);
  const [notice, setNotice] = useState('');
  const [pending, setPending] = useState(false);
  const [retrying, setRetrying] = useState(false);
  useEffect(() => {
    const uncertain = () => { setPending(true); setNotice('Checkout confirmation was interrupted. Retry the original request to confirm its result.'); };
    window.addEventListener('abs-checkout-uncertain', uncertain);
    return () => window.removeEventListener('abs-checkout-uncertain', uncertain);
  }, []);
  useEffect(() => {
    if (loading) return;
    let active = true;
    setReady(false);
    async function restore() {
      let profile = 'no-profile';
      if (user?.name) {
        const session = await fetch('/api/method/klik_pos.api.setup.get_session_context').then(r => r.json());
        if (session.message?.user !== user.name) {
          if (active) setNotice('Your session changed. Please sign in again before restoring a cart.');
          return;
        }
        window.csrf_token = session.message.csrf_token;
        try {
          const r = await fetch('/api/method/klik_pos.api.pos_profile.get_pos_details').then(r => r.json());
          profile = r.message?.name || profile;
        } catch { /* Remain scoped to this user if no profile is configured. */ }
      }
      if (!active) return;
      const name = `abs-cart:v1:${user?.name || 'Guest'}:${profile}`;
      const saved = localStorage.getItem(name);
      useCartStore.persist.setOptions({ name });
      useCartStore.setState({ cartId: newCartId(), profileName: profile === 'no-profile' ? null : profile, cartItems: [], appliedCoupons: [], selectedCustomer: null });
      if (saved && user?.name) {
        localStorage.setItem(name, saved);
        await useCartStore.persist.rehydrate();
        useCartStore.setState({ profileName: profile === 'no-profile' ? null : profile });
      }
      if (!active) return;
      const record = user?.name ? checkoutRecord() : null;
      const matching = record && JSON.parse(record.payload).checkoutCartId === useCartStore.getState().cartId;
      if (record?.completed && matching) {
        useCartStore.getState().clearCart();
        setNotice(`Previous checkout completed: ${record.invoice}. The completed cart has been cleared.`);
      } else if (record && !record.completed) {
        setPending(true); setNotice('A checkout has an uncertain result. Retry its original request before starting another sale.');
      } else if (useCartStore.getState().cartItems.length) {
        setNotice('Previous cart restored. Check prices and stock before paying.');
      } else { setNotice(''); setPending(false); }
      setReady(true);
    }
    restore().catch(() => { if (active) { setNotice('Cart recovery failed. Do not continue checkout until device storage is available.'); } });
    return () => { active = false; };
  }, [user?.name, loading, profileVersion]);
  async function retry() {
    const record = checkoutRecord();
    if (!record || record.completed) return;
    setRetrying(true);
    try {
      const result = await createSalesInvoice(JSON.parse(record.payload));
      if (JSON.parse(record.payload).checkoutCartId === useCartStore.getState().cartId) useCartStore.getState().clearCart();
      setPending(false); setNotice(`Checkout confirmed: ${result.invoice_name}. Open Invoice History to view or print it.`);
    } catch (e) { setNotice(e instanceof Error ? e.message : 'Checkout could not be confirmed.'); setPending(Boolean(checkoutRecord() && !checkoutRecord()?.completed)); }
    finally { setRetrying(false); }
  }
  if (!ready || loading) return <div role="status" className="p-8">{notice || 'Restoring your POS session…'}</div>;
  return <>{notice && <div role="status" className="fixed top-2 left-1/2 -translate-x-1/2 z-[100] max-w-xl rounded-lg bg-amber-100 text-amber-950 border border-amber-300 p-3 shadow-lg">
    {notice}
    {pending ? <button disabled={retrying} onClick={retry} className="ms-3 underline">{retrying ? 'Checking…' : 'Retry original checkout'}</button> : <button onClick={() => setNotice('')} className="ms-3 underline">Continue</button>}
  </div>}{children}</>;
}
