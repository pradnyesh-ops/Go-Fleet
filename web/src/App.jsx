import { useEffect, useEffectEvent, useState } from 'react'
import { Activity, AlertTriangle, Bell, Box, Check, ChevronDown, CircleAlert, Clock3, Fuel, Gauge, LockKeyhole, MapPin, MoreHorizontal, Radio, RefreshCw, Route, ShieldCheck, Truck, Unlock, Users, X } from 'lucide-react'
import './App.css'

const apiBaseUrl = import.meta.env.VITE_DASHBOARD_API_URL
const domains = {
  rental: { label: 'Rental operations', location: 'Dublin rental zone', activeLabel: 'Active rentals', workflow: 'Rental return protection', detail: 'Geo-lock a vehicle before collection or return to capture out-of-zone events.', lock: 'Set return zone' },
  fleet: { label: 'Fleet operations', location: 'Ireland route network', activeLabel: 'Vehicles en route', workflow: 'Route and driver compliance', detail: 'Monitor route adherence and driver behaviour against the assigned shift.', lock: 'Set route corridor' },
  industrial: { label: 'Industrial operations', location: 'North site perimeter', activeLabel: 'Assets operating', workflow: 'Site safety control', detail: 'Apply site-zone constraints and track load conditions for the selected asset.', lock: 'Set safety zone' },
}
const vehicles = [
  ['RNT-1001', 'rental'], ['RNT-1002', 'rental'], ['RNT-1003', 'rental'], ['RNT-1004', 'rental'],
  ['FLT-2001', 'fleet'], ['FLT-2002', 'fleet'], ['FLT-2003', 'fleet'], ['FLT-2004', 'fleet'],
  ['IND-3001', 'industrial'], ['IND-3002', 'industrial'], ['IND-3003', 'industrial'], ['IND-3004', 'industrial'],
].map(([id, domain], index) => ({ id, domain, x: 18 + (index % 4) * 23, y: 25 + (Math.floor(index / 4) % 3) * 24, color: domain === 'rental' ? 'teal' : domain === 'fleet' ? 'amber' : 'blue' }))
const categoryIcons = { usage: Route, behaviour: AlertTriangle, health: CircleAlert, load: Box, compliance: ShieldCheck, efficiency: Fuel }

function Metric({ icon: Icon, label, value, note, tone = 'teal' }) {
  return <article className={`metric-card metric-${tone}`}><div className="metric-top"><span>{label}</span><Icon size={18} /></div><strong>{value}</strong><p>{note}</p></article>
}
function relativeTime(timestamp) {
  if (!timestamp) return 'Awaiting data'
  const minutes = Math.round((new Date(timestamp) - new Date()) / 60000)
  return new Intl.RelativeTimeFormat('en', { numeric: 'auto' }).format(minutes, 'minute')
}

