# Karaoke Builder — Technical Prototype

Новое поколение караоке-билдера с полностью переработанным ML pipeline.

## 🎯 Цель прототипа

Создать рабочий end-to-end pipeline:

```
MP3 → Demucs → vocals.wav + instrumental.wav
vocals.wav + lyrics.txt → WhisperX → word-level timestamps
vocals.wav → torchcrepe → continuous pitch contour
Результаты → единый внутренний karaoke JSON
instrumental.wav → minus.mp3
```

**Главная задача** — НЕ красивый интерфейс, а работающий диагностируемый pipeline.

---

## 🏗️ Архитектура

```
┌─────────────────────────────────────────┐
│         Browser-like UI                 │
│  (HTML/CSS/JS - frontend/)              │
└──────────────────┬──────────────────────┘
                   │ HTTP/WebSocket
┌──────────────────▼──────────────────────┐
│      Application Layer                  │
│  (backend/app.py - Flask/FastAPI)       │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│    Local Processing Engine              │
│  backend/processors/                    │
│  ├── demucs_processor.py                │
│  ├── whisperx_processor.py              │
│  └── pitch_processor.py                 │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│  External Tools                         │
│  • Demucs (source separation)           │
│  • WhisperX (forced alignment)          │
│  • torchcrepe (pitch contour)           │
│  • FFmpeg (audio conversion)            │
└─────────────────────────────────────────┘
```

### Структура проекта

```
karaoke-builder/
├── README.md                 # Этот файл
├── requirements.txt          # Python зависимости
├── setup_models.py          # Скрипт установки моделей
│
├── backend/
│   ├── app.py               # Основной сервер (Flask/FastAPI)
│   ├── config.py            # Конфигурация
│   ├── stage_runner.py      # Универсальный runner для stages
│   ├── debug_logger.py      # Система логирования
│   │
│   ├── processors/
│   │   ├── __init__.py
│   │   ├── base_processor.py    # Базовый класс процессора
│   │   ├── demucs_processor.py  # Stage 1: Vocal Separation
│   │   ├── whisperx_processor.py # Stage 2: Alignment
│   │   ├── pitch_processor.py    # Stage 3: Pitch Contour
│   │   └── packaging_processor.py # Stage 4: Build JSON + MP3
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── karaoke_format.py     # Внутренний JSON формат
│   │   └── validation.py         # Input validation
│   │
│   └── utils/
│       ├── __init__.py
│       ├── audio_utils.py        # Аудио утилиты
│       └── system_info.py        # Информация о системе
│
├── frontend/
│   ├── index.html           # Главный экран
│   ├── preview.html         # Preview плеер
│   │
│   ├── css/
│   │   ├── main.css         # Основные стили
│   │   ├── preview.css      # Стили preview
│   │   └── debug.css        # Стили debug панели
│   │
│   ├── js/
│   │   ├── app.js           # Основная логика UI
│   │   ├── preview.js       # Логика плеера
│   │   ├── api.js           # API клиент
│   │   └── debug.js         # Debug панель
│   │
│   └── components/
│       ├── project-form.js  # Форма нового проекта
│       ├── pipeline-status.js # Статус pipeline
│       └── timeline.js      # Timeline компонент
│
├── temp/                    # Временные файлы (auto-generated)
│   └── job-YYYYMMDD-HHMMSS/
│       ├── input/
│       ├── demucs/
│       ├── whisperx/
│       ├── pitch/
│       ├── output/
│       └── logs/
│
└── logs/                    # Логи приложения (auto-generated)
```

---

## 🚀 Быстрый старт

### Требования

- **Python**: 3.9+
- **FFmpeg**: должен быть установлен в системе
- **GPU**: опционально (CUDA для ускорения)
- **OS**: Windows 10/11, macOS 12+, Linux

### Шаг 1: Установка зависимостей

```bash
cd karaoke-builder

# Создать виртуальное окружение (рекомендуется)
python -m venv venv

# Активировать окружение
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Установить Python зависимости
pip install -r requirements.txt
```

### Шаг 2: Установка ML моделей

```bash
# Запустить скрипт установки моделей
python setup_models.py
```

Скрипт проверит и загрузит:
- ✓ Demucs модель
- ✓ Whisper модель
- ✓ Alignment модель
- ✓ torchcrepe модель

**Важно**: Модели не хранятся в Git repository. Они загружаются отдельно при первом запуске.

### Шаг 3: Проверка системы

```bash
# Проверить доступность инструментов
python backend/utils/system_info.py
```

Ожидаемый вывод:
```
SYSTEM
────────────────────────────
OS: Windows 11 / macOS 12 / Linux
Python: 3.9.x
PyTorch: 2.x.x
CUDA: True/False
GPU: NVIDIA GeForce RTX ... (если есть)

TOOLS
────────────────────────────
FFmpeg: ✓
Demucs: ✓
WhisperX: ✓
torchcrepe: ✓

MODELS
────────────────────────────
Demucs: ✓
Whisper: ✓
Alignment: ✓
Pitch: ✓
```

### Шаг 4: Запуск приложения

```bash
# Запустить backend сервер
python backend/app.py
```

Сервер запустится на `http://localhost:5000`

### Шаг 5: Открыть UI

Открыть в браузере:
- `http://localhost:5000` — главный экран
- Или напрямую открыть `frontend/index.html`

---

## 📋 Минимальный пользовательский сценарий

1. **Запуск приложения**
   - Пользователь видит форму "Новый проект"

2. **Загрузка файлов**
   - Drag&drop или выбор MP3 файла
   - Drag&drop или выбор TXT файла с текстом
   - Ввод названия песни
   - Нажатие кнопки "Создать"

3. **Предварительный просмотр**
   - Отображается информация о файлах:
     - Имя MP3, длительность, размер
     - Имя TXT, количество строк текста

4. **Запуск pipeline**
   - Stage 0: Input Validation
   - Stage 1: Demucs (Vocal Separation)
   - Stage 2: WhisperX (Word-level Timestamps)
   - Stage 3: torchcrepe (Pitch Contour)
   - Stage 4: Packaging (Build JSON + MP3)

5. **Preview**
   - Воспроизведение instrumental (minus.mp3)
   - Синхронизированное отображение текста
   - Подсветка активной строки
   - Опционально: подсветка текущего слова
   - Timeline для диагностики

6. **Debug Console**
   - Встроенная панель логов
   - Отображение stderr внешних процессов
   - Кнопки "Copy Debug Info" и "Save Debug Log"

---

## 🔧 Pipeline Stages

### Stage 0 — Input Validation

Проверка:
- Существует ли MP3
- Читается ли аудио
- Поддерживается ли формат
- Есть ли TXT файл
- Не пустой ли TXT
- Можно ли получить duration
- Доступен ли processing engine
- Достаточно ли места во временной директории

### Stage 1 — Demucs

**Вход**: `song.mp3`  
**Выход**: `vocals.wav`, `instrumental.wav`

Использует Demucs для source separation.

Проверка результата:
- ✓ vocals.wav существует
- ✓ instrumental.wav существует
- Файлы не пустые
- Длительность соответствует исходному треку

### Stage 2 — WhisperX

**Вход**: `vocals.wav`, `lyrics.txt`  
**Выход**: `words.json` (word-level timestamps)

Использует forced alignment для точной синхронизации.

Результат преобразуется в нормализованный формат:

```json
{
  "lines": [
    {
      "start": 12.420,
      "end": 15.870,
      "text": "Я тебя люблю",
      "words": [
        {"text": "Я", "start": 12.420, "end": 12.710},
        {"text": "тебя", "start": 12.720, "end": 13.510},
        {"text": "люблю", "start": 13.520, "end": 15.870}
      ]
    }
  ]
}
```

### Stage 3 — Pitch (torchcrepe)

**Вход**: `vocals.wav`  
**Выход**: `pitch.json` (continuous pitch contour)

Непрерывная кривая высоты голоса:

```json
{
  "points": [
    {"time": 12.420, "frequency": 438.7, "confidence": 0.96}
  ]
}
```

### Stage 4 — Packaging

**Вход**: Результаты всех stages  
**Выход**: `karaoke.json`, `minus.mp3`

Создание внутреннего karaoke JSON формата:

```json
{
  "format": "karaoke",
  "version": 1,
  "metadata": {
    "title": "Название песни",
    "duration": 222.41
  },
  "lyrics": {...},
  "pitch": {...}
}
```

Конвертация instrumental.wav → minus.mp3 через FFmpeg.

---

## 🐛 Отладка и диагностика

### Debug Console

Встроенная панель отладки отображает:
- Логи каждого stage
- stdout/stderr внешних процессов
- Exit codes
- Время выполнения
- Созданные файлы

### Structured Errors

Ошибки двухуровневые:

**Уровень 1 (обычному пользователю)**:
```
WhisperX: ошибка
CUDA out of memory
```

**Уровень 2 (разработчику)**:
```
Full error
Command: whisperx ...
Exit code: 1
stdout: ...
stderr: CUDA out of memory...
Stack trace: ...
Environment: ...
```

### Temporary Files

Каждый pipeline запускается в отдельной временной директории:

```
temp/job-20260920-143201/
├── input/song.mp3
├── input/lyrics.txt
├── demucs/vocals.wav
├── demucs/instrumental.wav
├── whisperx/words.json
├── pitch/pitch.json
├── output/karaoke.json
├── output/minus.mp3
└── logs/pipeline.log
```

**Важно**: При ошибке временные файлы НЕ удаляются автоматически для диагностики.

### Diagnostic Commands

```bash
# Скопировать диагностическую информацию
[Кнопка в UI]

# Сохранить лог
[Кнопка в UI] → karaoke-debug-2026-09-20.txt

# Открыть временную директорию
[Кнопка в UI]
```

---

## 🎮 Режимы разработки

### Run Full Pipeline

