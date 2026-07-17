import { useEffect, useState } from 'react'
import { api } from '../api'

export default function Calls() {
  const [calls, setCalls] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    api.listCalls()
      .then(setCalls)
      .catch((e) => setError(e.message))
    const t = setInterval(() => {
      api.listCalls().then(setCalls).catch(() => {})
    }, 5000)
    return () => clearInterval(t)
  }, [])

  return (
    <div>
      <header className="page-head">
        <div>
          <h1>Calls</h1>
          <p className="muted">Live and completed AI sessions</p>
        </div>
      </header>
      {error && <div className="alert">{error}</div>}
      <section className="panel">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Phone</th>
              <th>Campaign</th>
              <th>Status</th>
              <th>Transfer</th>
              <th>Variables</th>
              <th>Started</th>
            </tr>
          </thead>
          <tbody>
            {calls.map((c) => (
              <tr key={c.id}>
                <td>{c.id}</td>
                <td className="mono">{c.phone || '—'}</td>
                <td>{c.campaign || '—'}</td>
                <td><span className={`pill status-${c.status}`}>{c.status}</span></td>
                <td className="mono">{c.transfer_campaign || '—'}</td>
                <td className="mono small">{JSON.stringify(c.variables || {})}</td>
                <td>{new Date(c.started_at).toLocaleString()}</td>
              </tr>
            ))}
            {calls.length === 0 && (
              <tr><td colSpan="7" className="muted">No calls yet.</td></tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  )
}
