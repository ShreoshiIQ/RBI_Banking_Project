const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const vm = require('node:vm');

function client(fetch) {
  const nodes = new Map();
  function node() {
    return {
      handlers: {}, children: [], textContent: '',
      addEventListener(event, handler) { this.handlers[event] = handler; },
      append(...children) { this.children.push(...children); },
      replaceChildren(...children) { this.children = children; },
      setAttribute(name, value) { this[name] = value; },
      querySelector() { return this.button || (this.button = { disabled: false }); },
      reset() {}, hidden: false, disabled: false, value: '',
    };
  }
  const context = vm.createContext({
    fetch,
    document: { createElement: node, getElementById(id) {
      if (!nodes.has(id)) nodes.set(id, node());
      return nodes.get(id);
    } },
  });
  vm.runInContext(readFileSync(join(__dirname, '../src/regintel/api/dashboard/app.js'), 'utf8'), context);
  return { context, nodes };
}

test('a stale unauthorized response preserves a newer session', async () => {
  let resolve;
  const { context } = client(() => new Promise(done => { resolve = done; }));
  vm.runInContext('token = "old"', context);
  const pending = vm.runInContext('api("/auth/me")', context);
  vm.runInContext('token = "new"', context);
  resolve({ status: 401 });
  await assert.rejects(pending, /Session changed/);
  assert.equal(vm.runInContext('token', context), 'new');
});

test('an unauthorized response clears its current session', async () => {
  const { context, nodes } = client(async () => ({ status: 401 }));
  vm.runInContext('token = "current"', context);
  await assert.rejects(vm.runInContext('api("/auth/me")', context), /session expired/);
  assert.equal(vm.runInContext('token', context), null);
  assert.equal(nodes.get('workspace').hidden, true);
});

test('requests send the active bearer token', async () => {
  let sent;
  const { context } = client(async (path, options) => {
    sent = { path, options };
    return { status: 200, ok: true, json: async () => ({ id: 1 }) };
  });
  vm.runInContext('token = "current"', context);
  await vm.runInContext('api("/auth/me")', context);
  assert.equal(sent.path, '/api/v1/auth/me');
  assert.equal(sent.options.headers.Authorization, 'Bearer current');
});

test('a second simulation submission does not duplicate a pending request', async () => {
  let finish;
  let calls = 0;
  const { context, nodes } = client(() => { calls++; return new Promise(resolve => { finish = resolve; }); });
  vm.runInContext('token = "current"', context);
  context.document.getElementById('scenario').files = [{ size: 10, text: async () => '{}' }];
  const form = nodes.get('simulation');
  const event = { preventDefault() {}, currentTarget: form };
  const pending = form.handlers.submit(event);
  await Promise.resolve();
  await form.handlers.submit(event);
  assert.equal(calls, 1);
  finish({ status: 401 });
  await pending;
  assert.equal(form.querySelector().disabled, false);
});

function reportResponse(path, status = 'pending_review') {
  const data = path.endsWith('/reviews') ? { reviews: [] } : {
    regulatory_reference: 'Synthetic instrument', assessment_status: 'needs_review',
    review_status: status, report: { findings: [{ status: 'missing',
      requirement: '<img src=x onerror=alert(1)>', explanation: 'Synthetic evidence', evidence: [] }] },
  };
  return { status: 200, ok: true, json: async () => data };
}

test('multimodal upload sends one request while a preview is pending', async () => {
  let finish, sent, calls = 0;
  const { context, nodes } = client((path, options) => {
    calls++; sent = { path, options }; return new Promise(resolve => { finish = resolve; });
  });
  context.FormData = class { append(name, value) { this[name] = value; } };
  vm.runInContext('token = "current"', context);
  const file = { size: 10, name: 'synthetic.xlsx' };
  context.document.getElementById('evidence-file').files = [file];
  const form = nodes.get('evidence-preview');
  const event = { preventDefault() {}, currentTarget: form };
  const pending = form.handlers.submit(event);
  await form.handlers.submit(event);
  assert.equal(calls, 1);
  assert.equal(sent.path, '/api/v1/ingestion/evidence-preview');
  assert.equal(sent.options.body.file, file);
  finish({ status: 401 }); await pending;
  assert.equal(form.querySelector().disabled, false);
});

test('viewer report detail renders untrusted text and hides review controls', async () => {
  const { context, nodes } = client(async path => reportResponse(path));
  vm.runInContext('token = "viewer-token"; role = "viewer"', context);
  await vm.runInContext('showReport("synthetic")', context);
  const children = nodes.get('detail').children;
  assert.equal(children.length, 4);
  assert.equal(children[2].children[0].textContent, 'missing: <img src=x onerror=alert(1)>');
  assert.equal(nodes.get('history').textContent, 'No human decisions recorded.');
});

test('officer review requires rationale and sends only the selected decision', async () => {
  const requests = [];
  let status = 'pending_review';
  const { context, nodes } = client(async (path, options) => {
    if (options.method === 'POST') { requests.push(options); status = 'rejected'; }
    return reportResponse(path, status);
  });
  vm.runInContext('token = "officer-token"; role = "compliance_officer"', context);
  await vm.runInContext('showReport("synthetic")', context);
  const form = nodes.get('detail').children.at(-1);
  const event = { preventDefault() {} };
  await form.handlers.submit(event);
  assert.equal(requests.length, 0);
  assert.equal(nodes.get('message').textContent, 'A review rationale is required.');
  form.children[0].children[0].value = '  Synthetic rejection rationale  ';
  form.children[1].value = 'rejected';
  await form.handlers.submit(event);
  assert.deepEqual(JSON.parse(requests[0].body), { decision: 'rejected', comment: 'Synthetic rejection rationale' });
  assert.equal(requests[0].headers.Authorization, 'Bearer officer-token');
  assert.equal(nodes.get('detail').children.length, 4);
  assert.equal(nodes.get('message').textContent, 'Human decision recorded.');
});
