import { Link } from "react-router-dom";
import { useMemo, useState } from "react";
import { useSalesInvoices } from "../hooks/useSalesInvoices";
import { usePOSDetails } from "../hooks/usePOSProfile";
import { formatCurrency } from "../utils/currency";

const reports = [
  { title: "Sales Register", route: "sales-register", description: "Sales invoices, taxes and totals" },
  { title: "Item-wise Sales Register", route: "item-wise-sales-register", description: "Sales by item and invoice" },
  { title: "Sales Analytics", route: "sales-analytics", description: "Sales analysis over time" },
  { title: "Sales Invoice Trends", route: "sales-invoice-trends", description: "Invoice trends over time" },
];

export default function ReportsPage() {
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [search, setSearch] = useState("");
  const { posDetails, loading: profileLoading, error: profileError } = usePOSDetails();
  const { invoices, isLoading, isLoadingMore, totalLoaded, totalCount, error } = useSalesInvoices("", false, undefined, true);
  const rows = useMemo(() => {
    const grouped = new Map<string, { code: string; name: string; uom: string; quantity: number; amount: number }>();
    for (const invoice of invoices) {
      if (!posDetails?.company || invoice.company !== posDetails.company || !invoice.custom_pos_opening_entry) continue;
      if ((fromDate && invoice.date < fromDate) || (toDate && invoice.date > toDate)) continue;
      for (const item of invoice.items) {
        const code = item.item_code || "";
        const name = item.item_name || code;
        const uom = item.uom || "";
        if (search && !`${code} ${name}`.toLowerCase().includes(search.toLowerCase())) continue;
        const key = `${code}\u0000${uom}`;
        const row = grouped.get(key) || { code, name, uom, quantity: 0, amount: 0 };
        row.quantity += Number(item.qty) || 0;
        row.amount += Number((item as unknown as { base_net_amount?: number }).base_net_amount ?? (Number(item.rate) || 0) * (Number(item.qty) || 0));
        grouped.set(key, row);
      }
    }
    return Array.from(grouped.values()).sort((a, b) => b.amount - a.amount || a.code.localeCompare(b.code));
  }, [invoices, posDetails?.company, fromDate, toDate, search]);
  const loading = profileLoading || isLoading || (!error && (isLoadingMore || totalLoaded < totalCount));
  return <main className="min-h-screen bg-gray-50 dark:bg-gray-900 p-6 lg:ml-20 pb-24">
    <div className="max-w-6xl mx-auto space-y-5">
      <h1 className="text-2xl font-bold dark:text-white">Reports</h1>
      <section className="rounded-lg border bg-white dark:bg-gray-800 p-4 space-y-4">
        <div><h2 className="text-xl font-semibold dark:text-white">Item-wise POS Sales</h2>
          <p className="text-sm text-gray-500">Submitted POS invoices for {posDetails?.company || "the active company"}. Returns reduce quantities and amounts. Net sales are after discounts and before tax in {posDetails?.company_currency || "company currency"}.</p></div>
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="text-sm dark:text-white">From date<input type="date" value={fromDate} onChange={e => setFromDate(e.target.value)} className="block w-full mt-1 rounded border p-2 dark:bg-gray-700" /></label>
          <label className="text-sm dark:text-white">To date<input type="date" value={toDate} onChange={e => setToDate(e.target.value)} className="block w-full mt-1 rounded border p-2 dark:bg-gray-700" /></label>
          <label className="text-sm dark:text-white">Item<input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search code or name" className="block w-full mt-1 rounded border p-2 dark:bg-gray-700" /></label>
        </div>
        {error || profileError ? <p role="alert" className="text-red-600">Could not load report: {error || profileError}</p> : loading ? <p>Loading sales data ({totalLoaded} of {totalCount})...</p> : fromDate && toDate && fromDate > toDate ? <p className="text-red-600">From date must be before the to date.</p> : <div className="overflow-x-auto">
          <table className="w-full text-sm text-left dark:text-gray-200"><thead><tr className="border-b"><th className="p-2">Item Code</th><th className="p-2">Item Name</th><th className="p-2">UOM</th><th className="p-2 text-right">Quantity</th><th className="p-2 text-right">Sales Amount</th></tr></thead>
            <tbody>{rows.map(row => <tr key={`${row.code}-${row.uom}`} className="border-b"><td className="p-2">{row.code}</td><td className="p-2">{row.name}</td><td className="p-2">{row.uom}</td><td className="p-2 text-right">{row.quantity.toLocaleString(undefined, {maximumFractionDigits: 3})}</td><td className="p-2 text-right">{formatCurrency(row.amount, posDetails?.company_currency || "USD")}</td></tr>)}</tbody>
            <tfoot><tr className="font-semibold"><td colSpan={4} className="p-2">Total sales amount</td><td className="p-2 text-right">{formatCurrency(rows.reduce((sum, row) => sum + row.amount, 0), posDetails?.company_currency || "USD")}</td></tr></tfoot></table>
          {rows.length === 0 && <p className="p-4 text-gray-500">No item sales found for these filters.</p>}
        </div>}
      </section>
      <p className="text-gray-600 dark:text-gray-300">Open ERPNext reports and use their filters to choose a company, period and other criteria.</p>
      <div className="grid gap-3 sm:grid-cols-2">
        {reports.map(report => <a key={report.route} href={`/desk/query-report/${encodeURIComponent(report.title)}`} className="block rounded-lg border bg-white dark:bg-gray-800 p-4 hover:border-blue-500">
          <div className="font-semibold dark:text-white">{report.title}</div><div className="text-sm text-gray-500 mt-1">{report.description}</div>
        </a>)}
      </div>
      <div className="flex gap-4"><Link className="text-blue-600" to="/dashboard">Sales Dashboard</Link><Link className="text-blue-600" to="/invoice">Invoice History</Link><Link className="text-blue-600" to="/closing_shift">Closing Shift</Link></div>
    </div>
  </main>;
}
