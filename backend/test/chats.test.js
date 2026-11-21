const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createApp } = require('../src/server');

const USER_A = '64b000000000000000000001';
const USER_B = '64b000000000000000000002';
const TOKEN_A = 'user-a-test-token';
const TOKEN_B = 'user-b-test-token';

function makeChat(id, userId, createdAt = new Date('2026-01-01T00:00:00Z')) {
  return {
    _id: id,
    userId,
    query: 'What does the Act say?',
    jurisdiction: 'India',
    answer: 'A safe answer.',
    decision: 'answer',
    confidence: 0.88,
    citations: [{ title: 'Example Act' }],
    abstentionReason: null,
    createdAt,
    updatedAt: createdAt,
    passwordHash: 'should-not-be-returned',
    access_token: 'should-not-be-returned',
    internalMetadata: { private: true },
  };
}

function mockChatLogModel(documents = []) {
  const state = { findFilters: [], findOneFilters: [], projections: [], sorts: [], limits: [], created: [] };

  function queryFor(resolve) {
    const query = {
      selection: null,
      sortOrder: null,
      maxRecords: null,
      select(fields) { this.selection = fields; state.projections.push(fields); return this; },
      sort(order) { this.sortOrder = order; state.sorts.push(order); return this; },
      limit(value) { this.maxRecords = value; state.limits.push(value); return this; },
      async lean() { return resolve(this); },
    };
    return query;
  }

  return {
    state,
    async create(record) { state.created.push(record); return record; },
    find(filter) {
      state.findFilters.push(filter);
      return queryFor((query) => {
        let results = documents.filter((item) => String(item.userId) === String(filter.userId));
        if (query.sortOrder?.createdAt === -1) {
          results = results.slice().sort((a, b) => b.createdAt - a.createdAt);
        }
        if (query.maxRecords !== null) results = results.slice(0, query.maxRecords);
        return results;
      });
    },
    findOne(filter) {
      state.findOneFilters.push(filter);
      return queryFor(() => documents.find((item) =>
        String(item._id) === String(filter._id) && String(item.userId) === String(filter.userId)) || null);
    },
  };
}

function makeApp(ChatLogModel, options = {}) {
  return createApp({
    ...options,
    ChatLogModel,
    queryAuthOptions: {
      verifyToken(token) {
        if (token === TOKEN_A) return { sub: USER_A };
        if (token === TOKEN_B) return { sub: USER_B };
        throw new Error('private token verification detail');
      },
    },
  });
}

async function withServer(app, callback) {
  const server = app.listen(0);
  await new Promise((resolve) => server.once('listening', resolve));
  try {
    return await callback('http://127.0.0.1:' + server.address().port);
  } finally {
    await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  }
}

function get(base, path, token) {
  return fetch(base + path, { headers: token ? { Cookie: 'access_token=' + token } : {} });
}

function expectedChat(item) {
  return {
    id: item._id,
    query: item.query,
    jurisdiction: item.jurisdiction,
    answer: item.answer,
    decision: item.decision,
    confidence: item.confidence,
    citations: item.citations,
    abstentionReason: item.abstentionReason,
    createdAt: item.createdAt.toISOString(),
    updatedAt: item.updatedAt.toISOString(),
  };
}

test('unauthenticated chat list and detail requests return 401 without database queries', async () => {
  const model = mockChatLogModel([makeChat('64b000000000000000000010', USER_A)]);
  await withServer(makeApp(model), async (base) => {
    const list = await get(base, '/api/chats');
    const detail = await get(base, '/api/chats/64b000000000000000000010');
    assert.equal(list.status, 401);
    assert.equal(detail.status, 401);
    assert.deepEqual(await list.json(), { error: 'Authentication required.' });
    assert.deepEqual(await detail.json(), { error: 'Authentication required.' });
  });
  assert.equal(model.state.findFilters.length, 0);
  assert.equal(model.state.findOneFilters.length, 0);
});

