import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'

const ACTIONS = ['continue', 'transfer', 'hangup', 'repeat']

export default function BotEditor() {
  const { id } = useParams()
  const [bot, setBot] = useState(null)
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')
  const [qForm, setQForm] = useState({
    prompt: '',
    variable_name: '',
    sort_order: 1,
    is_start: false,
    max_retries: 2,
  })
  const [answerDrafts, setAnswerDrafts] = useState({})

  async function load() {
    try {
      setBot(await api.getBot(id))
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => { load() }, [id])

  async function saveBot(e) {
    e.preventDefault()
    try {
      const updated = await api.updateBot(id, {
        name: bot.name,
        campaign: bot.campaign,
        transfer_campaign: bot.transfer_campaign,
        greeting: bot.greeting,
        voice: bot.voice,
        model: bot.model,
        temperature: bot.temperature,
        active: bot.active,
        language: bot.language,
        description: bot.description,
      })
      setBot(updated)
      setMsg('Bot settings saved')
    } catch (err) {
      setError(err.message)
    }
  }

  async function addQuestion(e) {
    e.preventDefault()
    await api.addQuestion(id, {
      ...qForm,
      sort_order: Number(qForm.sort_order),
      answers: [],
    })
    setQForm({ prompt: '', variable_name: '', sort_order: (bot.questions?.length || 0) + 2, is_start: false, max_retries: 2 })
    await load()
  }

  async function removeQuestion(qid) {
    if (!confirm('Delete question?')) return
    await api.deleteQuestion(qid)
    await load()
  }

  function draft(qid) {
    return answerDrafts[qid] || {
      intent: 'YES',
      keywords: 'yes, yeah, sure',
      action: 'continue',
      store_value: 'yes',
      next_question_id: '',
    }
  }

  async function addAnswer(qid) {
    const d = draft(qid)
    await api.addAnswer(qid, {
      intent: d.intent,
      keywords: d.keywords.split(',').map((s) => s.trim()).filter(Boolean),
      action: d.action,
      store_value: d.store_value || null,
      next_question_id: d.next_question_id ? Number(d.next_question_id) : null,
      priority: 10,
    })
    setAnswerDrafts({ ...answerDrafts, [qid]: undefined })
    await load()
  }

  async function removeAnswer(aid) {
    await api.deleteAnswer(aid)
    await load()
  }

  async function testCall() {
    setMsg('Starting simulated call…')
    try {
      const res = await api.startTestCall({
        bot_id: Number(id),
        campaign: bot.campaign,
        phone: '5551234567',
        lead_id: 'TEST001',
        call_id: `test-${Date.now()}`,
      })
      setMsg(`Call session #${res.call_session_id} queued. Watch worker logs / Calls page.`)
    } catch (e) {
      setError(e.message)
    }
  }

  if (!bot) return <p className="muted">Loading bot…</p>

  return (
    <div>
      <header className="page-head">
        <div>
          <Link className="muted" to="/bots">← Bots</Link>
          <h1>{bot.name}</h1>
          <p className="mono muted">{bot.campaign} → {bot.transfer_campaign}</p>
        </div>
        <button className="btn primary" onClick={testCall}>Run test call</button>
      </header>

      {error && <div className="alert">{error}</div>}
      {msg && <div className="alert ok">{msg}</div>}

      <form className="panel form-grid" onSubmit={saveBot}>
        <h2>Bot settings</h2>
        <label>Name<input value={bot.name} onChange={(e) => setBot({ ...bot, name: e.target.value })} /></label>
        <label>Campaign<input value={bot.campaign} onChange={(e) => setBot({ ...bot, campaign: e.target.value })} /></label>
        <label>Transfer campaign<input value={bot.transfer_campaign} onChange={(e) => setBot({ ...bot, transfer_campaign: e.target.value })} /></label>
        <label>Voice<input value={bot.voice} onChange={(e) => setBot({ ...bot, voice: e.target.value })} /></label>
        <label>LLM model<input value={bot.model} onChange={(e) => setBot({ ...bot, model: e.target.value })} /></label>
        <label className="full">Greeting<textarea rows={2} value={bot.greeting} onChange={(e) => setBot({ ...bot, greeting: e.target.value })} /></label>
        <label className="check">
          <input type="checkbox" checked={bot.active} onChange={(e) => setBot({ ...bot, active: e.target.checked })} />
          Active
        </label>
        <button className="btn primary">Save settings</button>
      </form>

      <section className="panel">
        <h2>Script builder</h2>
        <p className="muted">Questions run in order. Answers match keywords first, then local LLM intent.</p>

        {(bot.questions || []).map((q) => (
          <div key={q.id} className="question-block">
            <div className="row between">
              <h3>
                Q{q.sort_order}{q.is_start ? ' · START' : ''}
                {q.variable_name ? <span className="mono muted"> · {q.variable_name}</span> : null}
              </h3>
              <button className="btn danger" onClick={() => removeQuestion(q.id)}>Delete</button>
            </div>
            <p>{q.prompt}</p>

            <div className="answers">
              {(q.answers || []).map((a) => (
                <div key={a.id} className="answer-row">
                  <strong>{a.intent}</strong>
                  <span className="pill">{a.action}</span>
                  <span className="muted">{(a.keywords || []).join(', ')}</span>
                  {a.next_question_id && <span className="mono">→ Q#{a.next_question_id}</span>}
                  <button className="btn ghost" onClick={() => removeAnswer(a.id)}>×</button>
                </div>
              ))}
            </div>

            <div className="answer-form">
              <input
                placeholder="Intent"
                value={draft(q.id).intent}
                onChange={(e) => setAnswerDrafts({ ...answerDrafts, [q.id]: { ...draft(q.id), intent: e.target.value } })}
              />
              <input
                placeholder="keywords, comma, separated"
                value={draft(q.id).keywords}
                onChange={(e) => setAnswerDrafts({ ...answerDrafts, [q.id]: { ...draft(q.id), keywords: e.target.value } })}
              />
              <select
                value={draft(q.id).action}
                onChange={(e) => setAnswerDrafts({ ...answerDrafts, [q.id]: { ...draft(q.id), action: e.target.value } })}
              >
                {ACTIONS.map((a) => <option key={a} value={a}>{a}</option>)}
              </select>
              <input
                placeholder="Next question id (optional)"
                value={draft(q.id).next_question_id}
                onChange={(e) => setAnswerDrafts({ ...answerDrafts, [q.id]: { ...draft(q.id), next_question_id: e.target.value } })}
              />
              <button className="btn" type="button" onClick={() => addAnswer(q.id)}>Add answer</button>
            </div>
          </div>
        ))}

        <form className="add-q" onSubmit={addQuestion}>
          <h3>Add question</h3>
          <textarea
            required
            rows={2}
            placeholder="Question prompt spoken to the caller"
            value={qForm.prompt}
            onChange={(e) => setQForm({ ...qForm, prompt: e.target.value })}
          />
          <div className="row gap wrap">
            <input
              placeholder="Variable name (e.g. age_ok)"
              value={qForm.variable_name}
              onChange={(e) => setQForm({ ...qForm, variable_name: e.target.value })}
            />
            <input
              type="number"
              style={{ width: 100 }}
              value={qForm.sort_order}
              onChange={(e) => setQForm({ ...qForm, sort_order: e.target.value })}
            />
            <label className="check">
              <input
                type="checkbox"
                checked={qForm.is_start}
                onChange={(e) => setQForm({ ...qForm, is_start: e.target.checked })}
              />
              Start question
            </label>
            <button className="btn primary">Add question</button>
          </div>
        </form>
      </section>

      <section className="panel">
        <h2>VICIdial webhook</h2>
        <p className="muted">Set campaign Start Call URL / Dispo URL (or AGI) to:</p>
        <code className="block mono">
          http://YOUR_AIBOTS_IP/webhook/vicidial/start?campaign={bot.campaign}&amp;bot_id={bot.id}
        </code>
        <p className="muted">POST fields supported: call_id, lead_id, phone / phone_number, campaign, channel, uniqueid</p>
      </section>
    </div>
  )
}
