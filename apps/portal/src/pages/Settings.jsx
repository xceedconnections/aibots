import { useEffect, useState } from 'react'
import { api } from '../api'

export default function Settings() {
  const [cfg, setCfg] = useState(null)
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')

  useEffect(() => {
    api.getSettings()
      .then(setCfg)
      .catch((e) => setError(e.message))
  }, [])

  async function save(e) {
    e.preventDefault()
    try {
      const updated = await api.updateSettings({
        public_ip: cfg.public_ip,
        aibots_sip_password: cfg.aibots_sip_password,
        vicidial_url: cfg.vicidial_url,
        vicidial_user: cfg.vicidial_user,
        default_transfer_did: cfg.default_transfer_did,
      })
      setCfg(updated)
      setMsg('Settings saved. Recreate Asterisk if PUBLIC_IP or SIP password changed.')
    } catch (err) {
      setError(err.message)
    }
  }

  if (!cfg) return <p className="muted">Loading settings…</p>

  return (
    <div>
      <header className="page-head">
        <div>
          <h1>Settings</h1>
          <p className="muted">Global AIBOTS + SIP defaults (CRM-style, like AI AMD)</p>
        </div>
      </header>

      {error && <div className="alert">{error}</div>}
      {msg && <div className="alert ok">{msg}</div>}

      <div className="settings-grid">
        <form className="panel" onSubmit={save}>
          <div className="panel-head"><h3>SIP / public network</h3></div>
          <label>
            Public IP (AIBOTS)
            <input value={cfg.public_ip || ''} onChange={(e) => setCfg({ ...cfg, public_ip: e.target.value })} />
          </label>
          <label>
            SIP password
            <input value={cfg.aibots_sip_password || ''} onChange={(e) => setCfg({ ...cfg, aibots_sip_password: e.target.value })} />
          </label>
          <label>
            SIP port
            <input value={cfg.sip_port} readOnly />
          </label>
          <label>
            Default transfer DID
            <input
              placeholder="106027001"
              value={cfg.default_transfer_did || ''}
              onChange={(e) => setCfg({ ...cfg, default_transfer_did: e.target.value })}
            />
          </label>
          <button className="btn primary" type="submit">Save settings</button>
        </form>

        <form className="panel" onSubmit={save}>
          <div className="panel-head"><h3>Default VICIdial API</h3></div>
          <label>
            VICIdial URL
            <input value={cfg.vicidial_url || ''} onChange={(e) => setCfg({ ...cfg, vicidial_url: e.target.value })} />
          </label>
          <label>
            API user
            <input value={cfg.vicidial_user || ''} onChange={(e) => setCfg({ ...cfg, vicidial_user: e.target.value })} />
          </label>
          <label>
            Admin email
            <input value={cfg.admin_email || ''} readOnly />
          </label>
          <p className="hint">API credentials are optional for carrier/DID mode. Used only for lead comment updates.</p>
          <button className="btn primary" type="submit">Save settings</button>
        </form>
      </div>

      <section className="panel">
        <div className="panel-head"><h3>Apply on server</h3></div>
        <pre className="block mono">{`# After changing PUBLIC_IP or SIP password:
sudo nano /opt/aibots/.env
# set PUBLIC_IP=... and AIBOTS_SIP_PASSWORD=...
cd /opt/aibots && sudo docker compose up -d --force-recreate asterisk`}</pre>
        <ul>
          {(cfg.notes || []).map((n) => <li key={n} className="hint">{n}</li>)}
        </ul>
      </section>
    </div>
  )
}
