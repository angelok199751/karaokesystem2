/**
 * Karaoke Builder — Timing Editor
 *
 * Standalone editor for manual fixing of start/end times in karaoke.json.
 * Works on top of an already generated result — no pipeline involvement.
 *
 * Supported karaoke.json shapes (input):
 *   1) { "title": "...", "lyrics": [ {start, end, text}, ... ] }        (simple)
 *   2) { "metadata": {"title": ...}, "lyrics": {"lines": [...] } }      (internal)
 *
 * Saved file always uses the simple format from the task spec:
 *   { "title": "...", "lyrics": [ {start, end, text}, ... ] }
 */

(function () {
    'use strict';

    const EPS = 0.005; // rounding tolerance for validations (~ms)

    /* ---------------- State ---------------- */

    const state = {
        title: '',
        lyrics: [],          // [{start, end, text}]
        selectedIndex: -1,   // line targeted by Space-commit ("next to fix")
        playingIndex: -1,    // line currently active by audio time
        history: [],         // stack of undoable actions
        audioLoaded: false,
    };

    /* ---------------- DOM ---------------- */

    const $ = (id) => document.getElementById(id);

    const els = {
        songName: $('song-name'),
        btnLoadJson: $('btn-load-json'),
        jsonInput: $('json-input'),
        btnLoadAudio: $('btn-load-audio'),
        audioInput: $('audio-input'),
        btnSave: $('btn-save-json'),
        audio: $('audio-player'),
        btnPlay: $('btn-play'),
        btnSeekBack: $('btn-seek-back'),
        btnSeekFwd: $('btn-seek-fwd'),
        currentTime: $('current-time'),
        seekBar: $('seek-bar'),
        totalDuration: $('total-duration'),
        message: $('editor-message'),
        btnCommit: $('btn-commit'),
        btnUndo: $('btn-undo'),
        previewCurrent: $('preview-current'),
        previewNext: $('preview-next'),
        linesList: $('lines-list'),
        lineCount: $('line-count'),
    };

    /* ---------------- Helpers ---------------- */

    function fmtTime(t) {
        if (!isFinite(t) || t < 0) t = 0;
        const m = Math.floor(t / 60);
        const s = Math.floor(t % 60);
        const cs = Math.round((t - Math.floor(t)) * 100);
        const csAdj = cs === 100 ? 0 : cs;
        const sAdj = cs === 100 ? s + 1 : s;
        return String(m).padStart(2, '0') + ':' +
               String(sAdj % 60).padStart(2, '0') + '.' +
               String(csAdj).padStart(2, '0');
    }

    function round2(v) {
        return Math.round(v * 100) / 100;
    }

    let msgTimer = null;
    function showMessage(text, kind) {
        els.message.textContent = text || '';
        els.message.className = 'editor-message' + (kind ? ' ' + kind : '');
        if (msgTimer) clearTimeout(msgTimer);
        if (text && kind !== 'error') {
            msgTimer = setTimeout(() => {
                els.message.textContent = '';
                els.message.className = 'editor-message';
            }, 4000);
        }
    }

    function audioTime() {
        return isFinite(els.audio.currentTime) ? els.audio.currentTime : 0;
    }

    function canEdit() {
        if (!state.lyrics.length) {
            showMessage('Сначала загрузите karaoke.json', 'error');
            return false;
        }
        return true;
    }

    function hasAudio() {
        if (!state.audioLoaded) {
            showMessage('Сначала загрузите аудиофайл', 'error');
            return false;
        }
        return true;
    }

    /* ---------------- Validation ---------------- */

    // Returns error string or null.
    function validateSet(index, field, value) {
        const line = state.lyrics[index];
        if (!line) return 'Строка не найдена';

        if (field === 'start') {
            if (value >= line.end - EPS) {
                return 'Начало строки должно быть раньше её конца';
            }
            const prev = state.lyrics[index - 1];
            if (prev && value <= prev.start + EPS) {
                return 'Начало строки должно быть позже начала предыдущей';
            }
            if (prev && value < prev.end - EPS) {
                return 'Конец предыдущей строки пересекает начало этой';
            }
        } else if (field === 'end') {
            if (value <= line.start + EPS) {
                return 'Начало строки должно быть раньше её конца';
            }
            const next = state.lyrics[index + 1];
            if (next && value > next.start + EPS) {
                return 'Конец строки пересекает начало следующей';
            }
        }
        return null;
    }

    /* ---------------- Actions & Undo ---------------- */

    function pushAction(action) {
        state.history.push(action);
        if (state.history.length > 500) state.history.shift();
    }

    function undoLast() {
        const action = state.history.pop();
        if (!action) {
            showMessage('Нечего отменять');
            return;
        }
        if (action.type === 'set') {
            const line = state.lyrics[action.index];
            if (line) line[action.field] = action.prevValue;
            state.selectedIndex = action.index;
        } else if (action.type === 'commit') {
            const prevLine = state.lyrics[action.index - 1];
            const curLine = state.lyrics[action.index];
            if (prevLine) prevLine.end = action.prevEnd;
            if (curLine) curLine.start = action.prevStart;
            state.selectedIndex = action.index;
        }
        renderAll(false);
        showMessage('Действие отменено');
    }

    /* ---------------- Core editing ops ---------------- */

    function setTime(index, field, value, opts) {
        opts = opts || {};
        const rounded = round2(value);
        const err = validateSet(index, field, rounded);
        if (err) {
            showMessage(err, 'error');
            return false;
        }
        pushAction({
            type: 'set',
            index: index,
            field: field,
            prevValue: state.lyrics[index][field],
        });
        state.lyrics[index][field] = rounded;
        if (opts.select !== false) state.selectedIndex = index;
        renderAll(false);
        return true;
    }

    function clickTime(index, field) {
        if (!canEdit()) return;
        const line = state.lyrics[index];
        const t = audioTime();
        if (Math.abs(line[field] - t) <= EPS) {
            // Same point clicked again — just seek there (manual re-fix flow).
            seekTo(t);
            state.selectedIndex = index;
            renderAll(true);
            return;
        }
        if (!hasAudio()) return;
        if (setTime(index, field, t)) {
            seekTo(t);
        }
    }

    // Sequential commit ("Зафиксировать строку" / Space)
    function commitLine() {
        if (!canEdit()) return;
        if (!hasAudio()) return;
        const t = round2(audioTime());
        let idx = state.selectedIndex;

        if (idx < 0 || idx >= state.lyrics.length) {
            // nothing selected yet -> start with first line
            idx = 0;
        }

        if (idx === 0) {
            // First line: set its start, move to next
            if (t >= state.lyrics[0].end - EPS) {
                showMessage('Начало строки должно быть раньше её конца', 'error');
                return;
            }
            pushAction({ type: 'commit', index: 0, prevStart: state.lyrics[0].start, prevEnd: null });
            state.lyrics[0].start = t;
            state.selectedIndex = 1;
        } else {
            const prev = state.lyrics[idx - 1];
            const cur = state.lyrics[idx];
            if (t <= prev.start + EPS) {
                showMessage('Начало строки должно быть раньше её конца', 'error');
                return;
            }
            if (t >= cur.end - EPS) {
                showMessage('Начало строки должно быть раньше её конца', 'error');
                return;
            }
            pushAction({
                type: 'commit',
                index: idx,
                prevStart: cur.start,
                prevEnd: prev.end,
            });
            prev.end = t;
            cur.start = t;
            state.selectedIndex = idx + 1;
        }

        if (state.selectedIndex >= state.lyrics.length) {
            state.selectedIndex = state.lyrics.length - 1;
            showMessage('Все строки зафиксированы', 'ok');
        }
        renderAll(true);
    }

    /* ---------------- Audio ---------------- */

    function togglePlay() {
        if (!hasAudio()) return;
        if (els.audio.paused) {
            els.audio.play().catch((e) => showMessage('Не удалось воспроизвести аудио: ' + e.message, 'error'));
        } else {
            els.audio.pause();
        }
    }

    function seekTo(t) {
        if (!state.audioLoaded) return;
        const d = isFinite(els.audio.duration) ? els.audio.duration : t;
        els.audio.currentTime = Math.max(0, Math.min(t, d));
        updatePlaybackUi();
    }

    function nudge(delta) {
        seekTo(audioTime() + delta);
    }

    function updatePlaybackUi() {
        const t = audioTime();
        els.currentTime.textContent = fmtTime(t);
        if (document.activeElement !== els.seekBar) {
            els.seekBar.value = t;
        }
        els.btnPlay.textContent = els.audio.paused ? '▶' : '❚❚';

        // Active line by time
        let idx = -1;
        for (let i = 0; i < state.lyrics.length; i++) {
            const l = state.lyrics[i];
            if (t >= l.start && t < l.end) { idx = i; break; }
        }
        if (idx === -1 && state.lyrics.length && t >= state.lyrics[state.lyrics.length - 1].end) {
            idx = state.lyrics.length - 1;
        }
        if (idx !== state.playingIndex) {
            state.playingIndex = idx;
            highlightActiveLine();
            updatePreview();
        }
    }

    function scrollLineIntoView(index) {
        const row = els.linesList.querySelector('[data-index="' + index + '"]');
        if (row && row.scrollIntoView) {
            row.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        }
    }

    /* ---------------- Rendering ---------------- */

    function renderSongName() {
        els.songName.textContent = 'Песня: ' + (state.title || '—');
    }

    function buildLinesDom() {
        els.linesList.innerHTML = '';
        if (!state.lyrics.length) {
            const p = document.createElement('p');
            p.className = 'empty-hint';
            p.textContent = 'Загрузите karaoke.json, чтобы начать редактирование.';
            els.linesList.appendChild(p);
            els.lineCount.textContent = '0';
            return;
        }
        els.lineCount.textContent = String(state.lyrics.length);

        const frag = document.createDocumentFragment();
        state.lyrics.forEach((line, i) => {
            const row = document.createElement('div');
            row.className = 'line-row';
            row.dataset.index = String(i);

            // START cell
            const startCell = document.createElement('div');
            startCell.className = 'line-cell';
            const idxEl = document.createElement('span');
            idxEl.className = 'line-index';
            idxEl.textContent = String(i + 1);
            const startBtn = document.createElement('span');
            startBtn.className = 'line-time start-time';
            startBtn.textContent = '[' + fmtTime(line.start) + ']';
            startBtn.title = 'Клик = установить start в текущую позицию аудио';
            startBtn.addEventListener('click', () => clickTime(i, 'start'));
            startCell.appendChild(idxEl);
            startCell.appendChild(startBtn);

            // TEXT cell
            const textEl = document.createElement('div');
            textEl.className = 'line-text';
            textEl.textContent = line.text;
            textEl.title = 'Клик = сделать строку текущей для фиксации';
            textEl.addEventListener('click', () => {
                state.selectedIndex = i;
                renderAll(true);
            });

            // END cell
            const endCell = document.createElement('div');
            endCell.className = 'line-cell';
            endCell.style.justifyContent = 'flex-end';
            const endBtn = document.createElement('span');
            endBtn.className = 'line-time end-time';
            endBtn.textContent = '[' + fmtTime(line.end) + ']';
            endBtn.title = 'Клик = установить end в текущую позицию аудио';
            endBtn.addEventListener('click', () => clickTime(i, 'end'));
            endCell.appendChild(endBtn);

            row.appendChild(startCell);
            row.appendChild(textEl);
            row.appendChild(endCell);
            frag.appendChild(row);
        });
        els.linesList.appendChild(frag);
    }

    function refreshTimesDom() {
        state.lyrics.forEach((line, i) => {
            const row = els.linesList.querySelector('[data-index="' + i + '"]');
            if (!row) return;
            row.querySelector('.start-time').textContent = '[' + fmtTime(line.start) + ']';
            row.querySelector('.end-time').textContent = '[' + fmtTime(line.end) + ']';
        });
    }

    function highlightActiveLine() {
        const rows = els.linesList.querySelectorAll('.line-row');
        rows.forEach((row) => {
            const i = Number(row.dataset.index);
            row.classList.toggle('active', i === state.playingIndex);
            row.classList.toggle('selected', i === state.selectedIndex);
        });
    }

    function updatePreview() {
        const idx = state.playingIndex >= 0 ? state.playingIndex : state.selectedIndex;
        if (idx < 0 || idx >= state.lyrics.length) {
            els.previewCurrent.textContent = '<нет данных>';
            els.previewNext.textContent = '';
            return;
        }
        els.previewCurrent.textContent = state.lyrics[idx].text;
        const next = state.lyrics[idx + 1];
        els.previewNext.textContent = next ? next.text : '';
    }

    function renderAll(scrollToActive) {
        refreshTimesDom();
        highlightActiveLine();
        updatePreview();
        if (scrollToActive) {
            const target = state.playingIndex >= 0 ? state.playingIndex : state.selectedIndex;
            if (target >= 0) scrollLineIntoView(target);
        }
    }

    /* ---------------- Load / Save ---------------- */

    function normalizeLyrics(data) {
        let rawLines = [];
        if (Array.isArray(data.lyrics)) {
            rawLines = data.lyrics;
        } else if (data.lyrics && Array.isArray(data.lyrics.lines)) {
            rawLines = data.lyrics.lines;
        } else if (Array.isArray(data.lines)) {
            rawLines = data.lines;
        }
        const lines = [];
        rawLines.forEach((l) => {
            if (!l) return;
            const start = Number(l.start);
            const end = Number(l.end);
            if (!isFinite(start) || !isFinite(end)) return;
            lines.push({ start: start, end: end, text: String(l.text != null ? l.text : '') });
        });
        return lines;
    }

    function loadJsonFile(file) {
        const reader = new FileReader();
        reader.onload = () => {
            try {
                const data = JSON.parse(String(reader.result));
                const lines = normalizeLyrics(data);
                if (!lines.length) {
                    showMessage('В файле не найдено строк (ожидается поле "lyrics")', 'error');
                    return;
                }
                state.title = data.title ||
                    (data.metadata && data.metadata.title) ||
                    file.name.replace(/\.json$/i, '');
                state.lyrics = lines;
                state.selectedIndex = 0;
                state.playingIndex = -1;
                state.history = [];
                renderSongName();
                buildLinesDom();
                updatePreview();
                highlightActiveLine();
                showMessage('Загружено строк: ' + lines.length, 'ok');
            } catch (e) {
                showMessage('Не удалось прочитать JSON: ' + e.message, 'error');
            }
        };
        reader.onerror = () => showMessage('Ошибка чтения файла', 'error');
        reader.readAsText(file, 'utf-8');
    }

    function loadAudioFile(file) {
        if (els.audio.src && els.audio.src.startsWith('blob:')) {
            URL.revokeObjectURL(els.audio.src);
        }
        const url = URL.createObjectURL(file);
        els.audio.src = url;
        els.audio.load();
    }

    function saveJson() {
        if (!state.lyrics.length) {
            showMessage('Нечего сохранять — загрузите karaoke.json', 'error');
            return;
        }
        // Final format only: title + lyrics[{start,end,text}]
        const out = {
            title: state.title || 'Untitled',
            lyrics: state.lyrics.map((l) => ({
                start: l.start,
                end: l.end,
                text: l.text,
            })),
        };
        const blob = new Blob([JSON.stringify(out, null, 2)], { type: 'application/json' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'karaoke.json';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(() => URL.revokeObjectURL(a.href), 2000);
        showMessage('karaoke.json сохранён', 'ok');
    }

    /* ---------------- Keyboard shortcuts ---------------- */

    function isTypingTarget(el) {
        if (!el) return false;
        const tag = el.tagName;
        return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el.isContentEditable;
    }

    document.addEventListener('keydown', (e) => {
        if (isTypingTarget(e.target)) return;

        switch (e.code) {
            case 'Space':
                e.preventDefault();
                commitLine();
                break;
            case 'Enter':
                e.preventDefault();
                togglePlay();
                break;
            case 'ArrowLeft':
                e.preventDefault();
                nudge(-0.1);
                break;
            case 'ArrowRight':
                e.preventDefault();
                nudge(0.1);
                break;
            case 'KeyZ':
                if ((e.ctrlKey || e.metaKey) && !e.shiftKey) {
                    e.preventDefault();
                    undoLast();
                }
                break;
        }
    });

    /* ---------------- Wiring ---------------- */

    function init() {
        els.btnLoadJson.addEventListener('click', () => els.jsonInput.click());
        els.jsonInput.addEventListener('change', () => {
            const f = els.jsonInput.files[0];
            if (f) loadJsonFile(f);
            els.jsonInput.value = '';
        });

        els.btnLoadAudio.addEventListener('click', () => els.audioInput.click());
        els.audioInput.addEventListener('change', () => {
            const f = els.audioInput.files[0];
            if (f) loadAudioFile(f);
            els.audioInput.value = '';
        });

        els.btnSave.addEventListener('click', saveJson);

        els.btnPlay.addEventListener('click', togglePlay);
        els.btnSeekBack.addEventListener('click', () => nudge(-5));
        els.btnSeekFwd.addEventListener('click', () => nudge(5));

        els.seekBar.addEventListener('input', () => {
            seekTo(Number(els.seekBar.value));
        });

        els.btnCommit.addEventListener('click', commitLine);
        els.btnUndo.addEventListener('click', undoLast);

        // Audio events
        els.audio.addEventListener('loadedmetadata', () => {
            state.audioLoaded = true;
            els.seekBar.max = String(isFinite(els.audio.duration) ? els.audio.duration : 0);
            els.totalDuration.textContent = fmtTime(els.audio.duration);
            showMessage('Аудио загружено', 'ok');
            updatePlaybackUi();
        });
        els.audio.addEventListener('timeupdate', updatePlaybackUi);
        els.audio.addEventListener('play', updatePlaybackUi);
        els.audio.addEventListener('pause', updatePlaybackUi);
        els.audio.addEventListener('ended', updatePlaybackUi);

        // Prefill from the last pipeline job if available (convenience for
        // the "generate -> fix" flow; manual loading always stays possible).
        tryPrefillFromPipeline();
    }

    function tryPrefillFromPipeline() {
        // If the user already loaded files manually, don't override them.
        let cancelled = false;
        const audioEl = els.audio;
        fetch('/api/output/karaoke.json')
            .then((r) => (r.ok ? r.json() : null))
            .then((data) => {
                if (cancelled || !data) return;

                // Don't override data the user loaded manually in the meantime.
                if (state.lyrics.length) return;
                const lines = normalizeLyrics(data);
                if (!lines.length) return;
                state.title = data.title || (data.metadata && data.metadata.title) || '';
                state.lyrics = lines;
                state.selectedIndex = 0;
                renderSongName();
                buildLinesDom();
                updatePreview();
                highlightActiveLine();
                showMessage('Загружен результат последнего пайплайна. При необходимости загрузите свои файлы.', 'ok');
                // Check minus.mp3 availability without triggering a console
                // error: attach src only after a successful HEAD request and
                // use a dedicated audio element for the probe.
                return fetch('/api/output/minus.mp3', { method: 'HEAD' })
                    .then((r) => {
                        if (!cancelled && r.ok && els.audio === audioEl) {
                            audioEl.src = '/api/output/minus.mp3';
                            audioEl.load();
                        }
                    })
                    .catch(() => {});
            })
            .catch(() => { /* no backend — fine, manual mode */ });
    }

    document.addEventListener('DOMContentLoaded', init);
})();
