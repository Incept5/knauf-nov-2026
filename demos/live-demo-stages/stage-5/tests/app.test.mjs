/**
 * Tests for the Gipsplatten-Lieferprotokoll app in ../index.html.
 *
 * The page is loaded in jsdom with `fetch` and `confirm` stubbed, so the
 * real inline script runs unmodified. Dates are computed relative to the
 * real "today" so the seeded data always covers late/today/scheduled.
 */
import { describe, test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { JSDOM } from 'jsdom';

const HTML = readFileSync(fileURLToPath(new URL('../index.html', import.meta.url)), 'utf8');
const SCRIPT = HTML.match(/<script>([\s\S]*?)<\/script>/)[1];
// The app's storage key contains a literal U+2026 ('kna…s.v1'); read it from
// the source instead of hard-coding it so the tests can't drift from the app.
const LS_KEY = SCRIPT.match(/var LS_KEY = '([^']+)'/)[1];

// ---------- date helpers (mirror the app's local-date semantics) ----------
function iso(d) {
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${m}-${day}`;
}
function shift(n) {
  const d = new Date();
  d.setDate(d.getDate() + n);
  return iso(d);
}
const TODAY = iso(new Date());
const DOW = (new Date().getDay() + 6) % 7; // Mon = 0 … Sun = 6

// ---------- jsdom harness ----------
function weatherResponse(url) {
  const u = new URL(url);
  const start = u.searchParams.get('start_date');
  const end = u.searchParams.get('end_date');
  const time = [];
  for (let d = new Date(start + 'T00:00:00'); ; d.setDate(d.getDate() + 1)) {
    time.push(iso(d));
    if (iso(d) === end) break;
  }
  return {
    ok: true,
    status: 200,
    json: async () => ({
      daily: {
        time,
        weather_code: time.map(() => 61),
        temperature_2m_max: time.map(() => 21.4),
        temperature_2m_min: time.map(() => 8.6),
        precipitation_sum: time.map(() => 2),
      },
    }),
  };
}

function loadApp({ seed, fetchImpl, confirmResult = true } = {}) {
  const fetchCalls = [];
  // Parse without executing scripts, seed localStorage for the real origin,
  // then run the page's inline script — equivalent to the real load order
  // (the script sits at the end of <body>).
  const dom = new JSDOM(HTML, { url: 'http://localhost/', runScripts: 'outside-only' });
  const { window } = dom;
  const doc = window.document;
  if (seed !== undefined) window.localStorage.setItem(LS_KEY, seed);
  window.fetch = (url) => {
    fetchCalls.push(url);
    return fetchImpl ? fetchImpl(url) : Promise.resolve(weatherResponse(url));
  };
  window.confirm = () => confirmResult;
  window.eval(SCRIPT);
  return {
    dom,
    window,
    doc,
    fetchCalls,
    click(el) {
      el.dispatchEvent(new window.MouseEvent('click', { bubbles: true, cancelable: true }));
    },
    submit(form) {
      form.dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true }));
    },
    stored() {
      return JSON.parse(window.localStorage.getItem(LS_KEY));
    },
    rows() {
      return [...doc.querySelectorAll('#rows tr')];
    },
    rowByText(text) {
      return this.rows().find((tr) => tr.textContent.includes(text));
    },
    badgeOf(text) {
      return this.rowByText(text).querySelector('.badge').textContent;
    },
    relOf(text) {
      return this.rowByText(text).querySelector('.rel').textContent;
    },
    cols() {
      return [...doc.querySelectorAll('#cal-grid .cal-day')];
    },
    async settle() {
      await new Promise((r) => setTimeout(r, 0));
      await new Promise((r) => setTimeout(r, 0));
    },
  };
}

function seedJson(list) {
  return JSON.stringify(list.map((x, i) => ({ delivered: false, id: 'd' + i, ...x })));
}

// ---------------------------------------------------------------------------
describe('initial render (built-in seed)', () => {
  test('stats show 2 overdue, 1 due today, 1 scheduled, 1 delivered', async () => {
    const app = loadApp();
    await app.settle();
    const q = (sel) => app.doc.querySelector(sel).textContent;
    assert.equal(q('.stat.late .num'), '2');
    assert.equal(q('.stat.today .num'), '1');
    assert.equal(q('.stat:not(.late):not(.today) .num'), '1'); // scheduled
    assert.equal(app.rows().length, 5);
    assert.equal(app.doc.getElementById('empty').hidden, true);
  });

  test('rows are sorted by date and carry the right badge and relative label', async () => {
    const app = loadApp();
    await app.settle();
    assert.match(app.rows()[0].textContent, /Olympiapark Sanierung/); // oldest first
    assert.match(app.rows().at(-1).textContent, /Pasing Arcaden/); // newest last
    assert.equal(app.badgeOf('Olympiapark Sanierung'), 'Überfällig');
    assert.equal(app.badgeOf('Laim Business Campus'), 'Geliefert');
    assert.equal(app.badgeOf('Schwabing Parkside'), 'Überfällig');
    assert.equal(app.badgeOf('Marienhof Quartier'), 'Heute fällig');
    assert.equal(app.badgeOf('Pasing Arcaden'), 'Geplant');
    assert.equal(app.relOf('Olympiapark Sanierung'), '6 Tage überfällig');
    assert.equal(app.relOf('Laim Business Campus'), 'vor 3 Tagen');
    assert.equal(app.relOf('Marienhof Quartier'), 'Heute');
    assert.equal(app.relOf('Pasing Arcaden'), 'in 4 Tagen');
  });

  test('quantity is formatted with the de-DE thousands separator', async () => {
    const app = loadApp({ seed: seedJson([{ supplier: 'S', site: 'T', quantity: 1234, date: shift(3) }]) });
    await app.settle();
    assert.equal(app.rowByText('T').querySelector('td.num').textContent, '1.234');
  });

  test('date field defaults to today', async () => {
    const app = loadApp();
    await app.settle();
    assert.equal(app.doc.getElementById('date').value, TODAY);
  });
});

// ---------------------------------------------------------------------------
describe('filters', () => {
  test('clicking a filter narrows the table and moves the active class', async () => {
    const app = loadApp();
    await app.settle();
    app.click(app.doc.querySelector('#filters button[data-filter="late"]'));
    assert.equal(app.rows().length, 2);
    for (const tr of app.rows()) assert.equal(tr.querySelector('.badge').textContent, 'Überfällig');
    assert.equal(app.doc.querySelector('#filters button[data-filter="late"]').classList.contains('active'), true);
    assert.equal(app.doc.querySelector('#filters button[data-filter="all"]').classList.contains('active'), false);

    app.click(app.doc.querySelector('#filters button[data-filter="delivered"]'));
    assert.equal(app.rows().length, 1);
    assert.match(app.rows()[0].textContent, /Laim Business Campus/);

    app.click(app.doc.querySelector('#filters button[data-filter="all"]'));
    assert.equal(app.rows().length, 5);
  });

  test('empty message shows when a filter matches nothing', async () => {
    const app = loadApp({ seed: seedJson([{ supplier: 'S', site: 'T', quantity: 10, date: shift(5) }]) });
    await app.settle();
    app.click(app.doc.querySelector('#filters button[data-filter="delivered"]'));
    assert.equal(app.rows().length, 0);
    assert.equal(app.doc.getElementById('empty').hidden, false);
  });
});

// ---------------------------------------------------------------------------
describe('add form', () => {
  test('valid submission appends a delivery, persists it and resets the form', async () => {
    const app = loadApp();
    await app.settle();
    app.doc.getElementById('supplier').value = 'Knauf Iphofen';
    app.doc.getElementById('site').value = 'Neubau Test';
    app.doc.getElementById('quantity').value = '120';
    app.doc.getElementById('date').value = shift(2);
    app.submit(app.doc.getElementById('addForm'));
    await app.settle();

    assert.equal(app.rows().length, 6);
    const added = app.stored().at(-1);
    assert.equal(added.supplier, 'Knauf Iphofen');
    assert.equal(added.site, 'Neubau Test');
    assert.equal(added.quantity, 120); // stored as a number
    assert.equal(added.date, shift(2));
    assert.equal(added.delivered, false);
    assert.equal(app.doc.getElementById('supplier').value, ''); // form was reset
    assert.equal(app.doc.getElementById('date').value, TODAY);   // date re-defaults to today
  });

  test('rejects a quantity of zero', async () => {
    const app = loadApp();
    await app.settle();
    app.doc.getElementById('supplier').value = 'S';
    app.doc.getElementById('site').value = 'T';
    app.doc.getElementById('quantity').value = '0';
    app.doc.getElementById('date').value = shift(1);
    app.submit(app.doc.getElementById('addForm'));
    await app.settle();
    assert.equal(app.rows().length, 5);
  });

  test('rejects an empty supplier', async () => {
    const app = loadApp();
    await app.settle();
    app.doc.getElementById('supplier').value = '   ';
    app.doc.getElementById('site').value = 'T';
    app.doc.getElementById('quantity').value = '5';
    app.doc.getElementById('date').value = shift(1);
    app.submit(app.doc.getElementById('addForm'));
    await app.settle();
    assert.equal(app.rows().length, 5);
  });

  test('escapes HTML in user input (no injection)', async () => {
    const evil = '<img src=x onerror=alert(1)>';
    const app = loadApp();
    await app.settle();
    app.doc.getElementById('supplier').value = evil;
    app.doc.getElementById('site').value = 'XSS-Kartei-9';
    app.doc.getElementById('quantity').value = '5';
    app.doc.getElementById('date').value = shift(1);
    app.submit(app.doc.getElementById('addForm'));
    await app.settle();
    assert.equal(app.doc.querySelector('#rows img'), null);
    assert.equal(app.rowByText('XSS-Kartei-9').querySelector('td[data-label="Lieferant"]').textContent, evil);
  });
});

// ---------------------------------------------------------------------------
describe('row actions', () => {
  test('marking as delivered updates state, badge and storage', async () => {
    const app = loadApp({ seed: seedJson([{ supplier: 'S', site: 'T1', quantity: 10, date: shift(3), id: 'a1' }]) });
    await app.settle();
    app.click(app.doc.querySelector('#rows button[data-act="deliver"][data-id="a1"]'));
    assert.equal(app.stored()[0].delivered, true);
    assert.equal(app.badgeOf('T1'), 'Geliefert');
    assert.equal(app.doc.querySelector('#rows button[data-act="deliver"][data-id="a1"]'), null);
    assert.ok(app.doc.querySelector('#rows button[data-act="undo"][data-id="a1"]'));
  });

  test('undo restores the previous status', async () => {
    const app = loadApp({ seed: seedJson([{ supplier: 'S', site: 'T1', quantity: 10, date: shift(3), delivered: true, id: 'a1' }]) });
    await app.settle();
    assert.equal(app.badgeOf('T1'), 'Geliefert');
    app.click(app.doc.querySelector('#rows button[data-act="undo"][data-id="a1"]'));
    assert.equal(app.stored()[0].delivered, false);
    assert.equal(app.badgeOf('T1'), 'Geplant');
  });

  test('delete removes the row when confirmed', async () => {
    const app = loadApp({ seed: seedJson([{ supplier: 'S', site: 'T1', quantity: 10, date: shift(3), id: 'a1' }]), confirmResult: true });
    await app.settle();
    app.click(app.doc.querySelector('#rows button[data-act="delete"][data-id="a1"]'));
    assert.equal(app.stored().length, 0);
    assert.equal(app.rows().length, 0);
    assert.equal(app.doc.getElementById('empty').hidden, false);
  });

  test('delete keeps the row when the confirmation is cancelled', async () => {
    const app = loadApp({ seed: seedJson([{ supplier: 'S', site: 'T1', quantity: 10, date: shift(3), id: 'a1' }]), confirmResult: false });
    await app.settle();
    app.click(app.doc.querySelector('#rows button[data-act="delete"][data-id="a1"]'));
    assert.equal(app.stored().length, 1);
    assert.equal(app.rows().length, 1);
  });
});

// ---------------------------------------------------------------------------
describe('weekly calendar', () => {
  test('renders seven Mo–So columns and marks today', async () => {
    const app = loadApp();
    await app.settle();
    const cols = app.cols();
    assert.equal(cols.length, 7);
    assert.deepEqual(
      cols.map((c) => c.querySelector('.day-head').textContent.trim().slice(0, 2)),
      ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']
    );
    const todayCol = cols.find((c) => c.dataset.date === TODAY);
    assert.ok(todayCol.classList.contains('today'));
  });

  test('week navigation moves the visible week and back', async () => {
    const app = loadApp();
    await app.settle();
    app.click(app.doc.getElementById('cal-next'));
    assert.equal(app.cols()[0].dataset.date, shift(-DOW + 7)); // next Monday
    app.click(app.doc.getElementById('cal-prev'));
    assert.equal(app.cols()[0].dataset.date, shift(-DOW)); // back to this Monday
    app.click(app.doc.getElementById('cal-next'));
    app.click(app.doc.getElementById('cal-today'));
    assert.equal(app.cols()[0].dataset.date, shift(-DOW));
  });

  test('tap-to-move reschedules a delivery and persists it', async () => {
    const app = loadApp({ seed: seedJson([{ supplier: 'S', site: 'T1', quantity: 10, date: TODAY, id: 'm1' }]) });
    await app.settle();
    app.click(app.doc.querySelector('#cal-grid .chip[data-id="m1"]'));
    assert.ok(app.doc.querySelector('#cal-grid .chip.selected'), 'chip should be selected after first tap');
    const target = app.cols().find((c) => c.dataset.date !== TODAY);
    app.click(target);
    assert.equal(app.stored()[0].date, target.dataset.date);
  });

  test('tapping outside the calendar cancels a pending move', async () => {
    const app = loadApp({ seed: seedJson([{ supplier: 'S', site: 'T1', quantity: 10, date: TODAY, id: 'm1' }]) });
    await app.settle();
    app.click(app.doc.querySelector('#cal-grid .chip[data-id="m1"]'));
    app.click(app.doc.body);
    assert.equal(app.doc.querySelector('#cal-grid .chip.selected'), null);
    assert.equal(app.stored()[0].date, TODAY);
  });
});

// ---------------------------------------------------------------------------
describe('weather (Open-Meteo)', () => {
  test('fetches the forecast and renders icon, temperatures and precipitation', async () => {
    const app = loadApp();
    await app.settle();
    assert.ok(app.fetchCalls.length >= 1, 'expected a forecast request');
    const url = app.fetchCalls[0];
    assert.match(url, /api\.open-meteo\.com\/v1\/forecast/);
    assert.match(url, /latitude=48\.1351/);
    assert.match(url, /longitude=11\.582/);
    assert.match(url, /daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum/);
    assert.match(url, /timezone=Europe%2FBerlin/);
    const cell = app.rowByText('Marienhof Quartier').querySelector('td[data-label="Wetter München"]');
    assert.equal(cell.querySelector('.wx .tmp').textContent, '21°/9°');
    assert.equal(cell.querySelector('.wx .prc').textContent, ' · 2 mm');
    assert.match(cell.querySelector('.wx').getAttribute('title'), /Open-Meteo/);
  });

  test('a failed request shows the error note and dashes, and Retry recovers', async () => {
    let calls = 0;
    const app = loadApp({
      fetchImpl: (url) => {
        calls++;
        return calls === 1 ? Promise.reject(new Error('boom')) : Promise.resolve(weatherResponse(url));
      },
    });
    await app.settle();
    const note = app.doc.getElementById('wx-note');
    assert.equal(note.hidden, false);
    assert.match(app.doc.getElementById('wx-note-text').textContent, /Open-Meteo/);
    assert.equal(app.rowByText('Marienhof Quartier').querySelector('.wx.none').textContent, '—');

    app.click(app.doc.getElementById('wx-retry'));
    await app.settle();
    assert.equal(note.hidden, true);
    assert.equal(app.rowByText('Marienhof Quartier').querySelector('.wx .tmp').textContent, '21°/9°');
  });

  test('dates outside the forecast window are not requested and show a dash', async () => {
    const far = shift(200); // beyond the 16-day forecast horizon
    const app = loadApp({ seed: seedJson([{ supplier: 'S', site: 'Weit weg', quantity: 5, date: far, id: 'f1' }]) });
    await app.settle();
    for (const url of app.fetchCalls) {
      assert.ok(new URL(url).searchParams.get('end_date') < far, 'far date must never be requested');
    }
    const cell = app.rowByText('Weit weg').querySelector('td[data-label="Wetter München"]');
    assert.equal(cell.querySelector('.wx.none').textContent, '–');
    assert.match(cell.querySelector('.wx.none').getAttribute('title'), /Keine Vorhersage/);
  });
});

// ---------------------------------------------------------------------------
describe('persistence', () => {
  test('corrupted localStorage reseeds the demo data', async () => {
    const app = loadApp({ seed: '{not valid json' });
    await app.settle();
    assert.equal(app.stored().length, 5);
    assert.equal(app.rows().length, 5);
  });

  test('changes survive a reload (localStorage round-trip)', async () => {
    const app1 = loadApp({ seed: seedJson([{ supplier: 'S', site: 'T1', quantity: 10, date: shift(3), id: 'p1' }]) });
    await app1.settle();
    app1.click(app1.doc.querySelector('#rows button[data-act="deliver"][data-id="p1"]'));
    const raw = app1.window.localStorage.getItem(LS_KEY);

    const app2 = loadApp({ seed: raw });
    await app2.settle();
    assert.equal(app2.stored()[0].delivered, true);
    assert.equal(app2.badgeOf('T1'), 'Geliefert');
  });
});
