// FitPulse · вес и прогресс до цели. Scriptable, маленький или средний виджет.
// Секрет вводится при первом запуске и хранится в Keychain, а не в этом файле.
const SERVER = "https://fitness-bot-9f8m.onrender.com";
const KEY = "fitpulse.weight.health-token.v1";
const fm = FileManager.local();
const CACHE = fm.joinPath(fm.libraryDirectory(), "fitpulse-weight-v1.json");
const color = { bg: "0b0f19", text: "f8fafc", muted: "94a3b8", green: "00d084", track: "1e293b" };

function eraseCache() {
  try { if (fm.fileExists(CACHE)) fm.remove(CACHE); } catch (_) {}
}
function readCache() {
  try {
    const saved = JSON.parse(fm.readString(CACHE));
    return valid(saved.data) && Number.isFinite(saved.savedAt) ? saved : null;
  } catch (_) { return null; }
}
function valid(d) {
  return d && d.source === "apple_health" && ["ok", "empty"].includes(d.status)
    && Number.isFinite(d.goal_weight) && d.goal_weight > 0
    && (d.status === "empty" ? d.current_weight === null :
      Number.isFinite(d.current_weight) && d.current_weight > 0 &&
      Number.isFinite(d.progress_percent) && d.progress_percent >= 0 && d.progress_percent <= 100 &&
      Number.isFinite(d.lost_kg) && Number.isFinite(d.remaining_kg) &&
      typeof d.measured_on === "string" && /^\d{4}-\d{2}-\d{2}$/.test(d.measured_on));
}
function text(stack, value, size, fill = color.text, bold = false) {
  const t = stack.addText(value);
  t.font = bold ? Font.boldSystemFont(size) : Font.systemFont(size);
  t.textColor = new Color(fill);
  t.lineLimit = 1; t.minimumScaleFactor = 0.8;
  return t;
}
function number(v) { return Number(v).toFixed(1).replace(".", ",").replace(/,0$/, ""); }
function day(value) {
  const bits = value.split("-");
  return `${Number(bits[2])} ${["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"][Number(bits[1]) - 1]}`;
}
function progress(pct) {
  const ctx = new DrawContext();
  ctx.size = new Size(600, 12); ctx.opaque = false; ctx.respectScreenScale = true;
  ctx.setFillColor(new Color(color.track)); ctx.fillRect(new Rect(0, 0, 600, 12));
  ctx.setFillColor(new Color(color.green)); ctx.fillRect(new Rect(0, 0, Math.max(0, Math.min(100, pct)) * 6, 12));
  return ctx.getImage();
}
function messageWidget(message) {
  const w = new ListWidget();
  w.backgroundColor = new Color(color.bg); w.setPadding(14, 14, 14, 14);
  text(w, "FITPULSE", 11, color.green, true); w.addSpacer(10);
  const t = text(w, message, 13, color.muted); t.lineLimit = 5;
  w.url = URLScheme.forRunningScript();
  w.refreshAfterDate = new Date(Date.now() + 15 * 60000);
  return w;
}
function render(data, offline = false, savedAt = null) {
  if (data.status === "empty") return messageWidget("Пока нет веса. Запусти команду Health Export Kit на iPhone.");
  const small = config.widgetFamily === "small";
  const w = new ListWidget();
  w.backgroundColor = new Color(color.bg); w.setPadding(14, 14, 14, 14);
  w.url = SERVER + "/?tab=weekly";
  w.refreshAfterDate = new Date(Date.now() + 30 * 60000);
  const head = w.addStack(); head.centerAlignContent();
  text(head, "FITPULSE", 10, color.green, true); head.addSpacer();
  text(head, `ЦЕЛЬ ${number(data.goal_weight)} КГ`, small ? 9 : 10, color.muted);
  w.addSpacer(small ? 7 : 8);
  const row = w.addStack(); row.centerAlignContent();
  text(row, `${number(data.current_weight)} кг`, small ? 30 : 36, color.text, true);
  if (!small) {
    row.addSpacer();
    const right = row.addStack(); right.layoutVertically();
    text(right, `${number(data.progress_percent)}%`, 22, color.green, true);
    text(right, "пути пройдено", 10, color.muted);
  }
  w.addSpacer(8);
  const bar = w.addImage(progress(data.progress_percent));
  bar.imageSize = new Size(small ? 120 : 280, 6);
  w.addSpacer(6);
  if (small) {
    text(w, `${number(data.progress_percent)}% · осталось ${number(data.remaining_kg)} кг`, 10, color.green);
  } else {
    const labels = w.addStack();
    text(labels, `Сброшено ${number(data.lost_kg)} кг`, 11, color.muted);
    labels.addSpacer(); text(labels, `Осталось ${number(data.remaining_kg)} кг`, 11, color.muted);
  }
  w.addSpacer();
  const stale = Date.now() - Date.parse(data.measured_on + "T12:00:00+06:00") > 8 * 86400000;
  const footer = offline ? `Нет связи · замер ${day(data.measured_on)}` :
    `${stale ? "Давний замер" : "Замер"} ${day(data.measured_on)} · Apple Здоровье`;
  text(w, footer, small ? 8 : 9, offline || stale ? "f59e0b" : color.muted);
  if (offline && savedAt) {
    w.refreshAfterDate = new Date(Date.now() + 15 * 60000);
  }
  return w;
}
async function configure() {
  const a = new Alert();
  a.title = "Подключить FitPulse";
  a.message = "Вставь тот же HEALTH_IMPORT_TOKEN, что в Render и команде на iPhone. Только ключ, без слова Bearer.";
  a.addSecureTextField("Ключ подключения", ""); a.addAction("Сохранить"); a.addCancelAction("Отмена");
  if (await a.presentAlert() < 0) return false;
  const token = a.textFieldValue(0).trim().replace(/^Bearer\s+/i, "");
  if (token.length < 32) {
    const e = new Alert(); e.title = "Проверь ключ"; e.message = "Нужен полный ключ из Render, не короче 32 символов.";
    e.addAction("Понятно"); await e.presentAlert(); return false;
  }
  eraseCache(); Keychain.set(KEY, token); return true;
}
async function load() {
  const request = new Request(SERVER + "/api/widgets/weight");
  request.headers = { Authorization: "Bearer " + Keychain.get(KEY), Accept: "application/json" };
  request.timeoutInterval = 10;
  // Never forward the authorization header to a redirect destination.
  request.onRedirect = () => null;
  try {
    const body = await request.loadString();
    const status = request.response && request.response.statusCode;
    if (status === 401 || status === 403) { eraseCache(); return messageWidget("Неверный ключ. Открой скрипт в Scriptable и выбери «Изменить ключ»."); }
    if (status !== 200) throw new Error("Server unavailable");
    const data = JSON.parse(body);
    if (!valid(data)) throw new Error("Invalid data");
    try { fm.writeString(CACHE, JSON.stringify({ data, savedAt: Date.now() })); } catch (_) {}
    return render(data);
  } catch (_) {
    const status = request.response && request.response.statusCode;
    if (status === 401 || status === 403) { eraseCache(); return messageWidget("Проверь ключ подключения в Scriptable."); }
    const saved = readCache();
    return saved ? render(saved.data, true, saved.savedAt) : messageWidget("Сервер пока недоступен. Открой FitPulse и попробуй ещё раз.");
  }
}
async function main() {
  if (config.runsInApp) {
    if (Keychain.contains(KEY)) {
      const menu = new Alert(); menu.title = "FitPulse · вес";
      menu.addAction("Показать виджет"); menu.addAction("Изменить ключ"); menu.addDestructiveAction("Удалить ключ и сохранённые данные"); menu.addCancelAction("Отмена");
      const action = await menu.presentSheet();
      if (action < 0) return;
      if (action === 2) { Keychain.remove(KEY); eraseCache(); return; }
      if (action === 1 && !await configure()) return;
    } else if (!await configure()) return;
  }
  const widget = Keychain.contains(KEY) ? await load() : messageWidget("Открой этот скрипт в Scriptable и введи ключ подключения.");
  Script.setWidget(widget);
  if (config.runsInApp) await widget.presentMedium();
}
await main();
Script.complete();
