const { afterEach, test } = require('node:test');
const assert = require('node:assert/strict');
const { createApp } = require('../src/server');
const { DEFAULT_TIMEOUT_MS } = require('../src/routes/query');

test('FastAPI proxy default timeout is 270 seconds', () => {
  assert.equal(DEFAULT_TIMEOUT_MS, 270000);
});

const originalRagUrl = process.env.RAG_SERVICE_URL;
const originalFrontendOrigin = process.env.FRONTEND_ORIGIN;

function setRagUrl(value = 'http://127.0.0.1:8000') {
  process.env.RAG_SERVICE_URL = value;
}

async function withServer(app, callback) {
  const server = app.listen(0);
  await new Promise((resolve) => server.once('listening', resolve));
  const { port } = server.address();
  try {
    return await callback(`http://127.0.0.1:${port}`);
  } finally {
    await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  }
}

function upstreamResponse(status, body) {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

function createAuthenticatedApp(options = {}) {
  return createApp({
    ...options,
    ChatLogModel: options.ChatLogModel || { async create() {} },
    queryAuthOptions: {
      verifyToken(token) {
        if (token !== 'test-auth-token') throw new Error('private verification details');
        return { sub: 'test-user-id' };
      },
    },
  });
}

afterEach(() => {
  if (originalRagUrl === undefined) delete process.env.RAG_SERVICE_URL;
  else process.env.RAG_SERVICE_URL = originalRagUrl;
  if (originalFrontendOrigin === undefined) delete process.env.FRONTEND_ORIGIN;
  else process.env.FRONTEND_ORIGIN = originalFrontendOrigin;
});

test('successful authenticated query persists only the allowed ChatLog fields', async () => {
  setRagUrl();
  const result = {
    answer: 'A patent protects an invention.',
    decision: 'answer',
    confidence: 0.91,
    citations: [{ source: 'Patent Act', section: '3' }],
    abstention_reason: null,
    retrieved_evidence: [{ text: 'do not persist this evidence' }],
    generation_metadata: { provider: 'test' },
  };
  const records = [];
  let forwardedBody;
  const app = createAuthenticatedApp({
    ChatLogModel: { async create(record) { records.push(record); } },
    fetchImpl: async (_url, options) => {
      forwardedBody = JSON.parse(options.body);
      return upstreamResponse(200, result);
    },
  });

  await withServer(app, async (base) => {
    const response = await fetch(`${base}/api/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Cookie: 'access_token=test-auth-token' },
      body: JSON.stringify({ query: 'What does section 3 exclude?', jurisdiction: 'India' }),
    });
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), result);
  });

  assert.deepEqual(forwardedBody, { query: 'What does section 3 exclude?', jurisdiction: 'India' });
  assert.deepEqual(records, [{
    userId: 'test-user-id',
    query: 'What does section 3 exclude?',
    jurisdiction: 'India',
    answer: result.answer,
    decision: 'answer',
    confidence: 0.91,
    citations: result.citations,
  }]);
  const savedText = JSON.stringify(records);
  assert.equal(savedText.includes('test-auth-token'), false);
  assert.equal(savedText.includes('retrieved_evidence'), false);
  assert.equal(savedText.includes('do not persist this evidence'), false);
  assert.equal(savedText.includes('generation_metadata'), false);
});

test('query correlation ID is forwarded, returned, and logged without query text', async () => {
  setRagUrl();
  let upstreamRequestId;
  const logs = [];
  const originalInfo = console.info;
  const result = {
    answer: 'Answer', decision: 'answer', citations: [], sources: [],
    retrieved_evidence: [], confidence: 0.5, abstention_reason: null,
  };
  const app = createAuthenticatedApp({ fetchImpl: async (_url, options) => {
    upstreamRequestId = options.headers['X-Request-ID'];
    return upstreamResponse(200, result);
  } });

  console.info = (message) => logs.push(String(message));
  let response;
  try {
    await withServer(app, async (base) => {
      response = await fetch(`${base}/api/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Cookie: 'access_token=test-auth-token',
        },
        body: JSON.stringify({ query: 'private query text' }),
      });
      assert.equal(response.status, 200);
      assert.deepEqual(await response.json(), result);
    });
  } finally {
    console.info = originalInfo;
  }

  const responseRequestId = response.headers.get('x-request-id');
  assert.match(responseRequestId, /^[0-9a-f-]{36}$/i);
  assert.equal(upstreamRequestId, responseRequestId);
  const entries = logs.map((line) => JSON.parse(line));
  const start = entries.find((entry) => entry.event === 'request_start');
  const complete = entries.find((entry) => entry.event === 'request_complete');
  assert.equal(start.request_id, responseRequestId);
  assert.equal(complete.request_id, responseRequestId);
  assert.equal(complete.http_status, 200);
  assert.equal(typeof complete.duration_ms, 'number');
  assert.equal(logs.join('').includes('private query text'), false);
  assert.equal(logs.join('').includes('test-auth-token'), false);
});

