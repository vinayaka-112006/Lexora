const { test } = require('node:test');
const assert = require('node:assert/strict');
const ChatLog = require('../src/models/ChatLog');

test('ChatLog schema has required ownership and response fields with timestamps', async () => {
  const schema = ChatLog.schema;
  assert.equal(schema.path('userId').instance, 'ObjectId');
  assert.equal(schema.path('userId').options.ref, 'User');
  assert.equal(schema.path('userId').isRequired, true);
  assert.equal(schema.path('query').isRequired, true);
  assert.equal(schema.path('answer').isRequired, true);
  assert.equal(schema.path('decision').isRequired, true);
  assert.equal(schema.path('confidence').instance, 'Number');
  assert.equal(schema.path('citations').instance, 'Array');
  assert.equal(schema.path('abstentionReason').instance, 'String');
  assert.equal(schema.options.timestamps, true);
  assert.equal(schema.options.autoIndex, false);
  assert.deepEqual(new ChatLog().citations, []);

  await assert.rejects(new ChatLog({}).validate(), (error) => {
    assert.ok(error.errors.userId);
    assert.ok(error.errors.query);
    assert.ok(error.errors.answer);
    assert.ok(error.errors.decision);
    return true;
  });
});
