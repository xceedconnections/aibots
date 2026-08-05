import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, setToken } from '../api'

export default function Login() {
  const nav = useNavigate()
  const [email, setEmail] = useState('xceedconnections@gmail.com')
  const [password, setPassword] = useState('Openaccount@123')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function onSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const res = await api.login(email, password)
      setToken(res.access_token)
      nav('/')
    } catch (err) {
      setError(err.message || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={onSubmit}>
        <div className="brand login-brand">
          <span className="brand-mark">AI</span>
          <div>
            <h1 style={{ margin: 0, fontSize: '1.2rem' }}>AIBOTS</h1>
            <p style={{ margin: '0.15rem 0 0', color: 'var(--muted)', fontSize: '0.78rem' }}>
              VICIdial Voice Agents
            </p>
          </div>
        </div>
        <p className="muted">Campaigns, bots, Vicidialers, and SIP carrier settings.</p>
        {error && <div className="alert">{error}</div>}
        <label>
          Email
          <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />
        </label>
        <label>
          Password
          <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" required />
        </label>
        <button className="btn primary" disabled={loading}>
          {loading ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  )
}
