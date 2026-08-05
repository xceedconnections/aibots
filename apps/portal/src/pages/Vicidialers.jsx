import { useEffect, useState } from 'react'
import { api } from '../api'

const empty = {
  name: '',
  host: '',
  sip_ip: '',
  api_url: '',
  api_user: '',
  api_pass: '',
  notes: '',
  active: true,
}

export default function Vicidialers() {
  const [rows, setRows] = useState([])
  const [carrier, setCarrier] = useState(null)
  const [form, setForm] = useState(empty)
  const [show, setShow] = useState(false)
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')
  const [peer, setPeer] = useState('')

  async function load() {
    try {
      const [list, cfg] = await Promise.all([api.listVicidialers(), api.carrierConfig()])
      setRows(list)
      setCarrier(cfg)
      setPeer(cfg.vicidial_server_ip_peer || cfg.vicidial_server_ip_registration || '')
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => { load() }, [])

  async function create(e) {
    e.preventDefault()
    try {
      const created = await api.createVicidialer({
        ...form,
        sip_ip: form.sip_ip || form.host,
        api_url: form.api_url || '',
      })
      setShow(false)
      setForm(empty)
      setMsg(`Added ${created.name}. Asterisk IP allow-list updated (no registration).`)
      if (created.aibots_peer_snippet) setPeer(created.aibots_peer_snippet)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  async function remove(id) {
    if (!confirm('Remove this VICIdial server IP?')) return
    await api.deleteVicidialer(id)
    setMsg('Removed. Asterisk IP allow-list rebuilt.')
    await load()
  }

  async function toggle(row) {
    await api.updateVicidialer(row.id, { active: !row.active })
    await load()
  }

  async function sync() {
    try {
      await api.syncVicidialersAsterisk()
      setMsg('Asterisk IP identify file synced.')
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div>
      <header className="page-head">
        <div>
          <h1>VICIdial Servers</h1>
          <p className="muted">
            Add dialers anytime after install — IP-based trunks only (no SIP registration)
          </p>
        </div>
        <div className="row gap">
          <button className="btn ghost" type="button" onClick={sync}>Sync Asterisk</button>
          <button className="btn primary" type="button" onClick={() => setShow(true)}>Add server</button>
        </div>
      </header>

      {error && <div className="alert">{error}</div>}
      {msg && <div className="alert ok">{msg}</div>}

      <section className="panel">
        <div className="panel-head"><h3>Registered dialers (by IP)</h3></div>
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Host</th>
              <th>SIP IP (trusted)</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{r.name}</td>
                <td className="mono">{r.host}</td>
                <td className="mono">{r.sip_ip || r.host}</td>
                <td><span className={`pill ${r.active ? 'ok' : 'off'}`}>{r.active ? 'Active' : 'Off'}</span></td>
                <td className="row gap">
                  <button type="button" className="btn ghost" onClick={() => toggle(r)}>{r.active ? 'Pause' : 'Enable'}</button>
                  <button type="button" className="btn danger" onClick={() => remove(r.id)}>Delete</button>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={5} className="muted">
                  No dialers yet. Install is done — click <strong>Add server</strong> and enter each Vicidial public IP.
                </td>
              </tr>
            )}
          </tbody>
        </table>
        {carrier?.allowed_vicidial_ips?.length > 0 && (
          <p className="hint">Asterisk currently allows: {carrier.allowed_vicidial_ips.join(', ')}</p>
        )}
      </section>

      <section className="panel">
        <div className="panel-head"><h3>Firewall</h3></div>
        <p>
          Asterisk SIP <span className="mono">5060</span> and RTP{" "}
          <span className="mono">10000–10100</span> accept traffic only from IPs listed above.
          Internet SIP scanners are dropped. Add each Vicidial public IP here, then wait ~10s
          (or click Sync Asterisk).
        </p>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h3>Vicidial Asterisk IP peer (paste on each dialer)</h3>
          <span className="muted">No register =&gt; line</span>
        </div>
        <pre className="block mono">{peer}</pre>
        <p className="hint">
          Carrier Globals: <span className="mono">SIP/aibots@{carrier?.public_ip || 'AIBOTS_IP'}</span>
          {' '}· then use Portal → SIP Carrier for full dialplan.
        </p>
      </section>

      {show && (
        <div className="modal-backdrop" onClick={() => setShow(false)}>
          <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={create}>
            <h2>Add VICIdial server (IP)</h2>
            <p className="hint">Only the SIP IP is required for call routing. API fields are optional.</p>
            <label>
              Display name
              <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Vicibox-1" />
            </label>
            <label>
              Host / IP
              <input required value={form.host} onChange={(e) => setForm({ ...form, host: e.target.value })} placeholder="62.238.46.190" />
            </label>
            <label>
              SIP IP (if different)
              <input value={form.sip_ip} onChange={(e) => setForm({ ...form, sip_ip: e.target.value })} placeholder="same as host if blank" />
            </label>
            <label>
              Notes
              <input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
            </label>
            <div className="row gap">
              <button type="button" className="btn ghost" onClick={() => setShow(false)}>Cancel</button>
              <button className="btn primary" type="submit">Save IP peer</button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