export default function App() {
  const [domain, setDomain] = useState('rental')
  const [selectedId, setSelectedId] = useState('RNT-1001')
  const [records, setRecords] = useState({})
  const [locks, setLocks] = useState({})
  const [allEvents, setAllEvents] = useState(false)
  const [updated, setUpdated] = useState(null)
  const [refreshing, setRefreshing] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)

  const current = domains[domain]
  const visible = vehicles.filter((vehicle) => vehicle.domain === domain)
  const selected = vehicles.find((vehicle) => vehicle.id === selectedId) || visible[0]
  const selectedRecord = records[selected.id] || {}
  const latest = selectedRecord.latest || {}
  const history = selectedRecord.items || []
  const isLocked = Boolean(locks[selected.id])

  const loadVehicle = useEffectEvent(async (vehicleId, includeHistory = false) => {
    if (!apiBaseUrl) return
    const latestResponse = await fetch(`${apiBaseUrl}/vehicles/${vehicleId}/latest`)
    if (!latestResponse.ok) throw new Error('Cloud telemetry is unavailable')
    const currentState = await latestResponse.json()
    let eventHistory = records[vehicleId]?.items || []
    if (includeHistory) {
      const historyResponse = await fetch(`${apiBaseUrl}/vehicles/${vehicleId}`)
      if (!historyResponse.ok) throw new Error('Cloud telemetry is unavailable')
      eventHistory = (await historyResponse.json()).items || []
    }
    setRecords((previous) => ({ ...previous, [vehicleId]: { items: eventHistory, latest: currentState || {} } }))
  })
  const refresh = useEffectEvent(async () => {
    setRefreshing(true)
    setLoadError('')
    try {
      await Promise.all(visible.map((vehicle) => loadVehicle(vehicle.id, vehicle.id === selectedId)))
      setUpdated(new Date())
    } catch (error) {
      setLoadError(error.message)
    } finally {
      setRefreshing(false)
    }
  })
  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 30000)
    return () => clearInterval(interval)
  }, [refreshKey])
  useEffect(() => {
    loadVehicle(selectedId, true).catch((error) => setLoadError(error.message))
  }, [selectedId])
  const selectDomain = (nextDomain) => {
    setDomain(nextDomain)
    setSelectedId(vehicles.find((vehicle) => vehicle.domain === nextDomain).id)
    setRefreshKey((value) => value + 1)
  }
  const requestRefresh = () => setRefreshKey((value) => value + 1)
  const toggleLock = () => setLocks((previous) => ({ ...previous, [selected.id]: !previous[selected.id] }))
  const eventRows = history.slice(0, allEvents ? 50 : 5)
  const highSeverity = history.filter((event) => event.anomaly_score > 0.8).length

  return <main className="app-shell">
    <header className="topbar"><a className="brand" href="#overview"><span className="brand-mark"><Radio size={19} /></span><span>FLEET<span>INTEL</span></span></a><div className="topbar-actions"><span className="live-pill"><i /> AWS live data</span><button className="icon-button" aria-label="Notifications"><Bell size={19} /></button><button className="avatar">PM</button></div></header>
    <div className="workspace"><aside className="sidebar"><nav><a className="nav-item active" href="#overview"><Gauge size={18} />Overview</a><a className="nav-item" href="#map"><MapPin size={18} />Live map</a><a className="nav-item" href="#events"><Activity size={18} />Event stream</a><a className="nav-item" href="#safety"><ShieldCheck size={18} />Safety & compliance</a></nav><div className="sidebar-footer"><span className="section-label">Data pipeline</span><div className="pipeline-status"><i /><span>Cloud simulator</span><strong>12 assets</strong></div><div className="pipeline-status"><i /><span>Refresh interval</span><strong>30s</strong></div></div></aside>
      <section className="content" id="overview"><div className="page-heading"><div><p className="eyebrow">Multi-domain vehicle intelligence</p><h1>{current.label}</h1><p className="muted"><MapPin size={15} /> {current.location} <span className="dot-divider">•</span> {loadError || (updated ? `Updated ${relativeTime(updated)}` : 'Connecting to AWS')}</p></div><div className="heading-actions"><div className="domain-switcher">{Object.keys(domains).map((key) => <button key={key} className={domain === key ? 'selected' : ''} onClick={() => selectDomain(key)}>{key}</button>)}</div><button className="refresh-button" onClick={requestRefresh}><RefreshCw className={refreshing ? 'spinning' : ''} size={17} />Refresh</button></div></div>
        <section className="metrics-grid"><Metric icon={Truck} label={current.activeLabel} value={visible.length} note="Cloud-simulated assets" /><Metric icon={AlertTriangle} label="High-severity alerts" value={highSeverity} note="Selected asset history" tone="amber" /><Metric icon={Users} label="Connected assets" value="12" note="Across all operating domains" tone="blue" /><Metric icon={Gauge} label="Latest signal" value={latest.timestamp ? 'Live' : 'Waiting'} note={latest.timestamp ? relativeTime(latest.timestamp) : 'Simulator is starting'} tone="green" /></section>
        <section className="dashboard-grid"><article className="map-panel" id="map"><div className="panel-header"><div><h2>Live vehicle map</h2><p>Cloud simulator positions by operating domain</p></div><span className="map-count">{visible.length} online</span></div><div className="map-canvas"><i className="road road-one" /><i className="road road-two" /><i className="road road-three" /><span className="zone-label zone-one">ACTIVE ZONE</span><span className="zone-label zone-two">TELEMETRY GRID</span>{visible.map((vehicle) => <button key={vehicle.id} title={vehicle.id} className={`vehicle-pin pin-${vehicle.color} ${vehicle.id === selected.id ? 'is-selected' : ''}`} style={{ left: `${vehicle.x}%`, top: `${vehicle.y}%` }} onClick={() => setSelectedId(vehicle.id)}><Truck size={15} /></button>)}<div className="map-legend"><span><i className="legend teal" />Rental</span><span><i className="legend amber" />Fleet</span><span><i className="legend blue" />Industrial</span></div></div><div className="vehicle-list">{visible.map((vehicle) => { const state = records[vehicle.id]?.latest || {}; return <button key={vehicle.id} className={`vehicle-row ${vehicle.id === selected.id ? 'row-selected' : ''}`} onClick={() => setSelectedId(vehicle.id)}><i className={`status-dot ${vehicle.color}`} /><strong>{vehicle.id}</strong><span>{state.sensor_type?.replace('_', ' ') || 'Awaiting signal'}</span><span>{state.sensor_data?.speed_kmh ?? '—'} km/h</span><span>{relativeTime(state.timestamp)}</span></button> })}</div></article>
          <aside className="alert-panel"><div className="panel-header"><div><h2>Selected asset</h2><p>Latest cloud telemetry</p></div><button className="more-button" aria-label="More options"><MoreHorizontal size={18} /></button></div><div className="vehicle-detail"><span className={`detail-icon pin-${selected.color}`}><Truck size={16} /></span><div><strong>{selected.id}</strong><p>{latest.sensor_type?.replace('_', ' ') || 'Awaiting simulator event'}</p></div><button className="close-selection" onClick={() => setSelectedId(visible[0].id)} aria-label="Reset selection"><X size={16} /></button></div><dl className="telemetry-grid"><div><dt>Speed</dt><dd>{latest.sensor_data?.speed_kmh ?? '—'} <small>km/h</small></dd></div><div><dt>Fuel</dt><dd>{latest.sensor_data?.fuel_level_pct ?? '—'} <small>%</small></dd></div><div><dt>Signal</dt><dd>{latest.timestamp ? relativeTime(latest.timestamp) : 'Waiting'}</dd></div></dl><div className={`lock-status ${isLocked ? 'locked' : ''}`}>{isLocked ? <LockKeyhole size={15} /> : <Unlock size={15} />}{isLocked ? 'Geo-lock active for selected asset' : 'Geo-lock is not active'}</div><button className={`primary-action ${isLocked ? 'release' : ''}`} onClick={toggleLock}>{isLocked ? <><Unlock size={15} />Release lock</> : <><LockKeyhole size={15} />{current.lock}</>}</button><p className="action-note">{current.detail}</p><div className="queue-stats"><div><span>Events received</span><strong>{history.length}</strong></div><div><span>Alert score</span><strong>{latest.anomaly_score ?? '0.0'}</strong></div></div><div className="alert-footer"><Check size={14} /> Cloud pipeline connected</div></aside></section>
        <section className="events-panel" id="events"><div className="panel-header"><div><h2>Live event stream</h2><p>{selected.id} event history from AWS</p></div><button className="text-button" onClick={() => setAllEvents((value) => !value)}>{allEvents ? 'Show recent' : 'View all'} <ChevronDown size={14} /></button></div><div className="event-table">{eventRows.length ? eventRows.map((event) => { const Icon = categoryIcons[event.payload?.data_category] || Activity; const tone = event.anomaly_score > 0.8 ? 'critical' : event.anomaly_score > 0.3 ? 'warn' : 'good'; return <div className="event-row" key={event.event_id}><span className={`event-icon ${tone}`}><Icon size={15} /></span><div><strong>{event.sensor_type.replace('_', ' ')}</strong><p>{event.payload?.data_category || 'telemetry'} · anomaly score {event.anomaly_score}</p></div><time><Clock3 size={12} />{relativeTime(event.payload?.timestamp)}</time></div> }) : <div className="event-row"><span className="event-icon good"><Activity size={15} /></span><div><strong>Awaiting telemetry</strong><p>The AWS simulator publishes fresh events every minute.</p></div><time><Clock3 size={12} />Live</time></div>}</div></section>
        <section className="domain-action-panel" id="safety"><div><p className="eyebrow">Domain control</p><h2>{current.workflow}</h2><p>{current.detail}</p></div><button onClick={toggleLock}>{isLocked ? 'Release selected lock' : current.lock}</button></section>
      </section></div><footer><span><Radio size={12} /> CloudFront dashboard · API Gateway telemetry</span><span>{updated ? `Last refresh ${updated.toLocaleTimeString()}` : 'Connecting'}</span></footer>
  </main>
}
