import { useEffect, useState } from 'react'
import { api } from '../api'

export default function Carrier() {
  const [cfg, setCfg] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.carrierConfig()
      .then(setCfg)
      .catch((e) => setError(e.message))
  }, [])

  if (error) return <div className="alert">{error}</div>
  if (!cfg) return <p className="muted">Loading carrier settings…</p>

  const fw = `sudo ufw allow from ${cfg.vicidial_ip} to any port 5060 proto udp
sudo ufw allow from ${cfg.vicidial_ip} to any port 10000:10100 proto udp
sudo ufw reload`

  return (
    <div>
      <header className="page-head">
        <div>
          <h1>SIP Carrier</h1>
          <p className="muted">Vendor-style VICIdial integration — carrier only</p>
        </div>
      </header>

      <section className="panel">
        <h2>How it works</h2>
        <p>
          VICIdial dials through an <strong>AIBOTS SIP carrier</strong>. Audio lands on this server,
          the AI qualifies the lead, then transfers to your closer campaign — same pattern as commercial AI bots.
        </p>
        <ul>
          {(cfg.notes || []).map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      </section>

      <section className="panel">
        <h2>AIBOTS SIP trunk</h2>
        <table>
          <tbody>
            <tr><th>Host</th><td className="mono">{cfg.sip_host}</td></tr>
            <tr><th>Port</th><td className="mono">{cfg.sip_port} UDP</td></tr>
            <tr><th>Username</th><td className="mono">{cfg.sip_username}</td></tr>
            <tr><th>Password</th><td className="mono">{cfg.sip_password}</td></tr>
            <tr><th>Codecs</th><td>ulaw / alaw</td></tr>
          </tbody>
        </table>
      </section>

      <section className="panel">
        <h2>VICIdial → Admin → Carriers → Add</h2>
        <table>
          <tbody>
            <tr><th>Carrier / Account</th><td className="mono">{cfg.vicidial_carrier_account_entry}</td></tr>
            <tr><th>Protocol</th><td className="mono">{cfg.vicidial_carrier_protocol}</td></tr>
            <tr><th>Globals String</th><td className="mono">{cfg.vicidial_carrier_globals}</td></tr>
          </tbody>
        </table>
        <h3>SIP peer details</h3>
        <pre className="block mono">{cfg.vicidial_server_ip_registration}</pre>
        <h3>Dial string</h3>
        <pre className="block mono">{cfg.vicidial_carrier_dialplan}</pre>
      </section>

      <section className="panel">
        <h2>Campaign mapping</h2>
        <p>
          In <strong>Bots</strong>, set Campaign to your VICIdial campaign id and Transfer campaign
          to your closer / in-group. Assign the AIBOTS carrier to that outbound campaign.
        </p>
        <p className="muted">{cfg.closer_hint}</p>
      </section>

      <section className="panel">
        <h2>Firewall (AIBOTS server)</h2>
        <pre className="block mono">{fw}</pre>
      </section>
    </div>
  )
}
