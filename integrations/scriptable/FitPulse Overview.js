// FitPulse Overview · вес + три последних отправленных push. Средний размер Scriptable.
// Секрет вводится при первом запуске и хранится в Keychain, а не в этом файле.
const SERVER = "https://fitness-bot-9f8m.onrender.com";
const KEY = "fitpulse.weight.health-token.v1";
const fm = FileManager.local();
const CACHE = fm.joinPath(fm.libraryDirectory(), "fitpulse-overview-v1.json");
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
  return d && Array.isArray(d.notifications) && d.notifications.length <= 3
    && d.notifications.every(n => n && typeof n.title === 'string' && typeof n.body === 'string'
      && Number.isFinite(Date.parse(n.sent_at)) && typeof n.url === 'string' && n.url.startsWith('/') && !n.url.startsWith('//'))
    && Number.isFinite(Date.parse(d.as_of)) && d.source === "apple_health" && ["ok", "empty"].includes(d.status)
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
  w.backgroundColor = new Color(color.bg); w.setPadding(18, 18, 18, 18);
  text(w, "FITPULSE", 11, color.green, true); w.addSpacer(10);
  const t = text(w, message, 13, color.muted); t.lineLimit = 5;
  w.url = URLScheme.forRunningScript();
  w.refreshAfterDate = new Date(Date.now() + 15 * 60000);
  return w;
}
function clock(value) {
  return new Date(value).toLocaleTimeString('ru-RU', {timeZone:'Asia/Omsk',hour:'2-digit',minute:'2-digit'});
}
function sentTime(value) {
  const nowDay = new Date(Date.now() + 6 * 3600000).toISOString().slice(0,10);
  const dayInOmsk = new Date(Date.parse(value) + 6 * 3600000).toISOString().slice(0,10);
  return (dayInOmsk === nowDay ? '' : `${day(dayInOmsk)} `) + clock(value);
}
function render(data, offline = false, savedAt = null) {
  if (config.widgetFamily === 'small') return messageWidget('Для веса и трёх уведомлений выбери средний прямоугольный размер Scriptable.');
  const w = new ListWidget();
  w.backgroundColor = new Color(color.bg); w.setPadding(12, 14, 12, 14);
  w.url = SERVER + '/?tab=weekly';
  w.refreshAfterDate = new Date(Date.now() + 15 * 60000);
  const columns = w.addStack();
  const left = columns.addStack(); left.layoutVertically(); left.size = new Size(112, 0);
  text(left, 'FITPULSE · ЦЕЛЬ 80', 9, color.green, true); left.addSpacer(6);
  if (data.status === 'ok') {
    text(left, `${number(data.current_weight)} кг`, 27, color.text, true); left.addSpacer(7);
    const bar = left.addImage(progress(data.progress_percent)); bar.imageSize = new Size(106, 5);
    left.addSpacer(5); text(left, `${number(data.progress_percent)}% пути`, 12, color.green, true);
    left.addSpacer(3); text(left, `Ещё ${number(data.remaining_kg)} кг`, 10, color.muted);
    left.addSpacer(4); text(left, `Замер ${day(data.measured_on)}`, 9, color.muted);
  } else {
    text(left, 'Нет замера', 19, color.text, true); left.addSpacer(6);
    const note = text(left, 'Запусти экспорт здоровья', 10, color.muted); note.lineLimit = 2;
  }
  columns.addSpacer(10);
  const divider = columns.addStack(); divider.size = new Size(1, 112); divider.backgroundColor = new Color(color.track);
  columns.addSpacer(10);
  const right = columns.addStack(); right.layoutVertically();
  text(right, 'ОТПРАВЛЕННЫЕ PUSH', 10, color.muted, true); right.addSpacer(6);
  if (!data.notifications.length) {
    const note = text(right, 'Здесь появятся три последних уведомления после обновления сервера.', 10, color.muted); note.lineLimit = 5;
  }
  for (let i = 0; i < data.notifications.length; i++) {
    const n = data.notifications[i];
    const entry = right.addStack(); entry.layoutVertically(); entry.url = SERVER + n.url;
    const title = text(entry, n.title, 13, color.text, true); title.minimumScaleFactor = 0.9;
    entry.addSpacer(1);
    const detail = text(entry, `${sentTime(n.sent_at)} · ${n.body}`, 11, color.muted); detail.minimumScaleFactor = 1;
    if (i < data.notifications.length - 1) right.addSpacer(4);
  }
  w.addSpacer();
  const refreshed = new Date(savedAt || data.as_of).toISOString();
  text(w, `${offline ? 'Нет связи · сохранено' : 'Данные обновлены'} ${sentTime(refreshed)} · Омск`, 9, offline ? 'f59e0b' : color.muted);
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
  const request = new Request(SERVER + "/api/widgets/overview");
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
      const menu = new Alert(); menu.title = "FitPulse · обзор";
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