Основной режим:
```
Validate → Demucs → WhisperX → torchcrepe → Build JSON → Preview
```

### Run Individual Stages

Для разработки и тестирования:
- `[▶ Run Demucs]`
- `[▶ Run WhisperX]`
- `[▶ Run Pitch]`
- `[▶ Run Full Pipeline]`

### Retry Failed Stage

Если pipeline упал на этапе:
```
✓ Demucs
✗ WhisperX
○ torchcrepe
○ Packaging
```

Доступна кнопка `[Повторить WhisperX]` без повторного запуска Demucs.

---

## 📊 System Requirements

### Минимальные требования

- **CPU**: 4 ядра
- **RAM**: 8 GB
- **Disk**: 10 GB свободного места
- **Python**: 3.9+

### Рекомендуемые требования

- **CPU**: 8 ядер
- **RAM**: 16 GB
- **GPU**: NVIDIA с CUDA support
- **VRAM**: 6 GB+
- **Disk**: 20 GB SSD

### Поддержка GPU

Приложение автоматически определяет доступность CUDA:

```python
import torch
cuda_available = torch.cuda.is_available()
gpu_name = torch.cuda.get_device_name(0) if cuda_available else "N/A"
```

Работает и на CPU, но значительно медленнее.

---

## 📝 Внутренний формат данных

### Karaoke JSON (version 1)

```json
{
  "format": "karaoke",
  "version": 1,
  
  "metadata": {
    "title": "Название песни",
    "artist": "Исполнитель",
    "duration": 222.41,
    "created_at": "2026-09-20T14:32:01Z"
  },
  
  "lyrics": {
    "lines": [
      {
        "start": 12.420,
        "end": 15.870,
        "text": "Я тебя люблю",
        "words": [
          {
            "text": "Я",
            "start": 12.420,
            "end": 12.710
          }
        ]
      }
    ]
  },
  
  "pitch": {
    "points": [
      {
        "time": 12.420,
        "frequency": 438.7,
        "confidence": 0.96
      }
    ]
  }
}
```

**Важно**: 
- Формат версионируемый (`format`, `version`)
- Независим от конкретных ML инструментов
- UI работает только с этим форматом, не с сырыми данными WhisperX/torchcrepe

---

## 🎯 Milestones

### Milestone 1 — Engine Smoke Test
- [x] Структура проекта
- [ ] Demucs integration
- [ ] Debug logging

### Milestone 2 — Alignment
- [ ] WhisperX integration
- [ ] Normalized lyrics JSON
- [ ] Display JSON in UI

### Milestone 3 — Pitch
- [ ] torchcrepe integration
- [ ] Continuous pitch contour
- [ ] Pitch statistics

### Milestone 4 — Preview
- [ ] Audio player
- [ ] Lyrics synchronization
- [ ] Active line highlighting
- [ ] Seek functionality

### Milestone 5 — Full Pipeline
- [ ] End-to-end integration
- [ ] Error handling
- [ ] Stage retry
- [ ] Temp file management

---

## ⚠️ Что НЕ включено в прототип

- MIDI генерация
- Распознавание нот
- Распознавание аккордов
- Полноценный редактор таймингов
- Коррекция pitch
- Scoring пользователя
- Запись с микрофона
- Дуэты / multiplayer
- Аккаунты / авторизация
- Backend / база данных
- Облачное хранение
- Магазин песен

**Это технический прототип pipeline**, а не полноценное приложение.

---

## 🔍 Диагностика проблем

### Частые ошибки

#### 1. CUDA out of memory

```
Stage 2 — WhisperX FAILED

Причина:
CUDA out of memory

Process exit code: 1

stderr:
RuntimeError: CUDA out of memory...

[Повторить stage] [Сохранить лог]
```

**Решение**: 
- Закрыть другие приложения, использующие GPU
- Использовать CPU mode (медленнее)
- Уменьшить batch size (если поддерживается)

#### 2. FFmpeg not found

```
ERROR: FFmpeg не найден в PATH

[Инструкция по установке]
```

**Решение**:
- Windows: скачать с https://ffmpeg.org/download.html
- macOS: `brew install ffmpeg`
- Linux: `apt install ffmpeg` или `yum install ffmpeg`

#### 3. Модель не найдена

```
Модель WhisperX не установлена.

[Загрузить модель]
```

**Решение**: Запустить `python setup_models.py`

---

## 📞 Support

Для сообщений об ошибках используйте встроенную функцию "Скопировать диагностику" и прикрепляйте:

1. Debug log (`karaoke-debug-*.txt`)
2. Версию приложения
3. Информацию о системе (OS, Python, GPU)
4. Пример файла (если возможно)

---

## 📄 License

Technical Prototype — Internal Use Only

---

## 🙏 Acknowledgments

- **Demucs**: https://github.com/facebookresearch/demucs
- **WhisperX**: https://github.com/m-bain/whisperX
- **torchcrepe**: https://github.com/marl/crepe
- **FFmpeg**: https://ffmpeg.org/
