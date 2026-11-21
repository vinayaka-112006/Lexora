// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import App from './App.jsx'

const API = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '')

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function apiResponse(body, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body }
}

function answerResponse(overrides = {}) {
  return {
    query: 'What does Patent Act Section 3 say?',
    answer: 'Section 3 lists specified exclusions. [Source: Patent Act, section 3, pp. 1-2]',
    decision: 'answer',
    confidence: 0.9,
    citations: [{ raw: '[Source: Patent Act, section 3, pp. 1-2]', valid: true }],
    sources: [{ chunk_id: 'c1', citation: 'Patent Act, section 3, pp. 1-2', jurisdiction: 'India' }],
    retrieved_evidence: [{ source: { chunk_id: 'c1', document_name: 'Patent Act' }, text: 'Section 3 text.' }],
    abstention_reason: null,
    claim_verification: { claims: [{ claim_id: 1, status: 'uncertain', text: 'A legal claim.' }] },
    ...overrides,
  }
}

function savedChat(overrides = {}) {
  return {
    id: 'chat-123',
    query: 'Saved patent question?',
    jurisdiction: 'India',
    answer: 'Saved legal answer.',
    decision: 'answer',
    confidence: 0.8,
    citations: [{ raw: '[Source: Patent Act, section 3, pp. 1-2]', valid: true }],
    abstentionReason: null,
    createdAt: '2026-01-02T03:04:00.000Z',
    updatedAt: '2026-01-02T03:04:00.000Z',
    ...overrides,
  }
}

function makeFetch({
  sessionStatus = 401,
  sessionBody = { error: 'Authentication required.' },
  sessionAfterLoginStatus = 200,
  sessionAfterLoginBody = { user: { id: 'user-1', name: 'Example User', email: 'user@example.com' } },
  loginStatus = 200,
  loginBody,
  registerStatus = 201,
  queryStatus = 200,
  queryBody,
  chats = [],
  detail = savedChat(),
  detailStatus = 200,
  logoutStatus = 200,
  logoutFailure = false,
  onChats,
} = {}) {
  let sessionCalls = 0
  return vi.fn(async (url) => {
    if (url === API + '/api/auth/me') {
      sessionCalls += 1
      return sessionCalls === 1
        ? apiResponse(sessionBody, sessionStatus)
        : apiResponse(sessionAfterLoginBody, sessionAfterLoginStatus)
    }
    if (url === API + '/api/auth/logout') {
      if (logoutFailure) throw new Error('network failure')
      return apiResponse({ message: 'Logged out.' }, logoutStatus)
    }
    if (url === API + '/api/auth/login') {
      return apiResponse(loginBody || { user: { id: 'user-1', name: 'Example User', email: 'user@example.com' } }, loginStatus)
    }
    if (url === API + '/api/auth/register') {
      return apiResponse({ user: { id: 'user-1', name: 'Example User', email: 'user@example.com' } }, registerStatus)
    }
    if (url === API + '/api/chats') {
      return apiResponse(onChats ? onChats() : chats)
    }
    if (url.startsWith(API + '/api/chats/')) return apiResponse(detail, detailStatus)
    if (url === API + '/api/query') return apiResponse(queryBody || answerResponse(), queryStatus)
    if (url === API + '/api/news/search') return apiResponse({
      mode: 'news', answer: 'A news-only summary.', results: [{
        title: 'Current research update', description: 'A separate research result.',
        source: 'example.org', publishedDate: null, url: 'https://example.org/research',
      }],
    })
    throw new Error('Unexpected URL ' + url)
  })
}

function fillAndSubmit(query = 'What does Patent Act Section 3 say?') {
  fireEvent.change(screen.getByRole('textbox', { name: 'Your question' }), { target: { value: query } })
  fireEvent.click(screen.getByRole('button', { name: 'Send' }))
}

async function signIn(fetchMock) {
  render(<App />)
  await screen.findByRole('heading', { name: 'Sign in' })
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'user@example.com' } })
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'strong-password' } })
  fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
  await screen.findByRole('button', { name: 'Sign out' })
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
    API + '/api/chats',
    expect.objectContaining({ credentials: 'include' }),
  ))
}

