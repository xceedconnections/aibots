import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [calls, setCalls] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([api.stats(), api.recentCalls()])
      .then(([s, c]) => {
        setStats(s)
        setCalls(c)
      })
      .catch((e) => setError(e.message))
  }, [])

  if (error) return <div className="alert">{error}</div>
  if (!stats) return <p className="muted">Loading dashboard…</p>

  const cards = [
    { label: 'Active bots', value: stats.bots_active },
    { label: 'Calls today', value: stats.calls_today },
    { label: 'Transfers', value: stats.transfers_today },
    { label: 'Qualified', value: stats.qualified_today },
    { label: 'Rejected', value: stats.rejected_today },
    { label: 'Qual rate', value: `${stats.qualification_rate}%` },
    { label: 'Avg duration', value: `${Math.round(stats.avg_duration_seconds)}s` },
  ]

  return (
    <div>
      <header className="page-head">
        <div>
          <h1>Dashboard</h1>
          <p className="muted">Live qualification and transfer performance</p>
        </div>
        <Link className="btn primary" to="/bots">Manage bots</Link>
      </header>

      <div className="stat-grid">
        {cards.map((c) => (
          <div key={c.label} className="stat">
            <span>{c.label}</span>
            <strong>{c.value}</strong>
          </div>
        ))}
      </div>

      <section className="panel">
        <h2>Recent calls</h2>
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Phone</th>
              <th>Campaign</th>
              <th>Status</th>
              <th>Started</th>
            </tr>
          </thead>
          <tbody>
            {calls.length === 0 && (
              <tr><td colSpan="5" className="muted">No calls yet. Trigger a test from a bot.</td></tr>
            )}
            {calls.map((c) => (
              <tr key={c.id}>
                <td>{c.id}</td>
                <td className="mono">{c.phone || '—'}</td>
                <td>{c.campaign || '—'}</td>
                <td><span className={`pill status-${c.status}`}>{c.status}</span></td>
                <td>{new Date(c.started_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  )
}
