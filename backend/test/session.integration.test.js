const { test } = require('node:test');
const assert = require('node:assert/strict');
const jwt = require('jsonwebtoken');
const { createApp } = require('../src/server');

const TEST_SECRET = 'stage-8i-session-integration-test-secret';
const FRONTEND_ORIGIN = 'http://localhost:5173';
const USER = {
  _id: 'session-test-user',
  name: 'Session Test User',
  email: 'session-test@example.com',
  passwordHash: 'mock-hash',
};

function makeChat() {
  const date = new Date('2026-10-12T00:00:00.000Z');
  return {
    _id: '64b000000000000000000010',
    userId: USER._id,
    query: 'What does the example provision say?',
    answer: 'A mocked saved answer.',
    decision: 'answer',
    citations: [],
    createdAt: date,
    updatedAt: date,
  };
}

function makeChatLogModel() {
  const item = makeChat();
  return {
    find(filter) {
      assert.deepEqual(filter, { userId: USER._id });
      const query = {
        select() { return this; },
        sort(order) { assert.deepEqual(order, { createdAt: -1 }); return this; },
        limit(count) { assert.equal(count, 50); return this; },
        async lean() { return [item]; },
      };
      return query;
    },
  };
}

async function withServer(app, callback) {
  const server = app.listen(0);
  await new Promise((resolve) => server.once('listening', resolve));
  try {
    await callback(`http://localhost:${server.address().port}`);
  } finally {
    await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  }
}

test('login cookie authenticates /me and /chats from the configured localhost origin', async () => {
  const app = createApp({
    authOptions: {
      UserModel: {
        async findOne() { return USER; },
        async findById(id) { return id === USER._id ? USER : null; },
      },
      bcryptClient: { async compare() { return true; } },
      jwtSecret: TEST_SECRET,
      jwtExpiresIn: '1h',
      cookieOptions: { httpOnly: true, sameSite: 'lax', secure: false, path: '/' },
    },
    queryAuthOptions: {
      verifyToken(token) { return jwt.verify(token, TEST_SECRET); },
    },
    ChatLogModel: makeChatLogModel(),
  });

  await withServer(app, async (base) => {
    const login = await fetch(`${base}/api/auth/login`, {
      method: 'POST',
      headers: { Origin: FRONTEND_ORIGIN, 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: USER.email, password: 'test-password' }),
    });
    assert.equal(login.status, 200);
    assert.equal(login.headers.get('access-control-allow-origin'), FRONTEND_ORIGIN);
    assert.equal(login.headers.get('access-control-allow-credentials'), 'true');

    const setCookie = login.headers.get('set-cookie');
    assert.match(setCookie, /^access_token=/);
    assert.match(setCookie, /HttpOnly/i);
    assert.match(setCookie, /SameSite=Lax/i);
    assert.match(setCookie, /Path=\//i);
    const cookiePair = setCookie.split(';', 1)[0];
    assert.equal(JSON.stringify(await login.json()).includes(cookiePair.split('=')[1]), false);

    const me = await fetch(`${base}/api/auth/me`, {
      headers: { Origin: FRONTEND_ORIGIN, Cookie: cookiePair },
    });
    assert.equal(me.status, 200);
    assert.deepEqual(await me.json(), {
      user: { id: USER._id, name: USER.name, email: USER.email },
    });

    const chats = await fetch(`${base}/api/chats`, {
      headers: { Origin: FRONTEND_ORIGIN, Cookie: cookiePair },
    });
    assert.equal(chats.status, 200);
    const body = await chats.json();
    assert.equal(body.length, 1);
    assert.equal(body[0].id, '64b000000000000000000010');
    assert.equal('userId' in body[0], false);

    const blockedOrigin = await fetch(`${base}/api/auth/me`, {
      headers: { Origin: 'http://127.0.0.1:5173', Cookie: cookiePair },
    });
    assert.equal(blockedOrigin.status, 200);
    assert.equal(blockedOrigin.headers.get('access-control-allow-origin'), null);
  });
});
