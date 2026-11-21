const { afterEach, test } = require('node:test');
const assert = require('node:assert/strict');
const { createApp } = require('../src/server');

const TEST_SECRET = 'unit-test-secret-never-used-outside-tests';
const JWT_SECRET_BEFORE = process.env.JWT_SECRET;

function mockUserModel({ existingUser = null } = {}) {
  const state = { existingUser, created: [], lookups: [] };
  return {
    state,
    async findOne(filter) { state.lookups.push(filter); return state.existingUser; },
    async findById(id) { state.lookups.push({ _id: id }); return state.existingUser; },
    async create(document) {
      state.created.push(document);
      return { _id: 'user-id-1', name: document.name, email: document.email, ...document };
    },
  };
}

function makeApp({ UserModel, bcryptClient, jwtClient, authMiddleware } = {}) {
  return createApp({
    authOptions: {
      UserModel: UserModel || mockUserModel(),
      bcryptClient: bcryptClient || {
        async hash(value) { return 'hashed:' + value; },
        async compare(value, hash) { return hash === 'hashed:' + value; },
      },
      jwtClient: jwtClient || {
        sign(payload, secret, options) {
          assert.equal(secret, TEST_SECRET);
          assert.deepEqual(payload, { sub: 'user-id-1' });
          assert.equal(options.expiresIn, '7d');
          return 'mock.jwt.token';
        },
      },
      jwtSecret: TEST_SECRET,
      jwtExpiresIn: '7d',
      cookieOptions: { httpOnly: true, sameSite: 'lax', secure: false, path: '/' },
      authMiddleware,
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

async function post(base, path, body) {
  return fetch(base + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

async function get(base, path, cookie) {
  return fetch(base + path, { headers: cookie ? { Cookie: cookie } : {} });
}

function testAuthMiddleware(req, res, next) {
  const cookie = req.headers.cookie || '';
  if (!cookie.includes('access_token=valid-token')) return res.status(401).json({ error: 'Authentication required.' });
  req.user = { id: 'user-id-1' };
  return next();
}

afterEach(() => {
  if (JWT_SECRET_BEFORE === undefined) delete process.env.JWT_SECRET;
  else process.env.JWT_SECRET = JWT_SECRET_BEFORE;
});

test('registration hashes password and returns safe normalized user information', async () => {
  const UserModel = mockUserModel();
  let hashedInput;
  await withServer(makeApp({
    UserModel,
    bcryptClient: { async hash(value) { hashedInput = value; return 'bcrypt-hash'; } },
  }), async (base) => {
    const response = await post(base, '/api/auth/register', {
      name: ' Example User ', email: 'USER@Example.COM ', password: 'strong-password',
    });
    assert.equal(response.status, 201);
    const body = await response.json();
    assert.deepEqual(body, { user: { id: 'user-id-1', name: 'Example User', email: 'user@example.com' } });
    assert.equal(JSON.stringify(body).includes('passwordHash'), false);
    assert.equal(JSON.stringify(body).includes(TEST_SECRET), false);
  });
  assert.equal(hashedInput, 'strong-password');
  assert.deepEqual(UserModel.state.created, [{
    name: 'Example User', email: 'user@example.com', passwordHash: 'bcrypt-hash',
  }]);
  assert.equal(JSON.stringify(UserModel.state.created).includes('strong-password'), false);
});

test('duplicate email returns 409 without database details', async () => {
  const UserModel = mockUserModel({ existingUser: { _id: 'existing', email: 'user@example.com' } });
  await withServer(makeApp({ UserModel }), async (base) => {
    const response = await post(base, '/api/auth/register', {
      name: 'Example', email: 'user@example.com', password: 'strong-password',
    });
    assert.equal(response.status, 409);
    assert.deepEqual(await response.json(), { error: 'An account with this email already exists.' });
    assert.equal(UserModel.state.created.length, 0);
  });
});

test('registration rejects empty name, invalid email, and short password', async () => {
  await withServer(makeApp(), async (base) => {
    const emptyName = await post(base, '/api/auth/register', {
      name: ' ', email: 'user@example.com', password: 'strong-password',
    });
    const invalidEmail = await post(base, '/api/auth/register', {
      name: 'Example', email: 'not-an-email', password: 'strong-password',
    });
    const shortPassword = await post(base, '/api/auth/register', {
      name: 'Example', email: 'user@example.com', password: 'short',
    });
    assert.equal(emptyName.status, 400);
    assert.equal(invalidEmail.status, 400);
    assert.equal(shortPassword.status, 400);
  });
});

test('valid login verifies password, sets HTTP-only lax cookie, and omits JWT from JSON', async () => {
  const UserModel = mockUserModel({
    existingUser: { _id: 'user-id-1', name: 'Example User', email: 'user@example.com', passwordHash: 'stored-hash' },
  });
  let compared;
  await withServer(makeApp({
    UserModel,
    bcryptClient: { async compare(password, passwordHash) { compared = { password, passwordHash }; return true; } },
  }), async (base) => {
    const response = await post(base, '/api/auth/login', { email: 'USER@Example.COM ', password: 'strong-password' });
    assert.equal(response.status, 200);
    const body = await response.json();
    assert.deepEqual(body, { user: { id: 'user-id-1', name: 'Example User', email: 'user@example.com' } });
    const cookie = response.headers.get('set-cookie');
    assert.match(cookie, /access_token=mock\.jwt\.token/);
    assert.match(cookie, /HttpOnly/i);
    assert.match(cookie, /SameSite=Lax/i);
    assert.match(cookie, /Path=\//i);
    assert.doesNotMatch(cookie, /;\s*(?:Max-Age|Expires)=/i);
    assert.equal(cookie.toLowerCase().includes('secure'), false);
    assert.equal(JSON.stringify(body).includes('mock.jwt.token'), false);
    assert.equal(JSON.stringify(body).includes(TEST_SECRET), false);
  });
  assert.deepEqual(compared, { password: 'strong-password', passwordHash: 'stored-hash' });
  assert.deepEqual(UserModel.state.lookups, [{ email: 'user@example.com' }]);
});

test('wrong password and nonexistent account return the same generic 401', async () => {
  const responses = [];
  const wrongPasswordApp = makeApp({
    UserModel: mockUserModel({
      existingUser: { _id: 'user-id-1', name: 'Example', email: 'user@example.com', passwordHash: 'stored-hash' },
    }),
    bcryptClient: { async compare() { return false; } },
  });
  const missingUserApp = makeApp({ UserModel: mockUserModel() });
  await withServer(wrongPasswordApp, async (base) => {
    const response = await post(base, '/api/auth/login', { email: 'user@example.com', password: 'wrong-password' });
    responses.push([response.status, await response.json()]);
  });
  await withServer(missingUserApp, async (base) => {
    const response = await post(base, '/api/auth/login', { email: 'missing@example.com', password: 'wrong-password' });
    responses.push([response.status, await response.json()]);
  });
  assert.deepEqual(responses, [
    [401, { error: 'Invalid email or password.' }],
    [401, { error: 'Invalid email or password.' }],
  ]);
});

test('login normalizes email before lookup', async () => {
  const UserModel = mockUserModel();
  await withServer(makeApp({ UserModel }), async (base) => {
    await post(base, '/api/auth/login', { email: ' USER@Example.COM ', password: 'password' });
  });
  assert.deepEqual(UserModel.state.lookups, [{ email: 'user@example.com' }]);
});

test('duplicate-key race returns safe HTTP 409', async () => {
  const UserModel = mockUserModel();
  UserModel.create = async () => { const error = new Error('private database details'); error.code = 11000; throw error; };
  await withServer(makeApp({ UserModel }), async (base) => {
    const response = await post(base, '/api/auth/register', {
      name: 'Example', email: 'user@example.com', password: 'strong-password',
    });
    assert.equal(response.status, 409);
    assert.equal((await response.text()).includes('private database details'), false);
  });
});

test('query rejects requests without a valid cookie', async () => {
  let calls = 0;
  const app = createApp({
    fetchImpl: async () => { calls += 1; return { ok: true, status: 200, json: async () => ({ decision: 'answer' }) }; },
    authOptions: { UserModel: mockUserModel() },
  });
  await withServer(app, async (base) => {
    const response = await post(base, '/api/query', { query: 'test query' });
    assert.equal(response.status, 401);
  });
  assert.equal(calls, 0);
});

test('GET /me rejects a missing cookie', async () => {
  await withServer(makeApp({ authMiddleware: testAuthMiddleware }), async (base) => {
    const response = await get(base, '/api/auth/me');
    assert.equal(response.status, 401);
  });
});

test('GET /me rejects an invalid cookie', async () => {
  await withServer(makeApp({ authMiddleware: testAuthMiddleware }), async (base) => {
    const response = await get(base, '/api/auth/me', 'access_token=invalid-token');
    assert.equal(response.status, 401);
  });
});

test('GET /me returns only safe fields for the authenticated user', async () => {
  const UserModel = mockUserModel({ existingUser: {
    _id: 'user-id-1', name: 'Example User', email: 'user@example.com', passwordHash: 'never-return-this',
  } });
  await withServer(makeApp({ UserModel, authMiddleware: testAuthMiddleware }), async (base) => {
    const response = await get(base, '/api/auth/me', 'access_token=valid-token');
    assert.equal(response.status, 200);
    const body = await response.json();
    assert.deepEqual(body, { user: { id: 'user-id-1', name: 'Example User', email: 'user@example.com' } });
    assert.equal(JSON.stringify(body).includes('passwordHash'), false);
    assert.equal(JSON.stringify(body).includes('valid-token'), false);
    assert.deepEqual(UserModel.state.lookups, [{ _id: 'user-id-1' }]);
  });
});

test('GET /me rejects a valid session when its user no longer exists', async () => {
  const UserModel = mockUserModel();
  await withServer(makeApp({ UserModel, authMiddleware: testAuthMiddleware }), async (base) => {
    const response = await get(base, '/api/auth/me', 'access_token=valid-token');
    assert.equal(response.status, 401);
    assert.deepEqual(await response.json(), { error: 'Authentication required.' });
  });
});

test('POST /logout expires access_token without authentication or token exposure', async () => {
  await withServer(makeApp(), async (base) => {
    const response = await post(base, '/api/auth/logout', {});
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { message: 'Logged out.' });
    const cookie = response.headers.get('set-cookie');
    assert.match(cookie, /^access_token=;/);
    assert.match(cookie, /Expires=Thu, 01 Jan 1970/i);
    assert.match(cookie, /HttpOnly/i);
    assert.match(cookie, /Path=\//i);
    assert.equal(cookie.includes('mock.jwt.token'), false);
  });
});