test('authenticated query forwards only query and jurisdiction and returns FastAPI response', async () => {
  setRagUrl();
  let requestSeen;
  const result = {
    query: 'What are patentability requirements in India?', answer: 'Answer', decision: 'answer',
    confidence: 0.9, citations: [], sources: [], retrieved_evidence: [],
    abstention_reason: null, claim_verification: {},
  };
  const app = createAuthenticatedApp({ fetchImpl: async (url, options) => {
    requestSeen = { url, options };
    return upstreamResponse(200, result);
  } });

  await withServer(app, async (base) => {
    const response = await fetch(`${base}/api/query`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', Cookie: 'access_token=test-auth-token' },
      body: JSON.stringify({
        query: result.query, jurisdiction: 'India', ignored: 'must not be forwarded',
        rag_service_url: 'https://attacker.example',
      }),
    });
    assert.equal(response.status, 200);
    const body = await response.json();
    assert.deepEqual(body, result);
    const responseText = JSON.stringify(body);
    assert.equal(responseText.includes('JWT_SECRET'), false);
    assert.equal(responseText.includes('MONGODB_URI'), false);
    assert.equal(responseText.includes('test-auth-token'), false);
  });

  assert.equal(requestSeen.url, 'http://127.0.0.1:8000/query');
  assert.equal(requestSeen.options.method, 'POST');
  assert.deepEqual(JSON.parse(requestSeen.options.body), { query: result.query, jurisdiction: 'India' });
  assert.equal(requestSeen.options.headers.cookie, undefined);
  assert.equal(JSON.stringify(requestSeen.options).includes('test-auth-token'), false);
  assert.ok(requestSeen.options.signal);
});

test('unauthenticated query returns 401 without calling FastAPI', async () => {
  setRagUrl();
  let calls = 0;
  const app = createApp({ fetchImpl: async () => { calls += 1; return upstreamResponse(200, {}); } });
  await withServer(app, async (base) => {
    const response = await fetch(`${base}/api/query`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: 'What is a patent?' }),
    });
    assert.equal(response.status, 401);
    assert.deepEqual(await response.json(), { error: 'Authentication required.' });
  });
  assert.equal(calls, 0);
});

test('omitted jurisdiction is omitted from upstream payload', async () => {
  setRagUrl();
  let upstreamBody;
  const app = createAuthenticatedApp({ fetchImpl: async (_url, options) => {
    upstreamBody = JSON.parse(options.body);
    return upstreamResponse(200, { decision: 'answer' });
  } });

  await withServer(app, async (base) => {
    const response = await fetch(`${base}/api/query`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', Cookie: 'access_token=test-auth-token' },
      body: JSON.stringify({ query: 'What does Patent Act Section 3 say?' }),
    });
    assert.equal(response.status, 200);
  });
  assert.deepEqual(upstreamBody, { query: 'What does Patent Act Section 3 say?' });
});

test('empty query is rejected without contacting FastAPI', async () => {
  setRagUrl();
  let calls = 0;
  const app = createAuthenticatedApp({ fetchImpl: async () => { calls += 1; return upstreamResponse(200, {}); } });

  await withServer(app, async (base) => {
    const response = await fetch(`${base}/api/query`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', Cookie: 'access_token=test-auth-token' },
      body: JSON.stringify({ query: ' \t ' }),
    });
    assert.equal(response.status, 400);
    assert.deepEqual(await response.json(), { error: 'query must be a non-empty string' });
  });
  assert.equal(calls, 0);
});

test('missing query is rejected without contacting FastAPI', async () => {
  setRagUrl();
  let calls = 0;
  const app = createAuthenticatedApp({ fetchImpl: async () => { calls += 1; return upstreamResponse(200, {}); } });

  await withServer(app, async (base) => {
    const response = await fetch(`${base}/api/query`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', Cookie: 'access_token=test-auth-token' }, body: JSON.stringify({}),
    });
    assert.equal(response.status, 400);
    assert.deepEqual(await response.json(), { error: 'query must be a non-empty string' });
  });
  assert.equal(calls, 0);
});

test('authenticated query returns abstention response normally', async () => {
  setRagUrl();
  const abstention = {
    decision: 'abstain', answer: 'Insufficient current evidence', confidence: null,
    citations: [], sources: [], retrieved_evidence: [], abstention_reason: 'freshness',
  };
  const records = [];
  const app = createAuthenticatedApp({
    ChatLogModel: { async create(record) { records.push(record); } },
    fetchImpl: async () => upstreamResponse(200, abstention),
  });

  await withServer(app, async (base) => {
    const response = await fetch(`${base}/api/query`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', Cookie: 'access_token=test-auth-token' },
      body: JSON.stringify({ query: 'What is the current patent filing fee?' }),
    });
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), abstention);
  });
  assert.equal(records.length, 1);
  assert.equal(records[0].decision, 'abstain');
  assert.equal(records[0].abstentionReason, 'freshness');
});

