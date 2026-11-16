import { useEffect, useState } from 'react';
export interface Branding { business_name: string; logo: string; support_email: string; receipt_footer: string }
const defaults: Branding = { business_name: 'ABS PoS', logo: '', support_email: '', receipt_footer: '' };
export function useBranding() {
  const [branding, setBranding] = useState(defaults);
  useEffect(() => {
    const load = () => fetch('/api/method/klik_pos.api.setup.get_branding').then(r => r.json()).then(r => {
      if (r.message) {
        setBranding(r.message); document.title = r.message.business_name;
        const icon = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
        if (icon && r.message.logo) { icon.href = r.message.logo; icon.removeAttribute('type'); }
      }
    }).catch(() => {});
    load(); window.addEventListener('abs-branding-changed', load);
    return () => window.removeEventListener('abs-branding-changed', load);
  }, []);
  return branding;
}
