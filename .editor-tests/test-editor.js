/**
 * Headless smoke test for the timing editor (jsdom).
 * Simulates: JSON load, audio metadata, play/pause, click start/end,
 * Space commit, undo, save, re-load of saved JSON.
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const FRONTEND = '/workspace/karaoke-builder/frontend';
const html = fs.readFileSync(path.join(FRONTEND, 'editor.html'), 'utf-8');
const js = fs.readFileSync(path.join(FRONTEND, 'js/editor.js'), 'utf-8');

// Realistic karaoke.json (simple format from the task spec)
const KARAOKE = {
    title: 'Тестовая песня',
    lyrics: [
        { start: 11.438, end: 12.318, text: 'Первая строка' },
        { start: 12.318, end: 20.359, text: 'Вторая строка' },
        { start: 20.359, end: 27.49, text: 'Третья строка' },
    ],
};

let failures = 0;
function check(name, cond, extra) {
    if (cond) console.log('PASS  ' + name);
    else { failures++; console.log('FAIL  ' + name + (extra !== undefined ? ' -> ' + JSON.stringify(extra) : '')); }
}

const dom = new JSDOM(html, { url: 'http://localhost/editor', runScripts: 'outside-only', pretendToBeVisual: true });
const { window } = dom;
const { document } = window;

// ---- stub fetch: pipeline prefill unavailable (404) ----
window.fetch = async (url) => ({ ok: false, status: 404, json: async () => null });

// ---- stub Blob + object URLs so we can capture "uploaded" files ----
const blobs = {};
let blobCounter = 0;
class FakeBlob {
    constructor(parts, opts) { this.parts = parts; this.type = (opts && opts.type) || ''; this.id = ++blobCounter; blobs[this.id] = this; }
    async text() { return this.parts.join(''); }
}
window.Blob = FakeBlob;
window.URL.createObjectURL = (b) => 'blob:fake-' + b.id;
window.URL.revokeObjectURL = () => {};

// ---- stub FileReader to read our FakeBlob ----
window.FileReader = class {
    readAsText(blob) {
        blob.text().then((t) => { this.result = t; if (this.onload) this.onload(); },
                        (e) => { if (this.onerror) this.onerror(e); });
    }
};

// ---- run editor script ----
window.eval(js);
document.dispatchEvent(new window.Event('DOMContentLoaded'));

// ---- fake audio element with controllable currentTime/duration ----
const audio = document.getElementById('audio-player');
let curTime = 0;
Object.defineProperty(audio, 'currentTime', {
    get: () => curTime,
    set: (v) => { curTime = v; },
    configurable: true,
});
let paused = true;
Object.defineProperty(audio, 'paused', { get: () => paused, configurable: true });
Object.defineProperty(audio, 'duration', { get: () => 200, configurable: true });
audio.play = async () => { paused = false; audio.dispatchEvent(new window.Event('play')); };
audio.pause = () => { paused = true; audio.dispatchEvent(new window.Event('pause')); };
audio.load = () => {
    // simulate metadata arrival
    setTimeout(() => audio.dispatchEvent(new window.Event('loadedmetadata')), 0);
};

// helper: fire change on a file input with given content
function loadFile(inputId, content, name, type) {
    const input = document.getElementById(inputId);
    const blob = new FakeBlob([content], { type });
    Object.defineProperty(input, 'files', { value: [blob], configurable: true, writable: true });
    input.dispatchEvent(new window.Event('change'));
    return blob;
}

const seekBar = document.getElementById('seek-bar');

function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

(async () => {
    // ===== 1. Load karaoke.json =====
    loadFile('json-input', JSON.stringify(KARAOKE), 'karaoke.json', 'application/json');
    await sleep(30);

    const rows = () => document.querySelectorAll('.line-row');
    check('строк отрисовано = 3', rows().length === 3, rows().length);
    check('название песни показано', document.getElementById('song-name').textContent.includes('Тестовая песня'));
    check('время отображается с точностью 0.01', rows()[0].querySelector('.start-time').textContent === '[00:11.44]',
          rows()[0].querySelector('.start-time').textContent);

    // ===== 2. Load audio =====
    loadFile('audio-input', 'fake-audio-bytes', 'minus.mp3', 'audio/mpeg');
    await sleep(30);
    check('длительность показана', document.getElementById('total-duration').textContent === '03:20.00',
          document.getElementById('total-duration').textContent);

    // ===== 3. Play / Pause =====
    document.getElementById('btn-play').click();
    await sleep(10);
    check('Play работает (кнопка ❚❚)', !audio.paused && document.getElementById('btn-play').textContent === '❚❚');
    audio.pause();
    await sleep(10);
    check('Pause работает (кнопка ▶)', audio.paused && document.getElementById('btn-play').textContent === '▶');

    // Enter toggles play/pause
    document.body.dispatchEvent(new window.KeyboardEvent('keydown', { code: 'Enter', bubbles: true }));
    await sleep(10);
    check('Enter = play/pause', !audio.paused);
    audio.pause();

    // ===== 4. Seek buttons & arrows =====
    // NB: jsdom's activeElement is always <body>, so the editor keeps the
    // seek bar in sync on timeupdate — dispatch it to sync the slider value.
    seekBar.value = '45';
    seekBar.dispatchEvent(new window.Event('input')); // user drags slider to 45
    check('seek bar (шаг 0.01) перематает аудио', Math.abs(curTime - 45) < 1e-9, curTime);
    document.getElementById('btn-seek-back').click();
    check('−5 сек', Math.abs(curTime - 45) < 1e-9, curTime);
    document.getElementById('btn-seek-fwd').click();
    check('+5 сек', Math.abs(curTime - 50) < 1e-9, curTime);
    document.body.dispatchEvent(new window.KeyboardEvent('keydown', { code: 'ArrowRight', bubbles: true }));
    check('→ = +0.1 сек', Math.abs(curTime - 50.1) < 1e-6, curTime);
    document.body.dispatchEvent(new window.KeyboardEvent('keydown', { code: 'ArrowLeft', bubbles: true }));
    check('← = −0.1 сек', Math.abs(curTime - 50.0) < 1e-6, curTime);

    // ===== 5. Active line highlight + preview by time =====
    curTime = 15; // inside second line (12.318..20.359)
    audio.dispatchEvent(new window.Event('timeupdate'));
    await sleep(5);
    check('текущая строка подсвечена', rows()[1].classList.contains('active'));
    check('preview показывает текущую строку', document.getElementById('preview-current').textContent === 'Вторая строка',
          document.getElementById('preview-current').textContent);
    check('preview показывает следующую', document.getElementById('preview-next').textContent === 'Третья строка');

    // ===== 6. Click END of line 0 while at t=12.0 -> sets end =====
    curTime = 12.0;
    rows()[0].querySelector('.end-time').click();
    await sleep(5);
    check('клик по end устанавливает end', rows()[0].querySelector('.end-time').textContent === '[00:12.00]',
          rows()[0].querySelector('.end-time').textContent);

    // ===== 7. Validation: try invalid end (crosses next start) =====
    curTime = 13.0; // > next.start (12.318)
    rows()[0].querySelector('.end-time').click();
    await sleep(5);
    let msg = document.getElementById('editor-message').textContent;
    check('валидация: конец пересекает начало следующей', msg.includes('Конец строки пересекает начало следующей'), msg);
    check('некорректное значение не записано', rows()[0].querySelector('.end-time').textContent === '[00:12.00]');

    // ===== 8. Validation: start >= end =====
    curTime = 12.5; // >= line0.end (12.0)
    rows()[0].querySelector('.start-time').click();
    await sleep(5);
    msg = document.getElementById('editor-message').textContent;
    check('валидация: start раньше end', msg.includes('Начало строки должно быть раньше её конца'), msg);

    // ===== 9. Undo restores previous values =====
    document.getElementById('btn-undo').click();
    await sleep(5);
    check('Undo вернул исходный end[0]=12.32', rows()[0].querySelector('.end-time').textContent === '[00:12.32]',
          rows()[0].querySelector('.end-time').textContent);

    // ===== 10. Sequential commit via Space =====
    // Fresh state: reload json to reset selection/history
    loadFile('json-input', JSON.stringify(KARAOKE), 'karaoke.json', 'application/json');
    await sleep(30);

    // Space #1: first line start = 10.00
    curTime = 10.0;
    document.body.dispatchEvent(new window.KeyboardEvent('keydown', { code: 'Space', bubbles: true }));
    await sleep(5);
    check('Space #1: start[0]=10.00', rows()[0].querySelector('.start-time').textContent === '[00:10.00]',
          rows()[0].querySelector('.start-time').textContent);

    // Space #2 at 15.0: end[0]=15, start[1]=15
    curTime = 15.0;
    document.body.dispatchEvent(new window.KeyboardEvent('keydown', { code: 'Space', bubbles: true }));
    await sleep(5);
    check('Space #2: end[0]=15.00', rows()[0].querySelector('.end-time').textContent === '[00:15.00]');
    check('Space #2: start[1]=15.00', rows()[1].querySelector('.start-time').textContent === '[00:15.00]');

    // Commit #3 at 25.0 via button: end[1]=25, start[2]=25
    curTime = 25.0;
    document.getElementById('btn-commit').click();
    await sleep(5);
    check('Кнопка фиксации: end[1]=25.00', rows()[1].querySelector('.end-time').textContent === '[00:25.00]');
    check('Кнопка фиксации: start[2]=25.00', rows()[2].querySelector('.start-time').textContent === '[00:25.00]');

    // ===== 11. Undo last commit =====
    document.getElementById('btn-undo').click();
    await sleep(5);
    check('Undo фиксации: end[1]=20.36', rows()[1].querySelector('.end-time').textContent === '[00:20.36]',
          rows()[1].querySelector('.end-time').textContent);
    check('Undo фиксации: start[2]=20.36', rows()[2].querySelector('.start-time').textContent === '[00:20.36]');
    // Undo Space #2 as well so the saved file has untouched auto timings
    document.getElementById('btn-undo').click();
    await sleep(5);
    check('Undo #2 вернул end[0]=12.32', rows()[0].querySelector('.end-time').textContent === '[00:12.32]',
          rows()[0].querySelector('.end-time').textContent);

    // ===== 12. Shortcuts must NOT fire while focus is in an input =====
    curTime = 99;
    const someInput = document.getElementById('seek-bar'); // INPUT element
    someInput.dispatchEvent(new window.KeyboardEvent('keydown', { code: 'Space', bubbles: true }));
    await sleep(5);
    check('Space в input игнорируется (start[0] не изменился)',
          rows()[0].querySelector('.start-time').textContent === '[00:10.00]',
          rows()[0].querySelector('.start-time').textContent);

    // ===== 13. Save JSON =====
    let saved = null;
    const origCreate = document.createElement.bind(document);
    document.createElement = function (tag) {
        const el = origCreate(tag);
        if (tag === 'a') {
            el.click = function () {
                const b = blobs[Number(String(el.href).replace('blob:fake-', ''))];
                if (b) saved = b;
            };
        }
        return el;
    };
    document.getElementById('btn-save-json').click();
    await sleep(20);
    document.createElement = origCreate;

    check('Сохранение создало файл', !!saved);
    const parsed = JSON.parse(await saved.text());
    check('формат: только title + lyrics', Object.keys(parsed).sort().join(',') === 'lyrics,title', Object.keys(parsed));
    check('в строках только start/end/text',
          Object.keys(parsed.lyrics[0]).sort().join(',') === 'end,start,text', Object.keys(parsed.lyrics[0]));
    check('сохранённые значения корректны', parsed.lyrics[0].start === 10 && parsed.lyrics[0].end === 12.318 && parsed.title === 'Тестовая песня',
          JSON.stringify(parsed.lyrics[0]));
    check('исходные авто-тайминги сохранены с исходной точностью', parsed.lyrics[1].end === 20.359 && parsed.lyrics[2].start === 20.359 && parsed.lyrics[2].text === 'Третья строка', JSON.stringify(parsed.lyrics));

    // ===== 14. Re-load saved JSON into editor =====
    loadFile('json-input', JSON.stringify(parsed), 'karaoke.json', 'application/json');
    await sleep(30);
    check('повторная загрузка сохранённого JSON', rows().length === 3 &&
          rows()[0].querySelector('.start-time').textContent === '[00:10.00]',
          rows()[0] && rows()[0].querySelector('.start-time').textContent);

    // ===== 15. Internal pipeline format also loads =====
    const internal = {
        format: 'karaoke', version: 1,
        metadata: { title: 'Внутренний формат' },
        lyrics: { lines: [{ start: 1.5, end: 3.25, text: 'Строка A', words: [] }] },
        pitch: {},
    };
    loadFile('json-input', JSON.stringify(internal), 'internal.json', 'application/json');
    await sleep(30);
    check('внутренний формат пайплайна загружается', rows().length === 1 &&
          document.getElementById('song-name').textContent.includes('Внутренний формат'));

    console.log(failures === 0 ? '\nALL TESTS PASSED' : '\n' + failures + ' TEST(S) FAILED');
    process.exit(failures === 0 ? 0 : 1);
})().catch((e) => { console.error('TEST CRASH:', e); process.exit(2); });
