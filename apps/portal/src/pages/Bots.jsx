import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'

const empty = {
  name: '',
  campaign: '',
  transfer_campaign: '',
  language: 'en',
  voice: 'en_US-lessac-medium',
  model: 'qwen2.5:7b-instruct',
  temperature: 0.2,
  greeting: 'Hello, thank you for taking our call.',
  active: true,
  description: '',
}

export default function Bots() {
  const [bots, setBots] = useState([])
  const [show, setShow] = useState(false)
  const [form, setForm] = useState(empty)
  const [error, setError] = useState('')
  const nav = useNavigate()

  async function load() {
    try {
      setBots(await api.listBots())
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => { load() }, [])

  async function create(e) {
    e.preventDefault()
    try {
      const bot = await api.createBot(form)
      setShow(false)
      setForm(empty)
      nav(`/bots/${bot.id}`)
    } catch (err) {
      setError(err.message)
    }
  }

  async function clone(id) {
    const bot = await api.cloneBot(id)
    await load()
    nav(`/bots/${bot.id}`)
  }

  async function toggle(bot) {
    await api.updateBot(bot.id, { active: !bot.active })
    await load()
  }

  async function remove(id) {
    if (!confirm('Delete this bot and its script?')) return
    await api.deleteBot(id)
    await load()
  }

  return (
    <div>
      <header className="page-head">
        <div>
          <h1>Bots</h1>
          <p className="muted">Create AI agents mapped to VICIdial campaigns</p>
        </div>
        <button className="btn primary" onClick={() => setShow(true)}>New bot</button>
      </header>

      {error && <div className="alert">{error}</div>}

      <div className="bot-grid">
        {bots.map((b) => (
          <article key={b.id} className="bot-card">
            <div className="bot-card-top">
              <h3>{b.name}</h3>
              <span className={`pill ${b.active ? 'ok' : 'off'}`}>{b.active ? 'Active' : 'Paused'}</span>
            </div>
            <p className="mono">{b.campaign} → {b.transfer_campaign}</p>
            <p className="muted">{b.language} · {b.voice}</p>
            <div className="row gap">
              <Link className="btn" to={`/bots/${b.id}`}>Edit script</Link>
              <button className="btn ghost" onClick={() => toggle(b)}>{b.active ? 'Pause' : 'Activate'}</button>
              <button className="btn ghost" onClick={() => clone(b.id)}>Clone</button>
              <button className="btn danger" onClick={() => remove(b.id)}>Delete</button>
            </div>
          </article>
        ))}
        {bots.length === 0 && <p className="muted">No bots yet.</p>}
      </div>

      {show && (
        <div className="modal-backdrop" onClick={() => setShow(false)}>
          <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={create}>
            <h2>Create bot</h2>
            {[
              ['name', 'Bot name'],
              ['campaign', 'VICIdial campaign'],
              ['transfer_campaign', 'Closer / transfer campaign'],
              ['greeting', 'Greeting'],
            ].map(([key, label]) => (
              <label key={key}>
                {label}
                <input
                  required={key !== 'greeting'}
                  value={form[key]}
                  onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                />
              </label>
            ))}
            <div className="row gap">
              <button type="button" className="btn ghost" onClick={() => setShow(false)}>Cancel</button>
              <button className="btn primary">Create</button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
