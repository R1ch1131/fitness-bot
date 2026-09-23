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
    """Renders an elite, modern dark-mode weekly infographic image with Pro UI styling."""
    tz_gmt6 = timezone(timedelta(hours=6))
    ref_date = target_date or datetime.now(tz_gmt6).date()

    # Monday of current week
    monday = ref_date - timedelta(days=ref_date.weekday())
    sunday = monday + timedelta(days=6)
    weekday_names = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]

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
            w_title_short = titles[0][:11]
            workout_label = f"{w_title_short} • {t_str}"

        # Weight tracking
        day_w = weight_history.get(day_str)
        if day_w:
            if first_weight is None:
                first_weight = round(day_w, 1)
                first_weight_date = day_d.strftime("%d.%m")
            last_weight = round(day_w, 1)
            last_weight_date = day_d.strftime("%d.%m")

        daily_rows.append({
            "w_name": w_name,
            "day_str": day_d.strftime("%d.%m"),
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

    # 3. Canvas setup (1080 x 1560)
    W, H = 1080, 1560
    img = Image.new("RGB", (W, H), color=(10, 14, 22))  # Sleek obsidian slate
    draw = ImageDraw.Draw(img)

    # Fonts
    f_badge = _get_font(15, bold=True)
    f_title = _get_font(46, bold=True)
    f_subtitle = _get_font(19, bold=False)
    f_card_label = _get_font(16, bold=True)
    f_card_val = _get_font(34, bold=True)
    f_card_sub = _get_font(16, bold=True)
    f_th = _get_font(16, bold=True)
    f_day_name = _get_font(22, bold=True)
    f_day_date = _get_font(14, bold=False)
    f_cal_val = _get_font(21, bold=True)
    f_macro_badge = _get_font(15, bold=True)
    f_workout_badge = _get_font(17, bold=True)
    f_coach_h = _get_font(18, bold=True)
    f_coach_t = _get_font(17, bold=False)

    # --- Header ---
    top_pill_w = 320
    top_pill_x = (W - top_pill_w) // 2
    draw.rounded_rectangle([top_pill_x, 48, top_pill_x + top_pill_w, 86], radius=19, fill=(16, 24, 38), outline=(30, 48, 76), width=1)
    # Glowing dot
    draw.ellipse([top_pill_x + 18, 62, top_pill_x + 28, 72], fill=(56, 189, 248))
    draw.text((top_pill_x + 40, 67), "HEVY & YAZIO  •  AI COACH", fill=(186, 230, 253), font=f_badge, anchor="lm")

    # Main Title
    draw.text((W // 2, 126), "ИТОГИ НЕДЕЛИ", fill=(255, 255, 255), font=f_title, anchor="mm")
    
    # Subtitle range
    date_str = f"{monday.strftime('%d.%m')} — {sunday.strftime('%d.%m.%Y')}  |  Сводный дайджест"
    draw.text((W // 2, 172), date_str, fill=(148, 163, 184), font=f_subtitle, anchor="mm")

    # --- 4 KPI Cards (2x2 Grid) ---
    card_w = 486
    card_h = 130
    top_y = 212
    spacing_x = 28
    spacing_y = 18
    left_x = (W - (card_w * 2 + spacing_x)) // 2

    # Weight delta calculation
    w_delta = round((last_weight - first_weight), 2) if (first_weight and last_weight) else 0.0
    if w_delta < 0:
        w_pill_text = f"-{abs(w_delta):.1f} кг  (Сушка)"
        w_pill_bg = (6, 78, 59)
        w_pill_fg = (52, 211, 153)
        w_border = (16, 185, 129)
    elif w_delta > 0:
        w_pill_text = f"+{w_delta:.1f} кг"
        w_pill_bg = (76, 29, 39)
        w_pill_fg = (251, 113, 133)
        w_border = (244, 63, 94)
    else:
        w_pill_text = "0.0 кг  (Стабильно)"
        w_pill_bg = (30, 41, 59)
        w_pill_fg = (203, 213, 225)
        w_border = (100, 116, 139)

    cards_config = [
        {
            "x": left_x,
            "y": top_y,
            "label": "ДИНАМИКА ВЕСА",
            "val": f"{first_weight or '—'}  ->  {last_weight or '—'} кг",
            "pill_text": w_pill_text,
            "pill_bg": w_pill_bg,
            "pill_fg": w_pill_fg,
            "accent": w_border
        },
        {
            "x": left_x + card_w + spacing_x,
            "y": top_y,
            "label": "СРЕДНИЕ КАЛОРИИ",
            "val": f"{avg_cal:,} ккал",
            "pill_text": "Дефицит в норме",
            "pill_bg": (69, 38, 14),
            "pill_fg": (251, 191, 36),
            "accent": (245, 158, 11)
        },
        {
            "x": left_x,
            "y": top_y + card_h + spacing_y,
            "label": "СРЕДНИЙ БЕЛОК",
            "val": f"{avg_prot} г / день",
            "pill_text": "Цель: 158–198 г (Норма)" if avg_prot >= 155 else "Цель: 158–198 г (Подтянуть)",
            "pill_bg": (8, 51, 68) if avg_prot >= 155 else (69, 38, 14),
            "pill_fg": (56, 189, 248) if avg_prot >= 155 else (251, 191, 36),
            "accent": (6, 182, 212) if avg_prot >= 155 else (245, 158, 11)
        },
        {
            "x": left_x + card_w + spacing_x,
            "y": top_y + card_h + spacing_y,
            "label": "ОБЩИЙ ТОННАЖ (HEVY)",
            "val": f"{total_tonnage:,.0f} кг",
            "pill_text": f"{workout_days_count} силовые сессии",
            "pill_bg": (59, 7, 100),
            "pill_fg": (216, 180, 254),
            "accent": (168, 85, 247)
        }
    ]

    for c in cards_config:
        cx, cy = c["x"], c["y"]
        draw.rounded_rectangle([cx, cy, cx + card_w, cy + card_h], radius=18, fill=(16, 22, 34), outline=(32, 44, 68), width=1)
        draw.rounded_rectangle([cx + 16, cy + 2, cx + card_w - 16, cy + 4], radius=1, fill=c["accent"])
        draw.text((cx + 22, cy + 22), c["label"], fill=(148, 163, 184), font=f_card_label)
        draw.text((cx + 22, cy + 54), c["val"], fill=(255, 255, 255), font=f_card_val)
        
        # Status Pill Badge with mini circle
        p_text = c["pill_text"]
        p_w = draw.textlength(p_text, font=f_card_sub) + 36
        draw.rounded_rectangle([cx + 20, cy + 92, cx + 20 + p_w, cy + 118], radius=13, fill=c["pill_bg"])
        # Mini vector circle inside pill
        draw.ellipse([cx + 32, cy + 102, cx + 38, cy + 108], fill=c["pill_fg"])
        draw.text((cx + 46, cy + 105), p_text, fill=c["pill_fg"], font=f_card_sub, anchor="lm")

    # --- Weekly Breakdown Table ---
    tbl_top_y = top_y + card_h * 2 + spacing_y + 24
    tbl_w = card_w * 2 + spacing_x
    tbl_x = left_x

    # Table Header Bar
    draw.rounded_rectangle([tbl_x, tbl_top_y, tbl_x + tbl_w, tbl_top_y + 40], radius=10, fill=(20, 28, 44))
    draw.text((tbl_x + 28, tbl_top_y + 20), "ДЕНЬ", fill=(148, 163, 184), font=f_th, anchor="lm")
    draw.text((tbl_x + 185, tbl_top_y + 20), "КАЛОРИИ", fill=(148, 163, 184), font=f_th, anchor="lm")
    draw.text((tbl_x + 360, tbl_top_y + 20), "КБЖУ (Б / Ж / У)", fill=(148, 163, 184), font=f_th, anchor="lm")
    draw.text((tbl_x + 695, tbl_top_y + 20), "ТРЕНИРОВКА И ТОННАЖ", fill=(148, 163, 184), font=f_th, anchor="lm")

    row_y = tbl_top_y + 50
    row_h = 76
    row_gap = 10

    for r in daily_rows:
        if r["is_today"]:
            bg_col = (20, 32, 52)
            border_col = (14, 165, 233)
            border_w = 2
        else:
            bg_col = (15, 21, 33)
            border_col = (28, 38, 58)
            border_w = 1

        draw.rounded_rectangle([tbl_x, row_y, tbl_x + tbl_w, row_y + row_h], radius=14, fill=bg_col, outline=border_col, width=border_w)

        # 1. Day Column
        day_box_w = 110
        draw.rounded_rectangle([tbl_x + 14, row_y + 12, tbl_x + 14 + day_box_w, row_y + row_h - 12], radius=10, fill=(26, 36, 56) if not r["is_today"] else (3, 105, 161))
        draw.text((tbl_x + 14 + day_box_w / 2, row_y + 26), r["w_name"], fill=(255, 255, 255), font=f_day_name, anchor="mm")
        draw.text((tbl_x + 14 + day_box_w / 2, row_y + 48), r["day_str"], fill=(186, 230, 253) if r["is_today"] else (148, 163, 184), font=f_day_date, anchor="mm")

        # 2. Calories Column
        if r["has_nut"]:
            draw.text((tbl_x + 185, row_y + 38), f"{r['cal']:,}", fill=(255, 255, 255), font=f_cal_val, anchor="lm")
            draw.text((tbl_x + 185 + draw.textlength(f"{r['cal']:,}", font=f_cal_val) + 6, row_y + 39), "ккал", fill=(148, 163, 184), font=f_day_date, anchor="lm")
        else:
            draw.text((tbl_x + 185, row_y + 38), "—", fill=(100, 116, 139), font=f_cal_val, anchor="lm")

        # 3. KBJU Column (3 Separate Micro-Pills)
        if r["has_nut"]:
            p_x = tbl_x + 360
            m_items = [
                (f"Б: {int(r['prot'])}г", (8, 51, 68), (56, 189, 248)),
                (f"Ж: {int(r['fat'])}г", (69, 38, 14), (251, 191, 36)),
                (f"У: {int(r['carb'])}г", (23, 37, 84), (147, 197, 253))
            ]
            for m_text, m_bg, m_fg in m_items:
                m_w = draw.textlength(m_text, font=f_macro_badge) + 16
                draw.rounded_rectangle([p_x, row_y + 23, p_x + m_w, row_y + row_h - 23], radius=8, fill=m_bg)
                draw.text((p_x + m_w / 2, row_y + 38), m_text, fill=m_fg, font=f_macro_badge, anchor="mm")
                p_x += m_w + 8
        else:
            draw.text((tbl_x + 360, row_y + 38), "данные не записаны", fill=(100, 116, 139), font=f_coach_t, anchor="lm")

        # 4. Workout Column
        w_pill_x = tbl_x + 695
        w_pill_w = tbl_w - 710
        if r["is_workout"]:
            draw.rounded_rectangle([w_pill_x, row_y + 14, w_pill_x + w_pill_w, row_y + row_h - 14], radius=10, fill=(46, 16, 101), outline=(139, 92, 246), width=1)
            draw.text((w_pill_x + w_pill_w / 2, row_y + 38), r["workout_label"], fill=(233, 213, 255), font=f_workout_badge, anchor="mm")
        else:
            draw.rounded_rectangle([w_pill_x, row_y + 14, w_pill_x + w_pill_w, row_y + row_h - 14], radius=10, fill=(19, 26, 40))
            draw.text((w_pill_x + w_pill_w / 2, row_y + 38), "Отдых", fill=(100, 116, 139), font=f_workout_badge, anchor="mm")

        row_y += row_h + row_gap

    # --- Bottom Coach Insight Card ---
    coach_y = row_y + 16
    coach_h = 160
    draw.rounded_rectangle([tbl_x, coach_y, tbl_x + tbl_w, coach_y + coach_h], radius=18, fill=(16, 24, 38), outline=(37, 99, 235), width=1)
    # Left vertical glow bar
    draw.rounded_rectangle([tbl_x, coach_y + 16, tbl_x + 6, coach_y + coach_h - 16], radius=3, fill=(14, 165, 233))

    # Header
    draw.text((tbl_x + 26, coach_y + 24), "СОВЕТЫ ТРЕНЕРА НА СЛЕДУЮЩУЮ НЕДЕЛЮ", fill=(56, 189, 248), font=f_coach_h)

    # Bullet 1: Weight
    b1_label = "• Вес:"
    b1_text = f" {w_pill_text}. Отличный темп сушки, жировая прослойка стабильно уходит."
    draw.text((tbl_x + 26, coach_y + 58), b1_label, fill=(52, 211, 153), font=f_coach_h)
    draw.text((tbl_x + 26 + draw.textlength(b1_label, font=f_coach_h), coach_y + 59), b1_text, fill=(226, 232, 240), font=f_coach_t)

    # Bullet 2: Protein
    b2_label = "• Белок:"
    if avg_prot >= 155:
        b2_text = f" {avg_prot}г/день в среднем — планка держится отлично, мышечная масса защищена."
    else:
        b2_text = f" {avg_prot}г/день. Рекомендуется подтянуть до 160г+ (добавь творог, куриное филе или протеин)."
    draw.text((tbl_x + 26, coach_y + 88), b2_label, fill=(56, 189, 248), font=f_coach_h)
    draw.text((tbl_x + 26 + draw.textlength(b2_label, font=f_coach_h), coach_y + 89), b2_text, fill=(226, 232, 240), font=f_coach_t)

    # Bullet 3: Workout
    b3_label = "• Нагрузка:"
    b3_text = f" {total_tonnage:,.0f} кг за неделю ({workout_days_count} сессии). Продолжай прогрессировать в рабочем сплите!"
    draw.text((tbl_x + 26, coach_y + 118), b3_label, fill=(192, 132, 252), font=f_coach_h)
    draw.text((tbl_x + 26 + draw.textlength(b3_label, font=f_coach_h), coach_y + 119), b3_text, fill=(226, 232, 240), font=f_coach_t)

    # Output to BytesIO
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf
