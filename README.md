# Симулятор роя пчёл

Интерактивный многоагентный симулятор в браузере. Несколько ульев с пчёлами работают
в реальном времени — каждый по своему алгоритму роевого интеллекта.

---

## Быстрый старт

```
launcher.bat          # Windows — устанавливает зависимости, запускает сервер, открывает браузер
```

Или вручную:

```bash
cd backend
py -3.10 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Затем откройте **http://localhost:8000**

---

## Возможности

| Возможность | Описание |
|-------------|----------|
| Несколько ульев | Добавляйте/удаляйте ульи кнопкой «+ Добавить» |
| Выбор алгоритма | Каждый улей имеет свой алгоритм — выпадающий список |
| 5 алгоритмов | Жадный, Ближайший, Равномерный, Вероятностный, Избирательный |
| Расширяемость | Добавьте собственный алгоритм одним файлом Python |
| Слайдеры в реальном времени | Скорость, регенерация, пчёлы на улей, цветы, частота тиков |
| Список агентов | Левая панель — группировка пчёл по ульям, состояния цветов |
| Статистика | Тики, нектар, мёд, активные пчёлы |

---

## Архитектура

```
Swarm_of_bees/
├── launcher.bat                      # Запускатель для Windows
├── requirements.txt                  # fastapi, uvicorn[standard], websockets
├── README.md
│
├── backend/
│   ├── main.py                       # FastAPI: WebSocket /ws, статика /static
│   └── simulation/
│       ├── agents.py                 # Агенты: Bee, Flower, Hive, Vec2, HIVE_COLORS
│       ├── controller.py             # SwarmController — диспетчер алгоритмов
│       ├── engine.py                 # SimulationEngine — asyncio-цикл, мульти-улей
│       └── algorithms/
│           ├── __init__.py           # Импорт всех алгоритмов → регистрация
│           ├── base.py               # BaseSwarmAlgorithm (абстрактный класс)
│           ├── registry.py           # Реестр: register(), get_algorithm(), list_algorithms()
│           ├── greedy.py             # Жадный
│           ├── nearest.py            # Ближайший
│           ├── round_robin.py        # Равномерный
│           ├── probabilistic.py      # Вероятностный
│           └── custom_example.py     # Шаблон + алгоритм «Избирательный»
│
└── frontend/
    ├── index.html                    # 3-панельный layout
    ├── css/style.css                 # Тёмная тема #0F1923
    └── js/
        ├── canvas.js                 # CanvasRenderer — 60 FPS, мульти-улей, цвета
        ├── websocket.js              # SwarmWS — авто-переподключение
        └── app.js                    # Логика UI, управление ульями
```

### Бэкенд

**`SimulationEngine`** — центральный класс:
- Хранит `state.hives: Dict[str, Hive]`, `state.bees: Dict[str, Bee]`, `state.flowers`
- Методы: `add_hive()`, `remove_hive()`, `set_hive_algorithm()`, `update_params()`
- Асинхронный тик-цикл: `_update_flowers()` → `_update_bees()` → `controller.tick()`
- Каждый тик отправляет снимок состояния всем WebSocket-клиентам

**`SwarmController`** — диспетчер:
- Группирует пчёл по ульям
- Вызывает `algo.tick(hive, bees, flowers)` для каждого улья
- Кеширует экземпляры алгоритмов (для сохранения состояния между тиками)
- При смене алгоритма или удалении улья — создаёт новый экземпляр

**`BaseSwarmAlgorithm`** — контракт алгоритма:
- `tick()` — вызывается каждый тик; по умолчанию: отправляет полных пчёл в улей + `assign_idle_bees()`
- `assign_idle_bees(bees, flowers)` — **единственный метод для переопределения**
- Управление состоянием цветков (`open`/`closed`) — глобальное, в `engine._update_flowers()`

### Фронтенд

- **WebSocket** — получает снимок каждый тик; отправляет команды (start/stop/reset/add_hive/…)
- **CanvasRenderer** — 60 FPS через `requestAnimationFrame`; цвет пчёл и улья берётся из `bee.color`/`hive.color`
- **app.js** — управление ульями (добавить/удалить/сменить алгоритм), список агентов по ульям

### WebSocket API

| action | параметры | событие в ответе |
|--------|-----------|-----------------|
| `start` | — | `started` |
| `stop` | — | `stopped` + snapshot |
| `reset` | `params?` | `reset` + snapshot |
| `update_params` | `params` | `params_updated` |
| `add_hive` | `algorithm_name` | `hive_added` + snapshot |
| `remove_hive` | `hive_id` | `hive_removed` + snapshot |
| `set_hive_algorithm` | `hive_id, algorithm_name` | `algorithm_changed` + snapshot |
| `get_algorithms` | — | `algorithms` + список |

Снимок (`snapshot`) содержит: `tick`, `running`, `bees[]`, `flowers[]`, `hives[]`, `stats`, `params`, `algorithms[]`.

---

## Добавление собственного алгоритма

1. Создайте файл `backend/simulation/algorithms/my_algo.py`:

```python
from .base import BaseSwarmAlgorithm
from .registry import register
from ..agents import Bee, BeeState, Flower, FlowerState

@register
class MyAlgorithm(BaseSwarmAlgorithm):
    name = "my_algo"
    description = "Мой алгоритм: краткое описание"

    def assign_idle_bees(self, bees, flowers):
        open_flowers = [f for f in flowers.values() if f.state == FlowerState.OPEN]
        if not open_flowers:
            return
        for bee in bees:
            if bee.state != BeeState.IDLE:
                continue
            # --- ваша логика выбора цветка ---
            bee.target_flower_id = open_flowers[0].id
            bee.state = BeeState.TO_FLOWER
```

2. Добавьте импорт в `backend/simulation/algorithms/__init__.py`:

```python
from .my_algo import MyAlgorithm
```

3. Перезапустите сервер — алгоритм мгновенно появится в выпадающем списке каждого улья.

> Подробный шаблон с комментариями: [`custom_example.py`](backend/simulation/algorithms/custom_example.py)

---

## Встроенные алгоритмы

| Имя | Описание |
|-----|----------|
| `greedy` | **Жадный** — все свободные пчёлы летят к цветку с максимальным нектаром |
| `nearest` | **Ближайший** — каждая пчела летит к ближайшему открытому цветку |
| `round_robin` | **Равномерный** — пчёлы распределяются по открытым цветкам по очереди |
| `probabilistic` | **Вероятностный** — цветок выбирается случайно, вероятность ∝ нектару |
| `selective` | **Избирательный** — летят только к цветкам с нектаром ≥ 2.0 |

---

## Параметры симуляции

| Параметр | Диапазон | По умолчанию |
|----------|----------|--------------|
| Скорость пчёл | 1–8 пкс/тик | 3.0 |
| Регенерация нектара | 0.01–0.20 ед/тик | 0.05 |
| Пчёл на улей | 1–30 | 10 |
| Количество цветов | 1–20 | 5 |
| Частота тиков | 1–30 тик/с | 10 |
| Макс. нектар пчелы | — | 1.0 |
| Скорость сбора | — | 0.2 ед/тик |
| Скорость разгрузки | — | 0.5 ед/тик |
| Нектар → мёд | — | 3 : 1 |

---

## Требования

- Python 3.10+
- `fastapi`, `uvicorn[standard]`, `websockets`
- Современный браузер (Chrome, Firefox, Edge)
