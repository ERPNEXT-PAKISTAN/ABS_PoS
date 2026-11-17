import { useEffect, useState } from 'react'
import { Filter, X } from 'lucide-react'

type ItemType = { id: string; name: string; count: number }

export default function ItemTypeFilter() {
  const [types, setTypes] = useState<ItemType[]>([])
  const [selected, setSelected] = useState('')

  useEffect(() => {
    fetch('/api/method/klik_pos.api.item.get_item_types_for_pos')
      .then(r => r.ok ? r.json() : Promise.reject(r))
      .then(data => setTypes(Array.isArray(data?.message) ? data.message : []))
      .catch(() => setTypes([]))
  }, [])

  const apply = (value: string) => {
    setSelected(value)
    window.dispatchEvent(new CustomEvent('abs-custom-type-filter', { detail: { custom_type: value } }))
  }

  return <div className="flex items-center gap-2 px-3 py-2">
    <Filter size={16} className="text-gray-500" aria-hidden="true" />
    <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Item type</label>
    <select value={selected} onChange={e => apply(e.target.value)} className="rounded-lg border border-gray-300 bg-white px-2 py-1.5 text-sm dark:border-gray-600 dark:bg-gray-800 dark:text-white" aria-label="Filter items by custom type">
      <option value="">All types</option>
      {types.map(type => <option key={type.id} value={type.id}>{type.name} ({type.count})</option>)}
    </select>
    {selected && <button type="button" onClick={() => apply('')} className="rounded p-1 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700" title="Clear item type filter" aria-label="Clear item type filter"><X size={16} /></button>}
  </div>
}
