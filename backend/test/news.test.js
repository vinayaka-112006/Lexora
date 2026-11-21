const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createApp } = require('../src/server');
const { searchTavily, searchMode } = require('../src/services/tavilyService');

async function withServer(app, callback) {
  const server = app.listen(0);
  await new Promise((resolve) => server.once('listening', resolve));
  try { return await callback(`http://127.0.0.1:${server.address().port}`); }
  finally { await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve())); }
}

function post(base, body) {
  return fetch(`${base}/api/news/search`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
}

const passAuth = (req, res, next) => next();

test('news endpoint validates query and keeps search independent', async () => {
  let called = 0;
  const app = createApp({ queryAuthMiddleware: passAuth, newsSearch: async (query) => {
    called += 1;
    return { mode: 'news', answer: 'Summary', results: [{ title: query, url: 'https://example.com/a' }] };
  } });
  await withServer(app, async (base) => {
    const empty = await post(base, { query: '  ' });
    assert.equal(empty.status, 400);
    const tooLong = await post(base, { query: 'x'.repeat(501) });
    assert.equal(tooLong.status, 400);
    const response = await post(base, { query: 'latest Ayurveda news' });
    assert.equal(response.status, 200);
    assert.deepEqual((await response.json()).results[0].url, 'https://example.com/a');
  });
  assert.equal(called, 1);
});

test('Tavily service selects mode, normalizes dates and removes duplicate or unsafe URLs', async () => {
  assert.equal(searchMode('Latest AYUSH announcement'), 'news');
  assert.equal(searchMode('How does the web work?'), 'general');
  let request;
  const result = await searchTavily('Latest Ayurveda news', {
    apiKey: 'test-secret',
    fetchImpl: async (url, options) => {
      request = { url, body: JSON.parse(options.body) };
      return { ok: true, async json() { return { answer: 'A sourced summary', results: [
        { title: 'Article', content: 'Description', url: 'https://example.com/story', published_date: '2026-01-02' },
        { title: 'Duplicate', url: 'https://example.com/story' },
        { title: 'Unsafe', url: 'javascript:alert(1)' },
      ] }; } };
    },
  });
  assert.equal(request.url, 'https://api.tavily.com/search');
  assert.equal(request.body.topic, 'news');
  assert.equal(request.body.api_key, 'test-secret');
  assert.equal(result.results.length, 1);
  assert.equal(result.results[0].publishedDate, '2026-01-02');
  assert.equal(result.results[0].source, 'example.com');
});

test('Tavily service reports missing configuration without including a secret', async () => {
  await assert.rejects(searchTavily('Latest news', { apiKey: '' }), { code: 'TAVILY_NOT_CONFIGURED' });
});

test('news and research topics route to news search while unrelated current events use web search', () => {
  assert.equal(searchMode('Recent Ashwagandha research'), 'news');
  assert.equal(searchMode('New AYUSH government announcement'), 'news');
  assert.equal(searchMode('Latest election results'), 'news');
  assert.equal(searchMode('How does photosynthesis work?'), 'general');
});

test('Tavily service returns an empty result set and safely rejects upstream failures', async () => {
  const empty = await searchTavily('recent research', {
    apiKey: 'test-secret',
    fetchImpl: async () => ({ ok: true, async json() { return { answer: '', results: [] }; } }),
  });
  assert.deepEqual(empty.results, []);
  await assert.rejects(searchTavily('latest news', {
    apiKey: 'test-secret',
    fetchImpl: async () => ({ ok: false, status: 403 }),
  }), { code: 'TAVILY_UPSTREAM_ERROR' });
});
