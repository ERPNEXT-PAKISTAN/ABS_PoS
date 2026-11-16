import { useEffect, useState } from 'react';
import { useBranding, type Branding } from '../hooks/useBranding';
import { extractErrorMessage } from '../utils/errorExtraction';
interface Profile { name: string; company: string; warehouse: string; currency: string; checks: Record<string, boolean>; zatca: { state: string } }
interface Setup { can_manage: boolean; profiles: Profile[] }
export default function ABSSetup() {
  const branding = useBranding();
  const [form, setForm] = useState<Branding>(branding);
  const [setup, setSetup] = useState<Setup | null>(null);
  const [selected, setSelected] = useState('');
  const [message, setMessage] = useState('');
  const [saving, setSaving] = useState(false);
  useEffect(() => setForm(branding), [branding]);
  useEffect(() => {
    fetch('/api/method/klik_pos.api.setup.get_setup').then(r => r.json()).then(r => {
      if (!r.message) throw new Error(extractErrorMessage(r, 'Unable to load setup.'));
      setSetup(r.message); setSelected(r.message.profiles[0]?.name || '');
    }).catch(e => setMessage(e.message));
  }, []);
  const profile = setup?.profiles.find(p => p.name === selected);
  async function save() {
    setSaving(true); setMessage('');
    try {
      const response = await fetch('/api/method/klik_pos.api.setup.save_branding', {
        method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': window.csrf_token }, body: JSON.stringify({ settings: form })
      });
      const result = await response.json();
      if (!response.ok || !result.message) throw new Error(extractErrorMessage(result, 'Unable to save settings.'));
      window.dispatchEvent(new Event('abs-branding-changed')); setMessage('Settings saved.');
    } catch (e) { setMessage(e instanceof Error ? e.message : 'Unable to save settings.'); }
    finally { setSaving(false); }
  }
  return <section className="space-y-6 text-gray-900 dark:text-gray-100">
    <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-6 space-y-4">
      <h2 className="text-xl font-semibold">ABS PoS setup</h2>
      <p>Configure branding, then check your existing ERPNext company and counter settings.</p>
      {(['business_name', 'logo', 'support_email', 'receipt_footer'] as const).map(field => <label key={field} className="block">
        <span className="block text-sm mb-1">{{ business_name: 'POS name', logo: 'Uploaded logo path (optional)', support_email: 'Support email (optional)', receipt_footer: 'Receipt footer (optional)' }[field]}</span>
        <input disabled={!setup?.can_manage} value={form[field]} onChange={e => setForm({ ...form, [field]: e.target.value })} className="w-full rounded-lg border p-3 bg-white dark:bg-gray-900 border-gray-300 dark:border-gray-600" />
      </label>)}
      {setup?.can_manage && <div className="flex gap-4 items-center"><button disabled={saving} onClick={save} className="px-4 py-2 rounded-lg bg-beveren-600 text-white disabled:opacity-50">{saving ? 'Saving…' : 'Save branding'}</button><a href="/desk/abs-pos-settings" className="underline">Upload logo in settings</a></div>}
      {message && <p role="status" className="text-sm">{message}</p>}
    </div>
    <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-6 space-y-4">
      <h3 className="font-semibold">Counter readiness</h3>
      <select aria-label="POS Profile" value={selected} onChange={e => setSelected(e.target.value)} className="w-full rounded-lg border p-3 bg-white dark:bg-gray-900 border-gray-300 dark:border-gray-600">
        <option value="">Select a POS Profile</option>{setup?.profiles.map(p => <option key={p.name} value={p.name}>{p.company} — {p.name}</option>)}
      </select>
      {profile ? <>
        <p>{profile.company} · {profile.warehouse || 'Warehouse missing'} · {profile.currency || 'Currency missing'}</p>
        <ul className="grid sm:grid-cols-2 gap-2">{Object.entries(profile.checks).map(([name, ready]) => <li key={name}>{ready ? '✓' : '○'} {name.replaceAll('_', ' ')} — {ready ? 'Configured' : 'Needs configuration'}</li>)}</ul>
        <p className="font-medium">ZATCA: {profile.zatca.state}</p>
        <p className="text-sm">Select ABS Thermal Receipt in your POS Profile to use the configured receipt footer.</p>
        <p className="text-sm">Integration is optional. Enabled means configured, not independently verified for compliance.</p>
        {setup?.can_manage && <div className="flex flex-wrap gap-4 underline"><a href={`/desk/pos-profile/${encodeURIComponent(profile.name)}`}>Configure counter and cashiers</a><a href={`/desk/company/${encodeURIComponent(profile.company)}`}>Configure company</a><a href="/desk/print-format/ABS%20Thermal%20Receipt">ABS receipt template</a></div>}
      </> : <p>No accessible counter selected. Ask a System Manager to configure a POS Profile and assign your cashier account.</p>}
    </div>
  </section>;
}
