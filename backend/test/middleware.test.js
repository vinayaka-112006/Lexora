const { test } = require('node:test');
const assert = require('node:assert/strict');
const jwt = require('jsonwebtoken');
const { createAuthMiddleware } = require('../src/middleware/auth');
const { verifyAccessToken } = require('../src/utils/auth');

const TEST_SECRET = 'stage-8c-test-signing-key';

function runMiddleware(cookie, verifier = (token) => verifyAccessToken(token, { secret: TEST_SECRET })) {
  const req = { headers: cookie === undefined ? {} : { cookie } };
  const res = {
    statusCode: null,
    body: null,
    status(code) { this.statusCode = code; return this; },
    json(body) { this.body = body; return this; },
  };
  let nextCalled = false;
  createAuthMiddleware({ verifyToken: verifier })(req, res, () => { nextCalled = true; });
  return { req, res, nextCalled };
}

function signToken(secret = TEST_SECRET, expiresIn = '1h') {
  return jwt.sign({ sub: 'user-42' }, secret, { expiresIn });
}

test('missing cookie returns safe 401 without verifying or calling next', () => {
  let verified = false;
  const result = runMiddleware(undefined, () => { verified = true; });
  assert.equal(result.res.statusCode, 401);
  assert.deepEqual(result.res.body, { error: 'Authentication required.' });
  assert.equal(result.nextCalled, false);
  assert.equal(verified, false);
});

test('valid JWT attaches only subject as req.user.id and calls next', () => {
  const result = runMiddleware('access_token=' + signToken());
  assert.equal(result.nextCalled, true);
  assert.deepEqual(result.req.user, { id: 'user-42' });
  assert.equal(result.res.statusCode, null);
});

test('invalid JWT returns safe 401 without verification details', () => {
  const result = runMiddleware('access_token=' + signToken('wrong-test-signing-key'));
  assert.equal(result.res.statusCode, 401);
  assert.deepEqual(result.res.body, { error: 'Authentication required.' });
  assert.equal(result.nextCalled, false);
  assert.equal(JSON.stringify(result.res.body).includes('invalid signature'), false);
});

test('expired JWT returns safe 401', () => {
  const result = runMiddleware('access_token=' + signToken(TEST_SECRET, -1));
  assert.equal(result.res.statusCode, 401);
  assert.deepEqual(result.res.body, { error: 'Authentication required.' });
  assert.equal(result.nextCalled, false);
});

test('malformed JWT returns safe 401', () => {
  const result = runMiddleware('access_token=not.a.valid.jwt');
  assert.equal(result.res.statusCode, 401);
  assert.deepEqual(result.res.body, { error: 'Authentication required.' });
  assert.equal(result.nextCalled, false);
});
