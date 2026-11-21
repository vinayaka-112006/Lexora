const test = require('node:test');
const assert = require('node:assert/strict');
const User = require('../src/models/User');
const { connectDB } = require('../src/config/db');
const { startServer } = require('../src/server');

test('User schema requires email and passwordHash and configures normalized unique email and timestamps', async () => {
  const schema = User.schema;
  const email = schema.path('email');
  const passwordHash = schema.path('passwordHash');

  assert.equal(email.isRequired, true);
  assert.equal(email.options.unique, true);
  assert.equal(email.options.lowercase, true);
  assert.equal(email.options.trim, true);
  assert.equal(passwordHash.isRequired, true);
  assert.equal(schema.options.timestamps, true);
  assert.equal(schema.options.autoIndex, false);

  await assert.rejects(new User({}).validate(), (error) => {
    assert.ok(error.errors.email);
    assert.ok(error.errors.passwordHash);
    return true;
  });
});

test('connectDB rejects a missing MongoDB setting without connecting', async () => {
  let called = false;
  const fakeMongoose = {
    connection: { readyState: 0 },
    async connect() { called = true; },
  };

  await assert.rejects(connectDB({ mongooseClient: fakeMongoose, uri: '' }), /MONGODB_URI is not configured/);
  assert.equal(called, false);
});

test('connectDB uses configured URI and returns the established connection', async () => {
  const connection = { readyState: 0 };
  let receivedUri;
  const fakeMongoose = {
    connection,
    async connect(uri, options) {
      receivedUri = uri;
      assert.equal(options.serverSelectionTimeoutMS, 10000);
    },
  };

  assert.equal(await connectDB({ mongooseClient: fakeMongoose, uri: 'mock-uri' }), connection);
  assert.equal(receivedUri, 'mock-uri');
});

test('connectDB sanitizes connection errors', async () => {
  const fakeMongoose = {
    connection: { readyState: 0 },
    async connect() { throw new Error('mock-secret-detail'); },
  };

  await assert.rejects(connectDB({ mongooseClient: fakeMongoose, uri: 'mock-uri' }), (error) => {
    assert.equal(error.message, 'MongoDB connection failed');
    assert.equal(error.message.includes('mock-secret-detail'), false);
    return true;
  });
});

test('server continues serving when MongoDB connection fails and logs no connection details', async (t) => {
  const originalError = console.error;
  const logged = [];
  console.error = (...args) => logged.push(args.join(' '));
  t.after(() => { console.error = originalError; });

  const server = await startServer({
    connectDatabase: async () => { throw new Error('mock-secret-detail'); },
    port: 0,
  });
  t.after(() => new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve())));

  assert.ok(server.address().port > 0);
  assert.match(logged.join(' '), /continuing without database access/);
  assert.equal(logged.join(' ').includes('mock-secret-detail'), false);
});
