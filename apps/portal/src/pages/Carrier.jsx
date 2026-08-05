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
          <p className="muted">
            IP-based carriers only — same as commercial AI bots.
            Vicidial never uses an HTTP webhook / Start Call URL.
            Configure carriers, remote agents, and virtual DIDs only.
          </p>
        </div>
      </header>

      <section className="panel">
        <h2>How it works</h2>
        <ol>
          {(cfg.vicidial_steps || []).map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ol>
        <ul>
          {(cfg.notes || []).map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
        {cfg.allowed_vicidial_ips?.length > 0 && (
          <p className="hint">Trusted Vicidial IPs: <span className="mono">{cfg.allowed_vicidial_ips.join(', ')}</span></p>
        )}
      </section>

      <section className="panel">
        <h2>AIBOTS IP trunk (no registration)</h2>
        <table>
          <tbody>
            <tr><th>Host</th><td className="mono">{cfg.sip_host}</td></tr>
            <tr><th>Port</th><td className="mono">{cfg.sip_port} UDP</td></tr>
            <tr><th>Mode</th><td className="mono">{cfg.mode || 'ip_carrier'}</td></tr>
            <tr><th>Codecs</th><td>ulaw / alaw</td></tr>
          </tbody>
        </table>
        <h3>SIP peer on VICIdial Asterisk (IP-based)</h3>
        <pre className="block mono">{cfg.vicidial_server_ip_peer || cfg.vicidial_server_ip_registration}</pre>
      </section>

      <section className="panel">
        <h2>1) AI Carrier — Admin → Carriers → Add</h2>
        <table>
          <tbody>
            <tr><th>Carrier / Account</th><td className="mono">{cfg.vicidial_carrier_account_entry}</td></tr>
            <tr><th>Protocol</th><td className="mono">{cfg.vicidial_carrier_protocol}</td></tr>
            <tr><th>Globals String</th><td className="mono">{cfg.vicidial_carrier_globals}</td></tr>
          </tbody>
        </table>
        <h3>Carrier dialplan (paste)</h3>
        <pre className="block mono">{cfg.vicidial_ai_carrier_dialplan}</pre>
        <p className="muted">
          Match <strong>Client-Id</strong> and <strong>User-Id</strong> to each bot in AIBOTS
          (Client ID + Remote Agent). Assign this carrier to your outbound campaign.
        </p>
      </section>

      <section className="panel">
        <h2>2) Virtual DIDs + closers</h2>
        <p>
          Create inbound DIDs on VICIdial (e.g. <span className="mono">106027001</span>) and route
          each to a closer in-group. Set the bot <strong>Transfer DID</strong> to that number.
          When the AI qualifies, AIBOTS dials that DID back into VICIdial → live agents.
        </p>
        <p className="muted">{cfg.closer_hint}</p>
      </section>

      <section className="panel">
        <h2>3) Optional — Ctransfer carrier (VICIdial-side prefixes)</h2>
        <pre className="block mono">{cfg.vicidial_transfer_carrier_dialplan}</pre>
      </section>

      <section className="panel">
        <h2>4) Remote agents</h2>
        <p>
          Create remote agents whose extensions match the dialplan User-Id
          (e.g. <span className="mono">27001</span>, <span className="mono">27016</span>)
          and set the same value on the bot as <strong>Remote Agent</strong>.
        </p>
      </section>

      <section className="panel">
        <h2>Firewall (AIBOTS server)</h2>
        <pre className="block mono">{fw}</pre>
      </section>
    </div>
  )
}
