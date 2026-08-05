import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'

export default function Campaigns() {
  const [rows, setRows] = useState([])
  const [error, setError] = useState('')
  const [open, setOpen] = useState(null)

  useEffect(() => {
    api.listCampaigns()
      .then(setRows)
      .catch((e) => setError(e.message))
  }, [])

  return (
    <div>
      <header className="page-head">
        <div>
          <h1>Campaigns</h1>
          <p className="muted">AI agents mapped to VICIdial campaigns — copy dialplan per campaign</p>
        </div>
        <Link className="btn primary" to="/bots">Manage bots</Link>
      </header>

      {error && <div className="alert">{error}</div>}

      <section className="panel">
        <div className="panel-head"><h3>AI campaigns</h3></div>
        <table>
          <thead>
            <tr>
              <th>Bot</th>
              <th>Campaign</th>
              <th>Client ID</th>
              <th>Remote Agent</th>
              <th>Transfer DID</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.bot_id}>
                <td>{r.name}</td>
                <td className="mono">{r.campaign}</td>
                <td className="mono">{r.client_id || '—'}</td>
                <td className="mono">{r.remote_agent || '—'}</td>
                <td className="mono">{r.transfer_did || '—'}</td>
                <td><span className={`pill ${r.active ? 'ok' : 'off'}`}>{r.active ? 'Active' : 'Paused'}</span></td>
                <td className="row gap">
                  <button type="button" className="btn ghost" onClick={() => setOpen(open === r.bot_id ? null : r.bot_id)}>
                    Dialplan
                  </button>
                  <Link className="btn" to={`/bots/${r.bot_id}`}>Edit</Link>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={7} className="muted">No bots yet — create one under Bots / Scripts.</td></tr>
            )}
          </tbody>
        </table>
      </section>

      {rows.filter((r) => open === r.bot_id).map((r) => (
        <section className="panel" key={`dp-${r.bot_id}`}>
          <div className="panel-head">
            <h3>Carrier dialplan — {r.name}</h3>
            <span className="muted">Paste into VICIdial Admin → Carriers → AI carrier</span>
          </div>
          <pre className="block mono">{r.dialplan_snippet}</pre>
        </section>
      ))}
    </div>
  )
}
