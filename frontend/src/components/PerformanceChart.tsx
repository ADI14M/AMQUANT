import { useState } from 'react'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

const ranges = ['1W', '1M', '3M', '6M', '1Y', 'ALL'] as const
type Range = typeof ranges[number]
const base = [42, 43, 41, 46, 44, 48, 47, 51, 49, 52, 50, 55, 53, 58, 56, 60, 58, 63, 61, 66, 64, 69, 67, 72, 70, 75, 73, 78, 76, 82, 79]
const dataByRange: Record<Range, number[]> = {
  '1W': base.slice(-8), '1M': base.slice(-16), '3M': base.slice(-24), '6M': base, '1Y': [...base, 84, 81, 86, 83, 88, 86, 91, 88, 94, 91, 96, 94, 99, 97, 103, 100, 105, 103, 108, 106, 111, 108, 114, 110], 'ALL': [...base, 83, 86, 82, 89, 91, 88, 95, 92, 99, 97, 102, 99, 106, 103, 111, 108, 114, 110, 119, 116, 124, 120, 128, 125, 133, 130, 138, 135, 142, 139],
}
const labels: Record<Range, string[]> = { '1W': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun', 'Today'], '1M': ['Oct 14', 'Oct 16', 'Oct 18', 'Oct 20', 'Oct 22', 'Oct 24', 'Oct 26', 'Oct 28'], '3M': ['Aug 12', 'Aug 24', 'Sep 05', 'Sep 17', 'Sep 29', 'Oct 11', 'Oct 23', 'Nov 04'], '6M': ['Jun 04', 'Jun 28', 'Jul 22', 'Aug 15', 'Sep 08', 'Oct 02', 'Oct 26', 'Nov 10'], '1Y': ['Nov 25', 'Jan 26', 'Mar 26', 'May 26', 'Jul 26', 'Sep 26', 'Oct 26', 'Nov 26'], 'ALL': ['2023', 'Mar 24', 'Jul 24', 'Nov 24', 'Mar 25', 'Jul 25', 'Mar 26', 'Nov 26'] }

export default function PerformanceChart() {
  const [range, setRange] = useState<Range>('6M')
  const values = dataByRange[range]
  const data = values.map((value, index) => ({ day: index, value, label: labels[range][Math.round(index / Math.max(values.length - 1, 1) * (labels[range].length - 1))] }))
  return <section className="panel performance-panel">
    <div className="panel-heading"><div><div className="eyebrow">PORTFOLIO SIMULATION <span className="synthetic-pill"><i/> SYNTHETIC</span></div><h2>Strategy performance</h2><p>Illustrative simulation · not market data</p></div><div className="range-switch" aria-label="Chart time range">{ranges.map(item => <button key={item} aria-pressed={range === item} className={range === item ? 'selected' : ''} onClick={() => setRange(item)}>{item}</button>)}</div></div>
    <div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><AreaChart data={data} margin={{ top: 12, right: 7, left: 0, bottom: 0 }}><defs><linearGradient id="equityFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#20c997" stopOpacity={0.22}/><stop offset="100%" stopColor="#20c997" stopOpacity={0}/></linearGradient></defs><CartesianGrid stroke="#1b2531" vertical={false}/><XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fill: '#6e7d8f', fontSize: 10 }} interval={Math.max(Math.floor(data.length / 7), 1)}/><YAxis tickLine={false} axisLine={false} tick={{ fill: '#6e7d8f', fontSize: 10 }} tickFormatter={v => `$${v}k`} domain={['dataMin - 5', 'dataMax + 8']} width={48}/><Tooltip contentStyle={{ background: '#101721', border: '1px solid #263342', borderRadius: 8, fontSize: 12 }} labelFormatter={(label) => String(label ?? '')} formatter={(value) => [`$${Number(value).toFixed(1)}k`, 'Simulated value']}/><Area type="monotone" dataKey="value" stroke="#27d3a2" strokeWidth={2} fill="url(#equityFill)" activeDot={{ r: 4, fill: '#27d3a2', stroke: '#0b1117', strokeWidth: 2 }}/></AreaChart></ResponsiveContainer></div>
    <div className="chart-foot"><span><i className="legend-dot"/> Strategy A</span><span><i className="legend-dash"/> Benchmark</span><span className="chart-foot-note">Illustrative values · generated locally</span></div>
  </section>
}