describe('Stage 8F authentication and chat history', () => {
  it('uses the same localhost hostname as the configured frontend origin', () => {
    expect(new URL(API).origin).toBe('http://localhost:3000')
  })

  it('calls /me on load and shows login UI after an unauthenticated response', async () => {
    const fetchMock = makeFetch()
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    expect(screen.getByRole('status').textContent).toMatch(/Checking your session/)
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeTruthy()
    expect(fetchMock).toHaveBeenCalledWith(API + '/api/auth/me', expect.objectContaining({ credentials: 'include' }))
    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeTruthy()
    expect(screen.queryByRole('textbox', { name: 'Your question' })).toBeNull()
  })

  it('keeps the loading state visible while /me is pending', async () => {
    let resolveSession
    const pendingSession = new Promise((resolve) => { resolveSession = resolve })
    const fetchMock = vi.fn(async (url) => {
      if (url === API + '/api/auth/me') return pendingSession
      return apiResponse([])
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    expect(screen.getByRole('status').textContent).toMatch(/Checking your session/)
    expect(screen.queryByRole('heading', { name: 'Sign in' })).toBeNull()
    resolveSession(apiResponse({ error: 'Authentication required.' }, 401))
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeTruthy()
  })

  it('restores the authenticated UI and user information from /me', async () => {
    const fetchMock = makeFetch({
      sessionStatus: 200,
      sessionBody: { user: { id: 'restored-user', name: 'Restored User', email: 'restored@example.com' } },
      chats: [],
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    expect(await screen.findByRole('button', { name: 'Sign out' })).toBeTruthy()
    expect(screen.getByText('Restored User')).toBeTruthy()
    expect(screen.getByRole('textbox', { name: 'Your question' })).toBeTruthy()
    expect(fetchMock.mock.calls[0][1].credentials).toBe('include')
  })

  it('renders the registration form', async () => {
    vi.stubGlobal('fetch', makeFetch())
    render(<App />)
    await screen.findByRole('heading', { name: 'Sign in' })
    fireEvent.click(screen.getByRole('button', { name: 'Create an account' }))
    expect(screen.getByRole('heading', { name: 'Create your account' })).toBeTruthy()
    expect(screen.getByLabelText('Name')).toBeTruthy()
    expect(screen.getByLabelText('Email')).toBeTruthy()
    expect(screen.getByLabelText('Password').getAttribute('minlength')).toBe('8')
  })

  it('registers with credentials and returns to login without automatically authenticating', async () => {
    const fetchMock = makeFetch()
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    await screen.findByRole('heading', { name: 'Sign in' })
    fireEvent.click(screen.getByRole('button', { name: 'Create an account' }))
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Example User' } })
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'user@example.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'strong-password' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }))
    expect(await screen.findByText('Account created. Sign in to continue.')).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeTruthy()
    const registerCall = fetchMock.mock.calls.find(([url]) => url === API + '/api/auth/register')
    expect(fetchMock.mock.calls.filter(([url]) => url === API + '/api/auth/register')).toHaveLength(1)
    expect(registerCall[1].credentials).toBe('include')
    expect(JSON.parse(registerCall[1].body)).toEqual({
      name: 'Example User', email: 'user@example.com', password: 'strong-password',
    })
  })

  it('shows a safe invalid-credentials message after a failed login', async () => {
    const fetchMock = makeFetch({ loginStatus: 401, loginBody: { error: 'private backend detail' } })
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    await screen.findByRole('heading', { name: 'Sign in' })
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'user@example.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'wrong-password' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect((await screen.findByRole('alert')).textContent).toContain('Invalid email or password.')
    expect(screen.queryByText('private backend detail')).toBeNull()
  })

  it('checks the login cookie with /me before loading history and showing authenticated UI', async () => {
    const fetchMock = makeFetch({ chats: [savedChat()] })
    vi.stubGlobal('fetch', fetchMock)
    await signIn(fetchMock)
    expect(screen.getByRole('textbox', { name: 'Your question' })).toBeTruthy()
    expect(screen.getByText('Chat history')).toBeTruthy()
    expect(screen.getByRole('button', { name: /Saved patent question\?/ })).toBeTruthy()
    expect(screen.queryByRole('alert')).toBeNull()
    const loginCall = fetchMock.mock.calls.find(([url]) => url === API + '/api/auth/login')
    const meCalls = fetchMock.mock.calls
      .map(([url], index) => ({ url, index }))
      .filter(({ url }) => url === API + '/api/auth/me')
    const loginIndex = fetchMock.mock.calls.indexOf(loginCall)
    const historyIndex = fetchMock.mock.calls.findIndex(([url]) => url === API + '/api/chats')
    expect(meCalls).toHaveLength(2)
    expect(meCalls[1].index).toBeGreaterThan(loginIndex)
    expect(meCalls[1].index).toBeLessThan(historyIndex)
    expect(loginCall[1].credentials).toBe('include')
    expect(fetchMock.mock.calls.some(([url, options]) => url === API + '/api/chats'
      && options.credentials === 'include')).toBe(true)
  })

  it('shows a specific safe message when login succeeds but /me rejects the cookie', async () => {
    const fetchMock = makeFetch({ sessionAfterLoginStatus: 401 })
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    await screen.findByRole('heading', { name: 'Sign in' })
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'user@example.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'strong-password' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect((await screen.findByRole('alert')).textContent).toContain('browser session cookie was not accepted')
    expect(screen.queryByRole('textbox', { name: 'Your question' })).toBeNull()
    expect(screen.getByLabelText('Password').value).toBe('')
  })

  it('sends authenticated queries with credentials and preserves answer and citation rendering without diagnostics', async () => {
    const response = answerResponse()
    const fetchMock = makeFetch({ queryBody: response })
    vi.stubGlobal('fetch', fetchMock)
    await signIn(fetchMock)
    fireEvent.change(screen.getByRole('combobox', { name: 'Jurisdiction' }), { target: { value: 'India' } })
    fillAndSubmit()
    expect(await screen.findByText(response.answer)).toBeTruthy()
    expect(screen.queryByText(/confidence score 0\.90/)).toBeNull()
    const queryCall = fetchMock.mock.calls.find(([url]) => url === API + '/api/query')
    expect(queryCall[1].credentials).toBe('include')
    expect(JSON.parse(queryCall[1].body)).toEqual({
      query: 'What does Patent Act Section 3 say?', jurisdiction: 'India',
    })
    expect(screen.getByText(response.answer)).toBeTruthy()
    expect(screen.queryByText('Claim checks')).toBeNull()
    expect(screen.queryByText('Claim citation checks')).toBeNull()
    expect(screen.queryByText('Sources')).toBeNull()
  })

  it('labels a truncated model response as incomplete and does not offer answer follow-ups', async () => {
    const incomplete = answerResponse({
      decision: 'generation_incomplete',
      answer: 'Generation stopped before completion. This response is incomplete and has not been verified.',
      claim_verification: null,
    })
    const fetchMock = makeFetch({ queryBody: incomplete })
    vi.stubGlobal('fetch', fetchMock)
    await signIn(fetchMock)
    fillAndSubmit()
    expect(await screen.findByText('Incomplete response')).toBeTruthy()
    expect(screen.getByText(/Generation stopped before completion/).textContent).not.toContain('The statute provides that')
    expect(screen.queryByRole('group', { name: 'Suggested follow-up questions' })).toBeNull()
  })

  it('renders Markdown formatting, lists, paragraphs, code, links, and escaped markers in answers', async () => {
    const answer = [
      '**Intellectual Property (IP) Considerations:**',
      '',
      '## Legal framework',
      '',
      'The relevant points are:',
      '',
      '1. **Patent protection** may apply to a qualifying invention.',
      '2. *Trademark protection* may protect a distinctive mark.',
      '',
      'See [the official Act](https://example.gov/act). [Source: Patent Act, section 3, pp. 1-2]',
      '',
      '```text',
      'Section 3',
      '```',
      '',
      'Escaped markers: \\*literal asterisks\\*.',
    ].join('\n')
    const fetchMock = makeFetch({ queryBody: answerResponse({ answer }) })
    vi.stubGlobal('fetch', fetchMock)
    await signIn(fetchMock)
    fillAndSubmit()

    expect(await screen.findByText('Intellectual Property (IP) Considerations:')).toBeTruthy()
    expect(screen.getByText('Intellectual Property (IP) Considerations:').tagName).toBe('STRONG')
    expect(screen.getByRole('heading', { name: 'Legal framework', level: 2 })).toBeTruthy()
    expect(screen.getByText('Patent protection').tagName).toBe('STRONG')
    expect(screen.getByText('Trademark protection').tagName).toBe('EM')
    expect(screen.getAllByRole('list').some((list) => list.tagName === 'OL')).toBe(true)
    expect(screen.getByText('The relevant points are:')).toBeTruthy()
    expect(screen.getByText('Section 3')).toBeTruthy()
    expect(screen.getByRole('link', { name: 'the official Act' }).getAttribute('href')).toBe('https://example.gov/act')
    expect(screen.getByText(/\[Source: Patent Act, section 3, pp\. 1-2\]/)).toBeTruthy()
    const escapedMarkerParagraph = screen.getByText(/Escaped markers:/)
    expect(escapedMarkerParagraph.textContent).toContain('*literal asterisks*')
    expect(escapedMarkerParagraph.textContent).not.toContain('\\*')
  })

  it('keeps withheld claim diagnostics and internal validation details out of the chat', async () => {
    const response = answerResponse({
      answer: 'A cited but unverified legal claim. [Source: Patent Act, section 3, pp. 1-2]',
      claim_verification: {
        claims: [{
          claim_id: 1,
          status: 'uncertain',
          citation_valid: true,
          evidence_found: true,
          text: 'A cited but unverified legal claim.',
          citations: ['[Source: Patent Act, section 3, pp. 1-2]'],
        }, {
          claim_id: 3,
          status: 'unsupported',
          citation_valid: false,
          evidence_found: false,
          text: 'An unsupported claim.',
          citations: [],
        }],
        withheld_claim_count: 6,
        semantic_support: 'not_verified',
        generated_claims: [{
          claim_id: 2,
          text: 'A rejected legal claim.',
          citations: ['[Source: Act, section 7, pp. 2-3]'],
          citation_results: [{ valid: false, errors: ['Citation does not match any retrieved evidence.'] }],
          retained: false,
          withheld: true,
          withheld_reasons: ['citation_not_mapped_to_retrieved_evidence'],
          citation_errors: ['Citation does not match any retrieved evidence.'],
          safety_guards: [],
          matched_sources: [],
        }],
      },
    })
    const fetchMock = makeFetch({ queryBody: response })
    vi.stubGlobal('fetch', fetchMock)
    await signIn(fetchMock)
    fillAndSubmit()
    expect(await screen.findByText(response.answer)).toBeTruthy()
    expect(screen.getByText('Claims with matching citations')).toBeTruthy()
    expect(screen.getByText('A cited but unverified legal claim.')).toBeTruthy()
    expect(screen.getByText('[Source: Patent Act, section 3, pp. 1-2]')).toBeTruthy()
    expect(screen.queryByText('An unsupported claim.')).toBeNull()
    expect(screen.queryByText('Withheld claim diagnostics')).toBeNull()
    expect(screen.queryByText('Claim checks')).toBeNull()
    expect(screen.queryByText('A rejected legal claim.')).toBeNull()
    expect(screen.queryByText(/citation_not_mapped_to_retrieved_evidence/)).toBeNull()
    expect(screen.queryByText(/Citation does not match any retrieved evidence/)).toBeNull()
    expect(screen.queryByText(/Matched source metadata/)).toBeNull()
  })

  it('submits a clicked follow-up with the original question through the existing query API', async () => {
    const fetchMock = makeFetch()
    vi.stubGlobal('fetch', fetchMock)
    await signIn(fetchMock)
    fillAndSubmit('What is a patent under Indian law?')
    await screen.findByText(answerResponse().answer)
    fireEvent.click(screen.getByRole('button', { name: 'How does this apply to Ayurvedic products?' }))
    await waitFor(() => expect(fetchMock.mock.calls.filter(([url]) => url === API + '/api/query')).toHaveLength(2))
    const queryCalls = fetchMock.mock.calls.filter(([url]) => url === API + '/api/query')
    const followUp = JSON.parse(queryCalls[1][1].body).query
    expect(followUp).toContain('Context: Patent Act; India jurisdiction; original question: What is a patent under Indian law?; original topic: patent')
    expect(followUp).toContain('Follow-up request: How does this apply to Ayurvedic products?')
  })

  it('adds original patent context to a typed contextual follow-up', async () => {
    const fetchMock = makeFetch()
    vi.stubGlobal('fetch', fetchMock)
    await signIn(fetchMock)
    fillAndSubmit('What is a patent under Indian law?')
    await screen.findByText(answerResponse().answer)
    fillAndSubmit('How does this apply to Ayurvedic products?')
    await waitFor(() => expect(fetchMock.mock.calls.filter(([url]) => url === API + '/api/query')).toHaveLength(2))
    const queryCalls = fetchMock.mock.calls.filter(([url]) => url === API + '/api/query')
    const followUp = JSON.parse(queryCalls[1][1].body).query
    expect(followUp).toContain('How does this apply to Ayurvedic products?')
    expect(followUp).toContain('Context: Patent Act; India jurisdiction; original question: What is a patent under Indian law?; original topic: patent')
  })

  it('adds patent context to a typed simple-words follow-up', async () => {
    const fetchMock = makeFetch()
    vi.stubGlobal('fetch', fetchMock)
    await signIn(fetchMock)
    fillAndSubmit('What is a patent under Indian law?')
    await screen.findByText(answerResponse().answer)
    fillAndSubmit('Explain in simple words')
    await waitFor(() => expect(fetchMock.mock.calls.filter(([url]) => url === API + '/api/query')).toHaveLength(2))
    const queryCalls = fetchMock.mock.calls.filter(([url]) => url === API + '/api/query')
    const followUp = JSON.parse(queryCalls[1][1].body).query
    expect(followUp).toContain('Explain in simple words')
    expect(followUp).toContain('original question: What is a patent under Indian law?')
    expect(followUp).toContain('original topic: patent')
  })

  it('carries a clearly shared legal topic into a follow-up without naming the Act again', async () => {
    const fetchMock = makeFetch()
    vi.stubGlobal('fetch', fetchMock)
    await signIn(fetchMock)
    const root = 'I am an Indian citizen starting an Ayurvedic company in Karnataka and sourcing cultivated Ashwagandha roots. What applies under the Biological Diversity Act?'
    fillAndSubmit(root)
    await screen.findByText(answerResponse().answer)

    const followUp = 'I am an Indian citizen incorporating an Indian Ayurvedic company. We purchase cultivated Ashwagandha roots from Indian farmers. Explain whether Section 3 or Section 7 applies and distinguish the applicable person categories, activities, exemptions and conditions.'
    fillAndSubmit(followUp)
    await waitFor(() => expect(fetchMock.mock.calls.filter(([url]) => url === API + '/api/query')).toHaveLength(2))
    const queryCalls = fetchMock.mock.calls.filter(([url]) => url === API + '/api/query')
    const sentQuery = JSON.parse(queryCalls[1][1].body).query
    expect(sentQuery).toContain(followUp)
    expect(sentQuery).toContain('original question: ' + root)
    expect(sentQuery.match(/Context:/gi)).toHaveLength(1)
    expect(JSON.parse(queryCalls[1][1].body).jurisdiction).toBeUndefined()
  })

  it('preserves root context for common typed summary requests', async () => {
    const fetchMock = makeFetch()
    vi.stubGlobal('fetch', fetchMock)
    await signIn(fetchMock)
    fillAndSubmit('What is a patent under Indian law?')
    await screen.findByText(answerResponse().answer)

    for (const [index, request] of [
      'Give me the summary',
      'Summarize this',
      'Yeh give me the summary',
    ].entries()) {
      fillAndSubmit(request)
      await waitFor(() => expect(fetchMock.mock.calls.filter(([url]) => url === API + '/api/query')).toHaveLength(index + 2))
      const queryCalls = fetchMock.mock.calls.filter(([url]) => url === API + '/api/query')
      const sentQuery = JSON.parse(queryCalls[index + 1][1].body).query
      expect(sentQuery).toContain(request)
      expect(sentQuery).toContain('original question: What is a patent under Indian law?')
      expect(sentQuery).toContain('original topic: patent')
      expect(sentQuery.match(/original question:/gi)).toHaveLength(1)
      expect(sentQuery.match(/Context:/gi)).toHaveLength(1)
      await waitFor(() => expect(screen.getAllByText(answerResponse().answer)).toHaveLength(index + 2))
    }
  })

  it('keeps the original root question across three consecutive typed follow-ups', async () => {
    const fetchMock = makeFetch()
    vi.stubGlobal('fetch', fetchMock)
    await signIn(fetchMock)
    fillAndSubmit('What is a patent under Indian law?')
    await screen.findByText(answerResponse().answer)

    const followUps = [
      'What are the patentability requirements?',
      'How does this apply to Ayurvedic products?',
      'Explain in simple words',
    ]
    for (const [index, followUp] of followUps.entries()) {
      fillAndSubmit(followUp)
      await waitFor(() => expect(fetchMock.mock.calls.filter(([url]) => url === API + '/api/query')).toHaveLength(index + 2))
      const queryCalls = fetchMock.mock.calls.filter(([url]) => url === API + '/api/query')
      const sentQuery = JSON.parse(queryCalls[index + 1][1].body).query
      expect(sentQuery).toContain(followUp)
      expect(sentQuery).toContain('original question: What is a patent under Indian law?')
      expect(sentQuery.match(/original question:/gi)).toHaveLength(1)
      expect(sentQuery.match(/Context:/gi)).toHaveLength(1)
      expect(sentQuery).not.toContain('Follow-up request:')
      await waitFor(() => expect(screen.getAllByText(answerResponse().answer)).toHaveLength(index + 2))
    }
  })

  it('does not add patent context to a new unrelated typed question', async () => {
    const fetchMock = makeFetch()
    vi.stubGlobal('fetch', fetchMock)
    await signIn(fetchMock)
    fillAndSubmit('What is a patent under Indian law?')
    await screen.findByText(answerResponse().answer)
    fillAndSubmit('What is the capital of France?')
    await waitFor(() => expect(fetchMock.mock.calls.filter(([url]) => url === API + '/api/query')).toHaveLength(2))
    const queryCalls = fetchMock.mock.calls.filter(([url]) => url === API + '/api/query')
    expect(JSON.parse(queryCalls[1][1].body).query).toBe('What is the capital of France?')
    await screen.findAllByText(answerResponse().answer)
    fillAndSubmit('Explain in simple words')
    await waitFor(() => expect(fetchMock.mock.calls.filter(([url]) => url === API + '/api/query')).toHaveLength(3))
    const latestQueryCall = fetchMock.mock.calls.filter(([url]) => url === API + '/api/query')[2]
    const nextContext = JSON.parse(latestQueryCall[1].body).query
    expect(nextContext).toContain('original question: What is the capital of France?')
    expect(nextContext).not.toContain('What is a patent under Indian law?')
  })

  it('preserves an explicitly selected jurisdiction in typed follow-up context', async () => {
    const fetchMock = makeFetch()
    vi.stubGlobal('fetch', fetchMock)
    await signIn(fetchMock)
    fireEvent.change(screen.getByRole('combobox', { name: 'Jurisdiction' }), { target: { value: 'International' } })
    fillAndSubmit('What is a patent under Indian law?')
    await screen.findByText(answerResponse().answer)
    fillAndSubmit('Explain in simple words')
    await waitFor(() => expect(fetchMock.mock.calls.filter(([url]) => url === API + '/api/query')).toHaveLength(2))
    const queryCalls = fetchMock.mock.calls.filter(([url]) => url === API + '/api/query')
    const payload = JSON.parse(queryCalls[1][1].body)
    expect(payload.query).toContain('International jurisdiction')
    expect(payload.jurisdiction).toBe('International')
  })
  it('continues forwarding International and default jurisdiction selections', async () => {
    for (const jurisdiction of ['International', '']) {
      cleanup()
      const fetchMock = makeFetch()
      vi.stubGlobal('fetch', fetchMock)
      await signIn(fetchMock)
      if (jurisdiction) {
        fireEvent.change(screen.getByRole('combobox', { name: 'Jurisdiction' }), { target: { value: jurisdiction } })
      }
      fillAndSubmit()
      await screen.findByText(answerResponse().answer)
      const queryCall = fetchMock.mock.calls.find(([url]) => url === API + '/api/query')
      const sent = JSON.parse(queryCall[1].body)
      expect(sent.query).toBe(answerResponse().query)
      if (jurisdiction) expect(sent.jurisdiction).toBe(jurisdiction)
      else expect(sent).not.toHaveProperty('jurisdiction')
    }
  })

  it('shows loading feedback and prevents duplicate query submission', async () => {
    let resolveQuery
    let sessionCalls = 0
    const pendingQuery = new Promise((resolve) => { resolveQuery = resolve })
    const fetchMock = makeFetch()
    fetchMock.mockImplementation(async (url) => {
      if (url === API + '/api/query') return pendingQuery
      if (url === API + '/api/auth/me') {
        sessionCalls += 1
        return sessionCalls === 1
          ? apiResponse({ error: 'Authentication required.' }, 401)
          : apiResponse({ user: { id: 'user-1', name: 'Example User', email: 'user@example.com' } })
      }
      if (url === API + '/api/auth/login') {
        return apiResponse({ user: { id: 'user-1', name: 'Example User', email: 'user@example.com' } })
      }
      if (url === API + '/api/chats') return apiResponse([])
      return apiResponse(savedChat())
    })
    vi.stubGlobal('fetch', fetchMock)
    await signIn(fetchMock)
    fillAndSubmit()
    expect(screen.getByRole('status').textContent).toMatch(/Searching legal sources/)
    expect(screen.getByRole('button', { name: /Sending/ }).disabled).toBe(true)
    fireEvent.submit(screen.getByRole('textbox', { name: 'Your question' }).closest('form'))
    expect(fetchMock.mock.calls.filter(([url]) => url === API + '/api/query')).toHaveLength(1)
    resolveQuery(apiResponse(answerResponse()))
    expect(await screen.findByText(answerResponse().answer)).toBeTruthy()
  })

  it('loads a selected history item without making a new query', async () => {
    const chat = savedChat()
    const fetchMock = makeFetch({ chats: [chat], detail: chat })
    vi.stubGlobal('fetch', fetchMock)
    await signIn(fetchMock)
    fireEvent.click(screen.getByRole('button', { name: /Saved patent question\?/ }))
    expect(await screen.findByText(chat.answer)).toBeTruthy()
    const detailCall = fetchMock.mock.calls.find(([url]) => url === API + '/api/chats/' + chat.id)
    expect(detailCall[1].credentials).toBe('include')
    expect(fetchMock.mock.calls.some(([url]) => url === API + '/api/query')).toBe(false)
  })

  it('refreshes history after a successful query', async () => {
    let historyCalls = 0
    const newChat = savedChat({ id: 'new-chat', query: 'New saved question?' })
    const fetchMock = makeFetch({ onChats: () => (++historyCalls === 1 ? [] : [newChat]) })
    vi.stubGlobal('fetch', fetchMock)
    await signIn(fetchMock)
    fillAndSubmit('New saved question?')
    await screen.findByRole('button', { name: /New saved question\?/ })
    expect(historyCalls).toBe(2)
  })

  it('sign out calls the server and clears frontend session and chat state', async () => {
    const fetchMock = makeFetch()
    vi.stubGlobal('fetch', fetchMock)
    await signIn(fetchMock)
    fillAndSubmit()
    await screen.findByText(answerResponse().answer)
    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }))
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeTruthy()
    expect(screen.queryByRole('textbox', { name: 'Your question' })).toBeNull()
    expect(screen.queryByText(answerResponse().answer)).toBeNull()
    const logoutCall = fetchMock.mock.calls.find(([url]) => url === API + '/api/auth/logout')
    expect(logoutCall[1]).toMatchObject({ method: 'POST', credentials: 'include' })
  })

  it('clears local authentication state even when logout fails', async () => {
    const fetchMock = makeFetch({ logoutFailure: true })
    vi.stubGlobal('fetch', fetchMock)
    await signIn(fetchMock)
    fillAndSubmit()
    await screen.findByText(answerResponse().answer)
    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }))
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeTruthy()
    expect(screen.queryByRole('textbox', { name: 'Your question' })).toBeNull()
  })

  it('does not read or write authentication data in browser storage', async () => {
    const getItem = vi.spyOn(Storage.prototype, 'getItem')
    const setItem = vi.spyOn(Storage.prototype, 'setItem')
    const fetchMock = makeFetch()
    vi.stubGlobal('fetch', fetchMock)
    await signIn(fetchMock)
    expect(getItem).not.toHaveBeenCalled()
    expect(setItem).not.toHaveBeenCalled()
  })

  it('returns to login when an authenticated API request receives 401', async () => {
    const fetchMock = makeFetch({ queryStatus: 401, queryBody: { error: 'private backend detail' } })
    vi.stubGlobal('fetch', fetchMock)
    await signIn(fetchMock)
    fillAndSubmit()
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeTruthy()
    expect(await screen.findByText('Your session has expired. Please sign in again.')).toBeTruthy()
    expect(screen.queryByText('private backend detail')).toBeNull()
  })

  it('shows a safe registration conflict message', async () => {
    const fetchMock = makeFetch({ registerStatus: 409 })
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    await screen.findByRole('heading', { name: 'Sign in' })
    fireEvent.click(screen.getByRole('button', { name: 'Create an account' }))
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Example' } })
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'user@example.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'strong-password' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }))
    expect((await screen.findByRole('alert')).textContent).toContain('An account with this email already exists.')
  })

  it('preserves abstention rendering after authentication', async () => {
    const result = answerResponse({
      decision: 'abstain',
      answer: 'The available corpus cannot establish this.',
      confidence: null,
      citations: [],
      abstention_reason: 'Current information is unavailable.',
    })
    const fetchMock = makeFetch({ queryBody: result })
    vi.stubGlobal('fetch', fetchMock)
    await signIn(fetchMock)
    fillAndSubmit('What is the current patent filing fee?')
    expect(await screen.findByText('Insufficient evidence')).toBeTruthy()
    expect(screen.getByText(result.abstention_reason)).toBeTruthy()
    expect(await screen.findByText(result.answer)).toBeTruthy()
  })

  it('does not repeat an abstention reason already included in the answer', async () => {
    const reason = 'The retrieved evidence does not include section 7.'
    const result = answerResponse({
      decision: 'abstain', answer: reason, abstention_reason: reason,
      citations: [], claim_verification: null,
    })
    const fetchMock = makeFetch({ queryBody: result })
    vi.stubGlobal('fetch', fetchMock)
    await signIn(fetchMock)
    fillAndSubmit('Explain Section 7')
    expect(await screen.findByText(reason)).toBeTruthy()
    expect(screen.getAllByText(reason)).toHaveLength(1)
  })

  it('keeps retrieval diagnostics, warnings, and the caution badge out of the answer interface', async () => {
    const result = answerResponse({
      decision: 'answer_with_caution',
      answer: 'Section 3 text. [Source: Patent Act, section 3, pp. 1-2]',
      warnings: ['Uncited statements were omitted.'],
      retrieval_diagnostic: {
        all_found: false,
        requested: [
          { type: 'section', number: '3', found: true, chunk_ids: ['s3'] },
          { type: 'section', number: '7', found: false, chunk_ids: [] },
        ],
        missing: [{ type: 'section', number: '7', found: false, chunk_ids: [] }],
      },
    })
    const fetchMock = makeFetch({ queryBody: result })
    vi.stubGlobal('fetch', fetchMock)
    await signIn(fetchMock)
    fillAndSubmit('Explain Sections 3 and 7 of the Biological Diversity Act')
    expect(screen.queryByText('Answer · use caution')).toBeNull()
    expect(screen.queryByText(/use caution/)).toBeNull()
    expect(screen.queryByText('Uncited statements were omitted.')).toBeNull()
    expect(screen.queryByText('Requested provision retrieval')).toBeNull()
    expect(screen.queryByText('section 3: retrieved')).toBeNull()
    expect(screen.queryByText('section 7: not retrieved')).toBeNull()
    expect(await screen.findByText(result.answer)).toBeTruthy()
  })

  it('renders general chat responses without legal badges, abstention, or claim checks', async () => {
    const generalResponse = answerResponse({
      decision: 'general',
      answer: 'Hello! How can I help you today?',
      confidence: 1.0,
      citations: [],
      sources: [],
      retrieved_evidence: [],
      abstention_reason: null,
      claim_verification: null,
      retrieval_diagnostic: null,
      warnings: [],
      mode: 'general',
    })
    const fetchMock = makeFetch({ queryBody: generalResponse })
    vi.stubGlobal('fetch', fetchMock)
    await signIn(fetchMock)
    fillAndSubmit('hello')
    expect(await screen.findByText('Hello! How can I help you today?')).toBeTruthy()
    expect(screen.queryByText('Insufficient evidence')).toBeNull()
    expect(screen.queryByText('Answer')).toBeNull()
    expect(screen.queryByText('Claim checks')).toBeNull()
    expect(screen.queryByText('Claim citation checks')).toBeNull()
  })

  it('submits a query when Enter key is pressed without Shift', async () => {
    const fetchMock = makeFetch()
    vi.stubGlobal('fetch', fetchMock)
    await signIn(fetchMock)
    const textarea = screen.getByRole('textbox', { name: 'Your question' })
    fireEvent.change(textarea, { target: { value: 'What is a patent under Indian law?' } })
    fireEvent.keyDown(textarea, { key: 'Enter', code: 'Enter', shiftKey: false })
    await screen.findByText(answerResponse().answer)
    const queryCalls = fetchMock.mock.calls.filter(([url]) => url === API + '/api/query')
    expect(queryCalls.length).toBeGreaterThanOrEqual(1)
  })

  it('keeps the news panel separate and preserves its state and chat when closed', async () => {
    const fetchMock = makeFetch()
    vi.stubGlobal('fetch', fetchMock)
    await signIn(fetchMock)
    fillAndSubmit('What does Patent Act Section 3 say?')
    await screen.findByText(answerResponse().answer)

    fireEvent.click(screen.getByRole('button', { name: 'Recent News?' }))
    fireEvent.change(screen.getByRole('searchbox', { name: 'Search current information' }), {
      target: { value: 'Latest Ayurveda news' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Search', exact: true }))
    expect(await screen.findByText('A news-only summary.')).toBeTruthy()
    expect(screen.getByText('Current research update')).toBeTruthy()
    expect(fetchMock.mock.calls.some(([url]) => url === API + '/api/news/search')).toBe(true)

    fireEvent.click(screen.getByRole('button', { name: 'Close research panel' }))
    expect(screen.getByText(answerResponse().answer)).toBeTruthy()
    expect(screen.queryByText('Current research update')).toBeNull()
    expect(fetchMock.mock.calls.filter(([url]) => url === API + '/api/query')).toHaveLength(1)

    fireEvent.click(screen.getByRole('button', { name: 'Recent News?' }))
    expect(screen.getByText('A news-only summary.')).toBeTruthy()
    expect(screen.getByText('Current research update')).toBeTruthy()
  })
})
