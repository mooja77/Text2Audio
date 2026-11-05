// Behavioural check: runs the REAL web/js sources in a Node VM with fake fetch/audio/DOM.
const vm = require('vm');
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const WEB = path.join(__dirname, '..', 'web', 'js');
const PLAY = '\u25b6';

function resp(ok, status, text) {
  return { ok, status, text: async () => text, blob: async () => ({}) };
}

function env(fetchImpl, playImpl, initialText) {
  const alerts = [], revoked = [], audios = [];
  let refresh = 0;
  const btn = { textContent: initialText };
  const ctx = vm.createContext({
    window: { addEventListener() {} },
    document: { getElementById: () => btn, querySelector: () => null, querySelectorAll: () => [] },
    fetch: fetchImpl,
    URL: { createObjectURL: () => 'blob:fake', revokeObjectURL: u => revoked.push(u) },
    Audio: class { constructor(u) { this.url = u; audios.push(this); } play() { return playImpl(); } },
    localStorage: { getItem() { return null; }, setItem() {}, removeItem() {} },
    console, setTimeout,
  });
  for (const f of ['app.js', 'create.js', 'voices.js']) {
    vm.runInContext(fs.readFileSync(path.join(WEB, f), 'utf8'), ctx, { filename: f });
  }
  const T2A = vm.runInContext('T2A', ctx);
  T2A.refreshHealth = async () => { refresh++; };
  T2A.alert = m => alerts.push(m);
  return { T2A, btn, alerts, revoked, audios, refreshCount: () => refresh,
    Create: vm.runInContext('Create', ctx), Voices: vm.runInContext('Voices', ctx) };
}

const okPlay = () => Promise.resolve();
const scenarios = [
  { name: 'success', fetch: async () => resp(true, 200, ''), play: okPlay, msg: null },
  { name: 'studio unavailable 409', play: okPlay, msg: /No graphics card\./,
    fetch: async () => resp(false, 409, JSON.stringify({ detail: 'No graphics card.', error: 'studio_unavailable' })) },
  { name: 'render busy 409', play: okPlay, msg: /Another audiobook/,
    fetch: async () => resp(false, 409, JSON.stringify({ detail: 'A render is already in progress' })) },
  { name: 'network rejection', play: okPlay, msg: /try again/i,
    fetch: async () => { throw new Error('boom'); } },
  { name: 'audio.play rejection', play: () => Promise.reject(new Error('x')), msg: /try again/i,
    fetch: async () => resp(true, 200, '') },
];

if (process.argv[2]) scenarios.push({
  name: 'actual model recovery 409', play: okPlay, msg: /Install Text2Audio\.bat.*repair/i,
  fetch: async () => resp(false, 409, process.argv[2]),
});

const targets = [
  { label: 'Create.preview', initial: PLAY + ' Preview',
    run: (e) => e.Create.preview(), prefix: '' },
  { label: 'Voices.sample', initial: PLAY + ' Sample',
    run: (e) => e.Voices.sample('af_heart', e.btn), prefix: 'Sample failed: ' },
];

(async () => {
  for (const t of targets) {
    for (const s of scenarios) {
      const where = `${t.label} / ${s.name}`;
      const e = env(s.fetch, s.play, t.initial);
      await t.run(e);
      assert.strictEqual(e.refreshCount(), 1, where + ': health must be refreshed exactly once');
      assert.strictEqual(e.btn.textContent, t.initial, where + ': button must be restored');
      if (s.msg === null) {
        assert.deepStrictEqual(e.alerts, [], where + ': no error expected');
        assert.strictEqual(e.audios.length, 1, where + ': audio played');
        assert.strictEqual(typeof e.audios[0].onended, 'function', where + ': cleanup hook set');
        e.audios[0].onended();
        assert.deepStrictEqual(e.revoked, ['blob:fake'], where + ': object URL revoked');
      } else {
        assert.strictEqual(e.alerts.length, 1, where + ': one actionable error');
        assert.match(e.alerts[0], s.msg, where + ': error text');
        if (t.prefix) assert.ok(e.alerts[0].startsWith(t.prefix), where + ': prefix');
      }
    }
  }
  console.log('ui behaviour ok');
})().catch(err => { console.error(err && err.stack || err); process.exit(1); });