test('authenticated list is owner-scoped, newest-first, limited to 50, and returns only approved fields', async () => {
  const ownChats = Array.from({ length: 60 }, (_, index) => {
    return makeChat(
      index.toString(16).padStart(24, '0'),
      USER_A,
      new Date(Date.UTC(2026, 0, 1 + index)),
    );
  });
  const otherUserChat = makeChat('64b000000000000000000099', USER_B, new Date('2026-12-31T00:00:00Z'));
  const model = mockChatLogModel([...ownChats, otherUserChat]);

  await withServer(makeApp(model), async (base) => {
    const response = await get(base, '/api/chats?userId=' + USER_B, TOKEN_A);
    assert.equal(response.status, 200);
    const chats = await response.json();
    assert.equal(chats.length, 50);
    assert.equal(chats[0].id, ownChats[59]._id);
    assert.equal(chats[49].id, ownChats[10]._id);
    assert.deepEqual(chats[0], expectedChat(ownChats[59]));
    assert.equal(JSON.stringify(chats).includes(USER_B), false);
    assert.equal(JSON.stringify(chats).includes('passwordHash'), false);
    assert.equal(JSON.stringify(chats).includes('should-not-be-returned'), false);
    assert.equal(JSON.stringify(chats).includes('internalMetadata'), false);
    assert.equal(JSON.stringify(chats).includes(TOKEN_A), false);
  });

  assert.deepEqual(model.state.findFilters, [{ userId: USER_A }]);
  assert.deepEqual(model.state.sorts, [{ createdAt: -1 }]);
  assert.deepEqual(model.state.limits, [50]);
  assert.doesNotMatch(model.state.projections[0], /userId|passwordHash|internalMetadata/);
});

test('authenticated user can retrieve their own chat with only approved fields', async () => {
  const ownChat = makeChat('64b000000000000000000010', USER_A);
  const model = mockChatLogModel([ownChat, makeChat('64b000000000000000000011', USER_B)]);
  await withServer(makeApp(model), async (base) => {
    const response = await get(base, '/api/chats/' + ownChat._id, TOKEN_A);
    assert.equal(response.status, 200);
    const body = await response.json();
    assert.deepEqual(body, expectedChat(ownChat));
    assert.equal('userId' in body, false);
    assert.equal('passwordHash' in body, false);
    assert.equal('access_token' in body, false);
    assert.equal('internalMetadata' in body, false);
  });
  assert.deepEqual(model.state.findOneFilters, [{ _id: ownChat._id, userId: USER_A }]);
  assert.doesNotMatch(model.state.projections[0], /userId|passwordHash|internalMetadata/);
});

test('another user chat and nonexistent chat return the same 404 response', async () => {
  const otherChat = makeChat('64b000000000000000000020', USER_B);
  const model = mockChatLogModel([otherChat]);
  const responses = [];
  await withServer(makeApp(model), async (base) => {
    const other = await get(base, '/api/chats/' + otherChat._id, TOKEN_A);
    const missing = await get(base, '/api/chats/64b000000000000000000021', TOKEN_A);
    responses.push([other.status, await other.json()], [missing.status, await missing.json()]);
  });
  assert.deepEqual(responses, [
    [404, { error: 'Chat not found.' }],
    [404, { error: 'Chat not found.' }],
  ]);
  assert.deepEqual(model.state.findOneFilters, [
    { _id: otherChat._id, userId: USER_A },
    { _id: '64b000000000000000000021', userId: USER_A },
  ]);
});

test('malformed ObjectId returns the same safe 404 without querying MongoDB', async () => {
  const model = mockChatLogModel();
  await withServer(makeApp(model), async (base) => {
    const response = await get(base, '/api/chats/not-an-object-id', TOKEN_A);
    assert.equal(response.status, 404);
    assert.deepEqual(await response.json(), { error: 'Chat not found.' });
  });
  assert.equal(model.state.findOneFilters.length, 0);
});

test('public health endpoint and existing query route remain available', async () => {
  const model = mockChatLogModel();
  const app = makeApp(model, {
    fetchImpl: async (url) => ({
      ok: true,
      status: 200,
      json: async () => url.endsWith('/health')
        ? { status: 'ok' }
        : { answer: 'Answer', decision: 'answer', citations: [] },
    }),
  });

  await withServer(app, async (base) => {
    const health = await get(base, '/api/health/rag');
    assert.equal(health.status, 200);
    assert.deepEqual(await health.json(), { status: 'ok' });
    assert.equal(model.state.created.length, 0);
    const query = await fetch(base + '/api/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Cookie: 'access_token=' + TOKEN_A },
      body: JSON.stringify({ query: 'A question' }),
    });
    assert.equal(query.status, 200);
    assert.deepEqual(await query.json(), { answer: 'Answer', decision: 'answer', citations: [] });
  });
  assert.equal(model.state.created.length, 1);
  assert.equal(model.state.findFilters.length, 0);
  assert.equal(model.state.findOneFilters.length, 0);
});
