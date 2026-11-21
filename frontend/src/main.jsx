import React, { useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'

const icon = (name) => ({ dashboard: '⌂', alert: '◉', history: '↶', source: '◈', chart: '▥', bell: '♧', close: '×', external: '↗', refresh: '↻', star: '☆' }[name])
const formatDate = (value) => value ? new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }).format(new Date(value)) : 'Until further notice'
const label = (value) => (value || 'notice').replaceAll('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase())
const routesOf = (notice) => (notice.routes || []).map(route => route.route_id).filter(Boolean)

async function fetchJson(path, options) {
  const response = await fetch(path, options)
  if (!response.ok) throw new Error(`Request failed (${response.status})`)
  return response.json()
}

function App() {
  const [notices, setNotices] = useState([])
  const [pagination, setPagination] = useState({ page: 1, pages: 1, total: 0 })
  const [summary, setSummary] = useState({})
  const [analytics, setAnalytics] = useState({})
  const [sources, setSources] = useState([])
  const [runs, setRuns] = useState([])
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [activeNav, setActiveNav] = useState('Dashboard')
  const [selected, setSelected] = useState(null)
  const [history, setHistory] = useState([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState('all')
  const [route, setRoute] = useState('')
  const [area, setArea] = useState('')
  const [type, setType] = useState('')
  const [page, setPage] = useState(1)
  const [watchlist, setWatchlist] = useState(() => JSON.parse(localStorage.getItem('tn-watchlist') || '{"routes":[],"areas":[],"stations":[]}'))
  const [readAlerts, setReadAlerts] = useState(() => JSON.parse(localStorage.getItem('tn-read-alerts') || '[]'))
  const [bellOpen, setBellOpen] = useState(false)
  const [sourceMessage, setSourceMessage] = useState('')

  const loadData = async (targetPage = page) => {
    setLoading(true); setError('')
    const params = new URLSearchParams({ page: targetPage, page_size: 20 })
    if (query.trim()) params.set('search', query.trim())
    if (filter !== 'all') params.set('status', filter)
    if (route.trim()) params.set('route', route.trim())
    if (area.trim()) params.set('area', area.trim())
    if (type) params.set('advisory_type', type)
    const results = await Promise.allSettled([
      fetchJson(`/api/advisories?${params}`), fetchJson('/api/dashboard/summary'),
      fetchJson('/api/sources'), fetchJson('/api/alerts'), fetchJson('/api/refresh-runs'),
      fetchJson('/api/analytics/summary')
    ])
    const [advisories, summaryResult, sourceResult, alertResult, runResult, analyticsResult] = results
    if (advisories.status === 'fulfilled') {
      setNotices(advisories.value.items || []); setPagination(advisories.value)
    } else setError('Unable to reach backend API. Ensure FastAPI is running.')
    if (summaryResult.status === 'fulfilled') setSummary(summaryResult.value || {})
    if (sourceResult.status === 'fulfilled') setSources(sourceResult.value || [])
    if (alertResult.status === 'fulfilled') setAlerts(alertResult.value || [])
    if (runResult.status === 'fulfilled') setRuns(runResult.value || [])
    if (analyticsResult.status === 'fulfilled') setAnalytics(analyticsResult.value || {})
    setLoading(false)
  }

  useEffect(() => { loadData(page) }, [page, filter, route, area, type])
  useEffect(() => { const timer = setTimeout(() => { if (page !== 1) setPage(1); else loadData(1) }, 350); return () => clearTimeout(timer) }, [query])
  useEffect(() => { localStorage.setItem('tn-watchlist', JSON.stringify(watchlist)) }, [watchlist])
  useEffect(() => { localStorage.setItem('tn-read-alerts', JSON.stringify(readAlerts)) }, [readAlerts])

  const unread = alerts.filter(alert => !alert.is_read && !readAlerts.includes(alert.alert_id)).length
  const toggleWatch = (kind, value) => setWatchlist(current => {
    const values = current[kind] || []
    return { ...current, [kind]: values.includes(value) ? values.filter(item => item !== value) : [...values, value] }
  })
  const openNotice = async (notice) => {
    setSelected(notice); setHistory([]); setHistoryLoading(true)
    try { setHistory(await fetchJson(`/api/advisories/${notice.notice_id}/history`)) } catch { setHistory([]) } finally { setHistoryLoading(false) }
  }
  const markRead = async (id) => {
    try { await fetchJson(`/api/alerts/${id}/read`, { method: 'POST' }) }
    catch (err) { setError(err.message); return }
    setReadAlerts(current => current.includes(id) ? current : [...current, id])
    setAlerts(current => current.map(alert => alert.alert_id === id ? { ...alert, is_read: true } : alert))
  }
  const markAllRead = async () => {
    try { await fetchJson('/api/alerts/read-all', { method: 'POST' }) }
    catch (err) { setError(err.message); return }
    setReadAlerts(alerts.map(alert => alert.alert_id))
    setAlerts(current => current.map(alert => ({ ...alert, is_read: true })))
  }
  const refreshSource = async (sourceId) => {
    setSourceMessage('Refreshing source…')
    try { await fetchJson(`/api/sources/${sourceId}/refresh`, { method: 'POST' }); setSourceMessage('Source refresh requested.'); loadData(page) }
    catch (err) { setSourceMessage(err.message) }
  }
  const exportCsv = async () => {
    const params = new URLSearchParams()
    if (query.trim()) params.set('search', query.trim())
    if (filter !== 'all') params.set('status', filter)
    if (route.trim()) params.set('route', route.trim())
    if (area.trim()) params.set('area', area.trim())
    if (type) params.set('advisory_type', type)
    try {
      const response = await fetch(`/api/advisories/export.csv?${params}`)
      if (!response.ok) throw new Error(`Request failed (${response.status})`)
      const csv = await response.text()
      if (csv.split('\n').length <= 1) { setError('There are no advisories to export.'); return }
      const link = document.createElement('a'); link.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
      link.download = 'tn-transport-advisories.csv'; link.click(); URL.revokeObjectURL(link.href)
    } catch (err) { setError(err.message) }
  }

  const content = activeNav === 'Sources'
    ? <SourcesView sources={sources} runs={runs} refreshSource={refreshSource} message={sourceMessage} />
    : activeNav === 'Analytics'
      ? <AnalyticsView summary={summary} analytics={analytics} sources={sources} />
      : activeNav === 'Change history'
        ? <HistoryView notices={notices} openNotice={openNotice} />
        : <DashboardView notices={notices} pagination={pagination} loading={loading} query={query} setQuery={setQuery} filter={filter} setFilter={setFilter} route={route} setRoute={setRoute} area={area} setArea={setArea} type={type} setType={setType} openNotice={openNotice} exportCsv={exportCsv} sources={sources} alerts={alerts} summary={summary} page={page} setPage={setPage} watchlist={watchlist} toggleWatch={toggleWatch} />

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark">TN</span><span>TN Transport<span>Tracker</span></span></div>
      <div className="workspace-label">TAMIL NADU STATE CONTROL CENTER</div>
      <nav>{[['Dashboard', 'dashboard'], ['Advisories', 'alert'], ['Change history', 'history'], ['Sources', 'source'], ['Analytics', 'chart']].map(([name, glyph]) =>
        <button className={activeNav === name ? 'nav-item active' : 'nav-item'} onClick={() => setActiveNav(name)} key={name}><span className="nav-icon">{icon(glyph)}</span>{name}{name === 'Advisories' && <b>{summary.active ?? 0}</b>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="user"><span className="avatar">AA</span><span><strong>Ashfaq Ahamed J</strong><small>Administrator</small></span></div></div>
    </aside>
    <main className="main">
      <header className="topbar"><button className="mobile-menu">☰</button><div className="crumb">Tamil Nadu Transport <span>/</span> {activeNav}</div>
        <div className="top-actions"><span className={`sync-dot ${summary.last_checked ? '' : 'unknown'}`}></span><span className="synced">{summary.last_checked ? `Last verified ${formatDate(summary.last_checked)}` : 'No verification yet'}</span>
          <div className="bell-wrap"><button className="bell" aria-label={`${unread} unread notifications`} onClick={() => setBellOpen(value => !value)}>{icon('bell')}{unread > 0 && <i>{unread > 9 ? '9+' : unread}</i>}</button>
            {bellOpen && <div className="notification-menu"><strong>Notifications</strong><button className="mark-read" onClick={markAllRead}>Mark all read</button>{alerts.length ? alerts.slice(0, 8).map(alert => <button className={`notification ${!readAlerts.includes(alert.alert_id) && !alert.is_read ? 'unread' : ''}`} key={alert.alert_id} onClick={() => { markRead(alert.alert_id); openNotice({ notice_id: alert.notice_id, title: alert.message, summary: alert.message, status: 'active' }) }}><b>{label(alert.event_type)}</b><span>{alert.message}</span><small>{formatDate(alert.created_at)}</small></button>) : <span className="empty-note">No notifications</span>}</div>}
          </div>
        </div>
      </header>
      <div className="content"><div className="intro"><div><p className="eyebrow">TAMIL NADU TRANSPORT & RAILWAYS</p><h1>Good morning, Venkat <span>✦</span></h1><p className="subheading">Official service updates across Tamil Nadu bus, metro and railway networks.</p></div><button className="refresh" onClick={() => loadData(page)}>{icon('refresh')} Refresh data</button></div>
        {error && <div className="notice-banner">ⓘ {error}</div>}{content}
      </div>
    </main>
    {selected && <DetailModal notice={selected} history={history} historyLoading={historyLoading} onClose={() => setSelected(null)} watchlist={watchlist} toggleWatch={toggleWatch} />}
  </div>
}

function DashboardView({ notices, pagination, loading, query, setQuery, filter, setFilter, route, setRoute, area, setArea, type, setType, openNotice, exportCsv, sources, alerts, summary, page, setPage, watchlist, toggleWatch }) {
  const active = summary.active ?? notices.filter(n => n.status === 'active').length
  return <><section className="stats"><Stat label="Active advisories" value={active} detail="Current status" tone="blue" /><Stat label="Scheduled" value={summary.scheduled ?? 0} detail="Future validity" tone="green" /><Stat label="Recently changed" value={summary.recently_changed ?? 0} detail="New revisions" tone="purple" /><Stat label="Expired" value={summary.expired ?? 0} detail="No longer active" tone="orange" /><Stat label="Sources attention" value={summary.sources_needing_attention ?? 0} detail={`${sources.length} monitored`} tone="red" /></section>
    <div className="section-heading"><div><h2>Latest advisories</h2><p>Search, filter and export official updates</p></div><button className="view-all" onClick={() => { setFilter('all'); setQuery(''); setRoute(''); setArea(''); setType('') }}>Clear filters ↺</button></div>
    <div className="controls"><div className="searchbox"><span>⌕</span><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search routes, areas, stations or notices…" aria-label="Search advisories" /></div><input className="filter-input" value={route} onChange={e => setRoute(e.target.value)} placeholder="Route" aria-label="Filter by route" /><input className="filter-input" value={area} onChange={e => setArea(e.target.value)} placeholder="Area" aria-label="Filter by area" /><select className="filter-input" value={type} onChange={e => setType(e.target.value)} aria-label="Filter by advisory type"><option value="">All types</option><option value="delay">Delay</option><option value="closure">Closure</option><option value="reroute">Reroute</option><option value="maintenance">Maintenance</option></select><button className="export-button" onClick={exportCsv}>↓ CSV</button></div>
    <div className="controls-secondary"><div className="filter-pills">{[['all', 'All'], ['active', 'Active'], ['scheduled', 'Scheduled'], ['resolved', 'Resolved'], ['expired', 'Expired']].map(([key, text]) => <button key={key} className={filter === key ? 'pill selected' : 'pill'} onClick={() => setFilter(key)}>{text}</button>)}</div><span className="result-count">{pagination.total ?? 0} results</span></div>
    {loading ? <div className="state-card"><span className="spinner"></span>Loading advisories…</div> : notices.length ? <div className="advisory-list">{notices.map(notice => <AdvisoryCard key={notice.notice_id} notice={notice} onClick={() => openNotice(notice)} watched={watchlist.routes.some(routeId => routesOf(notice).includes(routeId)) || (notice.area && watchlist.areas.includes(notice.area))} toggleWatch={toggleWatch} />)}</div> : <div className="state-card"><strong>No advisories found</strong><span>Try a different search or filter.</span></div>}
    <Pagination page={page} pages={pagination.pages || 1} setPage={setPage} />
    <div className="lower-grid"><section className="panel"><div className="panel-header"><div><h2>Source health</h2><p>Monitoring status across official sources</p></div></div>{sources.slice(0, 5).map(source => <SourceRow key={source.source_id} source={source} />)}</section><section className="panel activity"><div className="panel-header"><div><h2>Recent activity</h2><p>Latest tracked backend events</p></div></div><div className="timeline">{alerts.slice(0, 4).map(alert => <div key={alert.alert_id}><i className="timeline-dot blue"></i><span><strong>{label(alert.event_type)}</strong><small>{alert.message} · {formatDate(alert.created_at)}</small></span></div>)}</div></section></div></>
}

function Stat({ label: title, value, detail, tone }) { return <div className={`stat-card ${tone}`}><div className="stat-top"><span>{title}</span><span className="stat-icon">◒</span></div><strong>{value}</strong><small>{detail}</small></div> }
function AdvisoryCard({ notice, onClick, watched, toggleWatch }) { return <article className="advisory-card" onClick={onClick} tabIndex="0" onKeyDown={e => e.key === 'Enter' && onClick()}><div className="card-main"><div className="card-title-row"><span className={`status-dot ${notice.status === 'resolved' || notice.status === 'expired' ? 'resolved' : ''}`}></span><h3>{notice.title}</h3><span className="status-badge">{label(notice.status)}</span></div><p>{notice.summary || notice.full_text || 'No summary provided.'}</p><div className="meta"><span>{notice.area || 'Tamil Nadu Network'}</span><span>•</span><span>{formatDate(notice.published_at)}</span><span>•</span><span>{notice.agency_name || notice.source_name}</span></div></div><button className={`watch-button ${watched ? 'watched' : ''}`} aria-label="Toggle watch route" onClick={e => { e.stopPropagation(); const routeId = routesOf(notice)[0]; if (routeId) toggleWatch('routes', routeId); else if (notice.area) toggleWatch('areas', notice.area) }}>{watched ? '★' : '☆'}</button><span className="card-arrow">→</span></article> }
function SourceRow({ source, onRefresh }) { const fresh = source.freshness_status === 'fresh'; const statusLabel = { fresh: 'Fresh', overdue: 'Stale', error: 'Refresh failed', never: 'Not checked', disabled: 'Disabled' }[source.freshness_status] || 'Unknown'; return <div className="source-row"><span className="source-logo logo-0">{source.source_name?.charAt(0)}</span><span className="source-name"><strong>{source.source_name}</strong><small>{source.last_successful_at ? `Verified ${formatDate(source.last_successful_at)}` : source.last_error || 'Not checked yet'}</small></span><span className={`healthy ${fresh ? '' : 'unhealthy'}`}><i></i>{statusLabel}</span>{onRefresh && <button className="small-action" onClick={() => onRefresh(source.source_id)}>↻</button>}</div> }
function Pagination({ page, pages, setPage }) { return pages > 1 && <div className="pagination"><button disabled={page <= 1} onClick={() => setPage(page - 1)}>← Previous</button><span>Page {page} of {pages}</span><button disabled={page >= pages} onClick={() => setPage(page + 1)}>Next →</button></div> }
function SourcesView({ sources, runs, refreshSource, message }) { return <><div className="section-heading"><div><h2>Source monitoring</h2><p>Health, freshness and refresh history for every official source.</p></div></div>{message && <div className="notice-banner">{message}</div>}<div className="source-grid">{sources.map(source => <section className="panel" key={source.source_id}><div className="panel-header"><h2>{source.source_name}</h2><span className={`healthy ${source.last_error ? 'unhealthy' : ''}`}>{source.last_error ? 'Attention' : 'Healthy'}</span></div><p className="source-url">{source.source_url}</p><div className="source-details"><span><b>Agency</b>{source.agency_name}</span><span><b>Notices</b>{source.notice_count}</span><span><b>Interval</b>{source.refresh_interval_minutes} min</span><span><b>Last success</b>{formatDate(source.last_successful_at)}</span></div><button className="refresh" onClick={() => refreshSource(source.source_id)}>↻ Refresh source</button></section>)}</div><section className="panel run-history"><h2>Refresh history</h2>{runs.length ? runs.slice(0, 12).map(run => <div className="run-row" key={run.run_id}><span>{formatDate(run.started_at)}</span><strong>{label(run.outcome)}</strong><span>{run.notices_found} found · {run.notices_updated} updated</span></div>) : <p className="empty-note">No refresh runs yet.</p>}</section></> }
function AnalyticsView({ summary, analytics, sources }) { const counts = Object.entries(analytics.by_status || {}); const max = Math.max(...counts.map(([, count]) => count), 1); const types = Object.entries(analytics.by_type || {}); return <><div className="section-heading"><div><h2>Analytics</h2><p>Operational snapshot based on the latest backend data.</p></div></div><section className="analytics-grid">{[['Total advisories', analytics.total_advisories ?? 0], ['Active', summary.active ?? 0], ['Changed recently', summary.recently_changed ?? 0], ['Monitored sources', sources.length]].map(([name, value]) => <div className="metric" key={name}><span>{name}</span><strong>{value}</strong></div>)}</section><section className="panel chart-panel"><h2>Advisory status distribution</h2>{counts.map(([status, count]) => <div className="bar-row" key={status}><span>{label(status)}</span><div><i style={{ width: `${count / max * 100}%` }}></i></div><b>{count}</b></div>)}</section><section className="panel chart-panel"><h2>Advisories by type</h2>{types.length ? types.map(([type, count]) => <div className="bar-row" key={type}><span>{label(type)}</span><div><i style={{ width: `${count / Math.max(...types.map(([, value]) => value), 1) * 100}%` }}></i></div><b>{count}</b></div>) : <p className="empty-note">No advisory type data is available.</p>}</section></> }
function HistoryView({ notices, openNotice }) { return <><div className="section-heading"><div><h2>Change history</h2><p>Select an advisory to compare its revisions.</p></div></div><div className="history-list">{notices.filter(n => n.revision_id).map(notice => <button className="history-item" key={notice.notice_id} onClick={() => openNotice(notice)}><span className="timeline-dot purple"></span><span><strong>{notice.title}</strong><small>{notice.change_summary || 'Revision'} · Revision {notice.revision_id} · {formatDate(notice.last_confirmed_at)}</small></span><span>→</span></button>)}</div></> }
function DetailModal({ notice, history, historyLoading, onClose, watchlist, toggleWatch }) { const routes = routesOf(notice); return <div className="modal-backdrop" onClick={onClose}><section className="modal" onClick={e => e.stopPropagation()}><button className="modal-close" onClick={onClose}>{icon('close')}</button><div className="modal-kicker"><span className="status-dot"></span>{label(notice.status)} <span>•</span> {label(notice.advisory_type)}</div><h2>{notice.title}</h2><p className="modal-summary">{notice.summary || notice.full_text}</p><div className="watch-actions">{routes.map(route => <button key={route} className={watchlist.routes.includes(route) ? 'watch-chip active' : 'watch-chip'} onClick={() => toggleWatch('routes', route)}>☆ {route}</button>)}{notice.area && <button className={watchlist.areas.includes(notice.area) ? 'watch-chip active' : 'watch-chip'} onClick={() => toggleWatch('areas', notice.area)}>☆ {notice.area}</button>}</div><div className="detail-grid"><div><small>AREA</small><strong>{notice.area || 'Tamil Nadu Network'}</strong></div><div><small>PUBLISHED</small><strong>{formatDate(notice.published_at)}</strong></div><div><small>VALID UNTIL</small><strong>{formatDate(notice.valid_to)}</strong></div><div><small>SOURCE</small><strong>{notice.source_name || notice.agency_name}</strong></div></div><div className="modal-copy"><h3>Official advisory information</h3><p>{notice.full_text || notice.summary || 'No additional information is available.'}</p></div><div className="revision-box"><h3>Revision history</h3>{historyLoading ? <span>Loading revisions…</span> : history.length ? history.map(item => <details key={item.history_id}><summary>Revision {item.revision_number} · {formatDate(item.observed_at)} — {item.change_summary || 'Updated'}</summary><div className="comparison"><div><b>Previous</b><pre>{JSON.stringify(item.previous_snapshot, null, 2)}</pre></div><div><b>Current</b><pre>{JSON.stringify(item.current_snapshot, null, 2)}</pre></div></div></details>) : <span>No revision history available.</span>}</div><div className="modal-footer"><span>Verified from official portal</span><a href={notice.source_url || '#'} target="_blank" rel="noopener noreferrer">View original portal ↗</a></div></section></div> }

createRoot(document.getElementById('root')).render(<App />)