test('authenticated query returns generation_error response normally', async () => {
  setRagUrl();
  const generationError = { decision: 'generation_error', answer: 'Try again later', citations: [] };
  const records = [];
  const app = createAuthenticatedApp({
    timeoutMs: 1000,
    ChatLogModel: { async create(record) { records.push(record); } },
    fetchImpl: async () => upstreamResponse(200, generationError),
  });

  await withServer(app, async (base) => {
    const startedAt = Date.now();
    const response = await fetch(`${base}/api/query`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', Cookie: 'access_token=test-auth-token' },
      body: JSON.stringify({ query: 'What does Patent Act Section 3 say?' }),
    });
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), generationError);
    assert.ok(Date.now() - startedAt < 1000, 'generation_error should pass through before proxy timeout');
  });
  assert.equal(records.length, 1);
  assert.equal(records[0].decision, 'generation_error');
});

test('unavailable FastAPI returns a safe service-unavailable response', async () => {
  setRagUrl();
  const records = [];
  const app = createAuthenticatedApp({
    ChatLogModel: { async create(record) { records.push(record); } },
    fetchImpl: async () => { throw new Error('internal host and stack'); },
  });

  await withServer(app, async (base) => {
    const response = await fetch(`${base}/api/query`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', Cookie: 'access_token=test-auth-token' },
      body: JSON.stringify({ query: 'What does Patent Act Section 3 say?' }),
    });
    assert.equal(response.status, 503);
    assert.deepEqual(await response.json(), { error: 'RAG service unavailable' });
  });
  assert.equal(records.length, 0);
});

test('FastAPI timeout returns a safe timeout response', async () => {
  setRagUrl();
  const records = [];
  const logs = [];
  const originalWarn = console.warn;
  const originalInfo = console.info;
  console.warn = (message) => logs.push(String(message));
  console.info = (message) => logs.push(String(message));
  const app = createAuthenticatedApp({
    ChatLogModel: { async create(record) { records.push(record); } },
    timeoutMs: 5,
    fetchImpl: (_url, { signal }) => new Promise((resolve, reject) => {
      signal.addEventListener('abort', () => reject(signal.reason), { once: true });
    }),
  });

  let response;
  try {
    await withServer(app, async (base) => {
      response = await fetch(`${base}/api/query`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', Cookie: 'access_token=test-auth-token' },
        body: JSON.stringify({ query: 'What does Patent Act Section 3 say?' }),
      });
      assert.equal(response.status, 504);
      assert.deepEqual(await response.json(), { error: 'RAG service timed out' });
    });
  } finally {
    console.warn = originalWarn;
    console.info = originalInfo;
  }
  assert.equal(records.length, 0);
  const requestId = response.headers.get('x-request-id');
  const entries = logs.map((line) => JSON.parse(line));
  assert.ok(entries.some((entry) => entry.event === 'upstream_failure'
    && entry.request_id === requestId && entry.reason === 'timeout'));
  assert.ok(entries.some((entry) => entry.event === 'request_complete'
    && entry.request_id === requestId && entry.http_status === 504));
});

test('RAG health is proxied and unavailable health is handled safely', async () => {
  setRagUrl();
  const healthApp = createApp({ fetchImpl: async (url) => {
    assert.equal(url, 'http://127.0.0.1:8000/health');
    return upstreamResponse(200, { status: 'ok' });
  } });
  await withServer(healthApp, async (base) => {
    const response = await fetch(`${base}/api/health/rag`);
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { status: 'ok' });
  });

  const unavailableApp = createApp({ fetchImpl: async () => { throw new Error('hidden details'); } });
  await withServer(unavailableApp, async (base) => {
    const response = await fetch(`${base}/api/health/rag`);
    assert.equal(response.status, 503);
    assert.deepEqual(await response.json(), { error: 'RAG service unavailable' });
  });
});

test('malformed JSON gets a safe client error', async () => {
  const app = createAuthenticatedApp({ fetchImpl: async () => { throw new Error('should not run'); } });
  await withServer(app, async (base) => {
    const response = await fetch(`${base}/api/query`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', Cookie: 'access_token=test-auth-token' }, body: '{',
    });
    assert.equal(response.status, 400);
    assert.deepEqual(await response.json(), { error: 'Malformed JSON request' });
  });
});

test('CORS permits the configured Vite origin for browser requests', async () => {
  const app = createApp({ fetchImpl: async () => { throw new Error('preflight must not proxy'); } });
  await withServer(app, async (base) => {
    const response = await fetch(`${base}/api/query`, {
      method: 'OPTIONS',
      headers: {
        Origin: 'http://localhost:5173',
        'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'content-type',
      },
    });
    assert.equal(response.status, 204);
    assert.equal(response.headers.get('access-control-allow-origin'), 'http://localhost:5173');
    assert.equal(response.headers.get('access-control-allow-credentials'), 'true');
  });
});

test('CORS never combines wildcard origin with credential support', async () => {
  process.env.FRONTEND_ORIGIN = '*';
  const app = createApp({ fetchImpl: async () => { throw new Error('preflight must not proxy'); } });
  await withServer(app, async (base) => {
    const response = await fetch(`${base}/api/query`, {
      method: 'OPTIONS',
      headers: {
        Origin: 'http://localhost:5173',
        'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'content-type',
      },
    });
    assert.equal(response.headers.get('access-control-allow-origin'), null);
  });
});
