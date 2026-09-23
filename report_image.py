import os
import io
from pathlib import Path
from datetime import datetime, date, timedelta, timezone
from PIL import Image, ImageDraw, ImageFont

FONTS_DIR = Path(__file__).resolve().parent / "assets" / "fonts"
ROBOTO_REGULAR = FONTS_DIR / "Roboto-Regular.ttf"
ROBOTO_BOLD = FONTS_DIR / "Roboto-Bold.ttf"

def _get_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """Loads bundled Roboto font with system fallbacks."""
    target_path = ROBOTO_BOLD if bold else ROBOTO_REGULAR
    if target_path.exists():
        try:
            return ImageFont.truetype(str(target_path), size)
        except Exception:
            pass

    # Windows fallbacks
    sys_fallbacks = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in sys_fallbacks:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass

    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


def generate_weekly_report_image(coach, target_date=None) -> io.BytesIO:
    """Renders a sleek, modern dark-mode weekly infographic image with KPIs, table, and coach insights."""
    tz_gmt6 = timezone(timedelta(hours=6))
    ref_date = target_date or datetime.now(tz_gmt6).date()

    # Monday of current week
    monday = ref_date - timedelta(days=ref_date.weekday())
    sunday = monday + timedelta(days=6)
    weekday_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

    # 1. Fetch weight range from YAZIO
    weight_history = {}
    if coach.yazio.is_configured() and coach.yazio.client:
        try:
            from yazio_exporter.export_body import fetch_weight_range
            w_start_str = (monday - timedelta(days=7)).strftime("%Y-%m-%d")
            w_end_str = (sunday + timedelta(days=1)).strftime("%Y-%m-%d")
            weight_history = coach.yazio._execute_with_retry(
                fetch_weight_range, coach.yazio.client, w_start_str, w_end_str
            ) or {}
        except Exception as e:
            print(f"Weight history fetch note: {e}")

    # Map workouts by local date (GMT+6)
    from analyzer import parse_iso
    workouts_by_date = {}
    for w in coach.workouts:
        iso_start = w.get("start_time")
        if iso_start:
            try:
                dt = parse_iso(iso_start)
                if dt:
                    local_d = dt.astimezone(tz_gmt6).date()
                    workouts_by_date.setdefault(local_d, []).append(w)
            except Exception:
                pass

    # 2. Collect daily data for Monday..Sunday
    daily_rows = []
    total_tonnage = 0.0
    total_calories = 0.0
    total_protein = 0.0
    total_fat = 0.0
    total_carbs = 0.0
    logged_days_count = 0
    workout_days_count = 0

    first_weight = None
    first_weight_date = None
    last_weight = None
    last_weight_date = None

    for i in range(7):
        day_d = monday + timedelta(days=i)
        day_str = day_d.strftime("%Y-%m-%d")
        w_name = weekday_names[i]
        day_label = f"{w_name} {day_d.strftime('%d.%m')}"

        # Nutrition
        cal = 0
        prot = 0.0
        fat = 0.0
        carb = 0.0
        has_nut = False

        if coach.yazio.is_configured() and day_d <= ref_date:
            try:
                summary = coach.yazio.get_daily_summary(day_d)
                if summary:
                    cal = round(summary.get("calories", 0))
                    prot = round(summary.get("protein", 0), 1)
                    fat = round(summary.get("fat", 0), 1)
                    carb = round(summary.get("carbs", 0), 1)
                    if cal > 0 or prot > 0:
                        has_nut = True
                        total_calories += cal
                        total_protein += prot
                        total_fat += fat
                        total_carbs += carb
                        logged_days_count += 1
            except Exception:
                pass

        # Workout & Tonnage
        day_workouts = workouts_by_date.get(day_d, [])
        day_tonnage = 0.0
        workout_label = "Отдых"
        is_workout = False
        if day_workouts:
            is_workout = True
            workout_days_count += len(day_workouts)
            titles = []
            for dw in day_workouts:
                an = coach.analyzer.analyze_workout(dw)
                t_kg = an.get("total_tonnage_kg", 0.0)
                day_tonnage += t_kg
                titles.append(dw.get("title", "Тренировка"))
            total_tonnage += day_tonnage
            t_str = f"{day_tonnage / 1000:.1f}т" if day_tonnage >= 1000 else f"{int(day_tonnage)}кг"
            w_title_short = titles[0][:10]
            workout_label = f"{w_title_short} ({t_str})"

        # Weight tracking
        day_w = weight_history.get(day_str)
        if day_w:
            if first_weight is None:
                first_weight = round(day_w, 1)
                first_weight_date = day_d.strftime("%d.%m")
            last_weight = round(day_w, 1)
            last_weight_date = day_d.strftime("%d.%m")

        daily_rows.append({
            "day_label": day_label,
            "day_d": day_d,
            "cal": cal,
            "prot": prot,
            "fat": fat,
            "carb": carb,
            "has_nut": has_nut,
            "workout_label": workout_label,
            "is_workout": is_workout,
            "is_today": (day_d == ref_date)
        })

    # Weight fallbacks
    if first_weight is None or last_weight is None:
        try:
            prof = coach.yazio.get_user_profile() if coach.yazio.is_configured() else {}
            cur_w = prof.get("current_weight_kg")
            if first_weight is None:
                past_weights = {k: v for k, v in weight_history.items() if k <= monday.strftime("%Y-%m-%d")}
                if past_weights:
                    closest_k = max(past_weights.keys())
                    first_weight = round(past_weights[closest_k], 1)
                    first_weight_date = datetime.strptime(closest_k, "%Y-%m-%d").strftime("%d.%m")
                else:
                    first_weight = cur_w
                    first_weight_date = monday.strftime("%d.%m")
            if last_weight is None:
                last_weight = cur_w
                last_weight_date = ref_date.strftime("%d.%m")
        except Exception:
            pass

    avg_cal = round(total_calories / logged_days_count) if logged_days_count > 0 else 0
    avg_prot = round(total_protein / logged_days_count, 1) if logged_days_count > 0 else 0
    avg_fat = round(total_fat / logged_days_count, 1) if logged_days_count > 0 else 0
    avg_carb = round(total_carbs / logged_days_count, 1) if logged_days_count > 0 else 0

    # 3. Canvas setup
    W, H = 1080, 1480
    img = Image.new("RGB", (W, H), color=(11, 15, 23))  # Deep Obsidian
    draw = ImageDraw.Draw(img)

    # Fonts
    f_badge = _get_font(18, bold=True)
    f_title = _get_font(42, bold=True)
    f_subtitle = _get_font(20, bold=False)
    f_card_label = _get_font(18, bold=False)
    f_card_val = _get_font(32, bold=True)
    f_card_sub = _get_font(18, bold=True)
    f_th = _get_font(17, bold=True)
    f_tb_main = _get_font(22, bold=True)
    f_tb_sub = _get_font(18, bold=False)
    f_coach_h = _get_font(20, bold=True)
    f_coach_t = _get_font(19, bold=False)

    # Decorative header glow
    draw.ellipse([W//2 - 350, -100, W//2 + 350, 150], fill=(20, 35, 60))

    # --- Header ---
    pill_text = "HEVY & YAZIO AI COACH"
    draw.rounded_rectangle([W//2 - 160, 40, W//2 + 160, 76], radius=18, fill=(18, 30, 48), outline=(56, 189, 248), width=1)
    draw.text((W//2, 58), pill_text, fill=(56, 189, 248), font=f_badge, anchor="mm")

    # Title & Dates
    draw.text((W//2, 115), "ИТОГИ НЕДЕЛИ", fill=(248, 250, 252), font=f_title, anchor="mm")
    date_str = f"{monday.strftime('%d.%m')} — {sunday.strftime('%d.%m.%Y')}"
    draw.text((W//2, 160), date_str, fill=(148, 163, 184), font=f_subtitle, anchor="mm")

    # --- 4 KPI Cards (2x2 Grid) ---
    card_w = 480
    card_h = 120
    top_y = 195
    spacing_x = 40
    spacing_y = 20
    left_x = (W - (card_w * 2 + spacing_x)) // 2

    # Weight delta text
    w_delta = round((last_weight - first_weight), 2) if (first_weight and last_weight) else 0.0
    w_delta_color = (34, 197, 94) if w_delta <= 0 else (244, 63, 94)  # green or rose
    w_delta_str = f"-{abs(w_delta):.1f} кг за неделю (Сушка)" if w_delta < 0 else (f"+{w_delta:.1f} кг" if w_delta > 0 else "0.0 кг (Стабильно)")

    cards_data = [
        # (x, y, label, val, sub, sub_color, border_color)
        (
            left_x, top_y,
            "ДИНАМИКА ВЕСА",
            f"{first_weight or '—'} -> {last_weight or '—'} кг",
            w_delta_str,
            w_delta_color,
            (34, 197, 94)
        ),
        (
            left_x + card_w + spacing_x, top_y,
            "СРЕДНИЕ КАЛОРИИ",
            f"{avg_cal:,} ккал / день",
            "Дефицит под контролем",
            (245, 158, 11),
            (245, 158, 11)
        ),
        (
            left_x, top_y + card_h + spacing_y,
            "СРЕДНИЙ БЕЛОК",
            f"{avg_prot} г / день",
            f"Норма: 158–198 г ({'В норме' if avg_prot >= 155 else 'Подтянуть'})",
            (6, 182, 212) if avg_prot >= 155 else (245, 158, 11),
            (6, 182, 212)
        ),
        (
            left_x + card_w + spacing_x, top_y + card_h + spacing_y,
            "ОБЩИЙ ТОННАЖ (HEVY)",
            f"{total_tonnage:,.0f} кг",
            f"{workout_days_count} силовых тренировок",
            (168, 85, 247),
            (168, 85, 247)
        )
    ]

    for cx, cy, label, val, sub, sub_color, border_color in cards_data:
        draw.rounded_rectangle([cx, cy, cx + card_w, cy + card_h], radius=16, fill=(18, 25, 38), outline=(35, 48, 71), width=1)
        draw.rounded_rectangle([cx, cy + 12, cx + 4, cy + card_h - 12], radius=2, fill=border_color)
        draw.text((cx + 20, cy + 20), label, fill=(148, 163, 184), font=f_card_label)
        draw.text((cx + 20, cy + 54), val, fill=(248, 250, 252), font=f_card_val)
        draw.text((cx + 20, cy + 92), sub, fill=sub_color, font=f_card_sub)

    # --- Weekly Breakdown Table ---
    tbl_top_y = 490
    tbl_w = card_w * 2 + spacing_x
    tbl_x = left_x

    # Table Header Bar
    draw.rounded_rectangle([tbl_x, tbl_top_y, tbl_x + tbl_w, tbl_top_y + 44], radius=10, fill=(24, 34, 52))
    draw.text((tbl_x + 24, tbl_top_y + 22), "ДЕНЬ", fill=(148, 163, 184), font=f_th, anchor="lm")
    draw.text((tbl_x + 190, tbl_top_y + 22), "КАЛОРИИ", fill=(148, 163, 184), font=f_th, anchor="lm")
    draw.text((tbl_x + 380, tbl_top_y + 22), "КБЖУ (Б / Ж / У)", fill=(148, 163, 184), font=f_th, anchor="lm")
    draw.text((tbl_x + 690, tbl_top_y + 22), "ТРЕНИРОВКА И ТОННАЖ", fill=(148, 163, 184), font=f_th, anchor="lm")

    row_y = tbl_top_y + 54
    row_h = 72
    row_gap = 10

    for r in daily_rows:
        bg_col = (20, 28, 42) if not r["is_today"] else (26, 40, 62)
        border_col = (45, 60, 88) if not r["is_today"] else (56, 189, 248)
        border_w = 2 if r["is_today"] else 1

        draw.rounded_rectangle([tbl_x, row_y, tbl_x + tbl_w, row_y + row_h], radius=12, fill=bg_col, outline=border_col, width=border_w)

        # Day Pill
        day_badge_bg = (30, 42, 64) if not r["is_today"] else (14, 116, 144)
        draw.rounded_rectangle([tbl_x + 16, row_y + 14, tbl_x + 155, row_y + row_h - 14], radius=8, fill=day_badge_bg)
        draw.text((tbl_x + 85, row_y + row_h // 2), r["day_label"], fill=(248, 250, 252), font=f_tb_main, anchor="mm")

        # Calories
        if r["has_nut"]:
            draw.text((tbl_x + 190, row_y + row_h // 2 - 2), f"{r['cal']:,} ккал", fill=(248, 250, 252), font=f_tb_main, anchor="lm")
        else:
            draw.text((tbl_x + 190, row_y + row_h // 2), "—", fill=(100, 116, 139), font=f_tb_main, anchor="lm")

        # KBJU
        if r["has_nut"]:
            macros_line = f"Б: {int(r['prot'])}г   Ж: {int(r['fat'])}г   У: {int(r['carb'])}г"
            draw.text((tbl_x + 380, row_y + row_h // 2 - 2), macros_line, fill=(203, 213, 225), font=f_tb_sub, anchor="lm")
        else:
            draw.text((tbl_x + 380, row_y + row_h // 2), "не записано", fill=(100, 116, 139), font=f_tb_sub, anchor="lm")

        # Workout badge
        if r["is_workout"]:
            w_badge_bg = (49, 24, 75)
            w_border = (168, 85, 247)
            w_text_col = (216, 180, 254)
            draw.rounded_rectangle([tbl_x + 685, row_y + 14, tbl_x + tbl_w - 16, row_y + row_h - 14], radius=8, fill=w_badge_bg, outline=w_border, width=1)
            draw.text((tbl_x + 685 + (tbl_w - 701) // 2, row_y + row_h // 2), r['workout_label'], fill=w_text_col, font=f_tb_main, anchor="mm")
        else:
            draw.rounded_rectangle([tbl_x + 685, row_y + 14, tbl_x + tbl_w - 16, row_y + row_h - 14], radius=8, fill=(15, 23, 35))
            draw.text((tbl_x + 685 + (tbl_w - 701) // 2, row_y + row_h // 2), "Отдых", fill=(100, 116, 139), font=f_tb_sub, anchor="mm")

        row_y += row_h + row_gap

    # --- Bottom Coach Advice Card ---
    coach_y = row_y + 15
    coach_h = 160
    draw.rounded_rectangle([tbl_x, coach_y, tbl_x + tbl_w, coach_y + coach_h], radius=16, fill=(15, 26, 42), outline=(37, 99, 235), width=2)
    # Header
    draw.text((tbl_x + 24, coach_y + 24), "РЕЗЮМЕ И СОВЕТЫ ТРЕНЕРА НА СЛЕДУЮЩУЮ НЕДЕЛЮ:", fill=(56, 189, 248), font=f_coach_h)

    # Bullet 1
    b1 = f"• Вес: {w_delta_str}. Отличная динамика! Жировая прослойка уходит, форма улучшается."
    draw.text((tbl_x + 24, coach_y + 60), b1, fill=(226, 232, 240), font=f_coach_t)

    # Bullet 2
    if avg_prot >= 155:
        b2 = f"• Белок: в среднем {avg_prot}г/день — целевая планка держится отлично, мышечная масса защищена."
    else:
        b2 = f"• Белок: в среднем {avg_prot}г/день. Рекомендуется подтянуть до 160г+ (добавь творог/грудку/протеин)."
    draw.text((tbl_x + 24, coach_y + 92), b2, fill=(226, 232, 240), font=f_coach_t)

    # Bullet 3
    b3 = f"• Нагрузка: {total_tonnage:,.0f} кг за неделю ({workout_days_count} сессии). Продолжай прогрессировать в рабочем сплите!"
    draw.text((tbl_x + 24, coach_y + 124), b3, fill=(226, 232, 240), font=f_coach_t)

    # Output to BytesIO
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf
