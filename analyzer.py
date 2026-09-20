from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

def parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        # Replace Z with +00:00 for standard fromisoformat
        clean = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(clean)
    except Exception:
        return None

def estimate_1rm(weight: float, reps: int) -> float:
    """Calculates estimated 1RM using Epley formula."""
    if reps <= 0 or weight <= 0:
        return 0.0
    if reps == 1:
        return weight
    return round(weight * (1 + reps / 30.0), 1)

def classify_muscle_group(exercise_title: str) -> str:
    """Classifies exercise into anatomical muscle category."""
    title = exercise_title.lower()
    
    # Cardio
    if any(k in title for k in ["treadmill", "дорожка", "бег", "run", "bike", "вело", "rower"]):
        return "Кардио"
    
    # Chest
    if any(k in title for k in ["bench press", "жим лежа", "жим лёжа", "chest", "груд"]):
        return "Грудь"
    
    # Shoulders
    if any(k in title for k in ["shoulder press", "жим от плеч", "жим стоя", "lateral raise", "махи", "плеч", "дельт"]):
        return "Плечи"
    
    # Back
    if any(k in title for k in ["lat pulldown", "вертикальная тяга", "cable row", "горизонтальная тяга", "bent over row", "тяга в наклоне", "pull up", "подтягиван", "спин"]):
        return "Спина"
    
    # Arms - Triceps
    if any(k in title for k in ["triceps", "трицепс", "брусья", "разгибание рук"]):
        return "Трицепс"
    
    # Arms - Biceps
    if any(k in title for k in ["biceps", "бицепс", "hammer", "молот", "сгибание рук"]):
        return "Бицепс"
    
    # Legs - Posterior Chain & Deadlift
    if any(k in title for k in ["deadlift", "становая тяга", "romanian", "румынская", "leg curl", "сгибание ног"]):
        return "Задняя поверхность / Ягодицы"
    
    # Legs - Quads & General
    if any(k in title for k in ["squat", "присед", "leg press", "жим ногами", "leg extension", "разгибание ног", "lunge", "выпад", "calf", "голень"]):
        return "Квадрицепсы / Ноги"
    
    # Core
    if any(k in title for k in ["crunch", "скручиван", "plank", "планка", "пресс", "hyperextension", "гиперэкстенз"]):
        return "Кор / Пресс"
    
    return "Другое"

class WorkoutAnalyzer:
    """Analytical engine for evaluating workouts, progressive overload and fatigue."""

    def __init__(self, workouts: List[Dict[str, Any]]):
        # Sort workouts chronologically: oldest first for progression tracking
        self.workouts = sorted(
            workouts,
            key=lambda w: parse_iso(w.get("start_time")) or datetime.min
        )

    def get_latest_workout(self) -> Optional[Dict[str, Any]]:
        return self.workouts[-1] if self.workouts else None

    def analyze_workout(self, workout: Dict[str, Any]) -> Dict[str, Any]:
        """Calculates detailed metrics for a single workout."""
        start = parse_iso(workout.get("start_time"))
        end = parse_iso(workout.get("end_time"))
        duration_minutes = round((end - start).total_seconds() / 60, 1) if (start and end) else 0

        total_tonnage = 0.0
        total_working_sets = 0
        total_reps = 0
        muscle_tonnage = {}
        exercises_analysis = []
        cardio_info = []

        for ex in workout.get("exercises", []):
            title = ex.get("title", "Без названия")
            muscle = classify_muscle_group(title)
            sets = ex.get("sets", [])

            ex_tonnage = 0.0
            ex_reps = 0
            ex_working_sets = 0
            max_weight = 0.0
            best_set_1rm = 0.0
            set_summaries = []

            is_cardio = (muscle == "Кардио")
            cardio_dist = 0.0
            cardio_duration_sec = 0

            for s in sets:
                stype = s.get("type", "normal")
                w = float(s.get("weight_kg") or 0.0)
                r = int(s.get("reps") or 0)
                dist = float(s.get("distance_meters") or 0.0)
                dur = int(s.get("duration_seconds") or 0)

                if is_cardio or dist > 0 or dur > 0:
                    cardio_dist += dist
                    cardio_duration_sec += dur
                    continue

                if stype != "warmup":
                    ex_working_sets += 1
                    tonnage = w * r
                    ex_tonnage += tonnage
                    ex_reps += r

                if w > max_weight:
                    max_weight = w

                s_1rm = estimate_1rm(w, r)
                if s_1rm > best_set_1rm:
                    best_set_1rm = s_1rm

                set_str = f"{w} кг x {r}" if w > 0 else f"{r} повт"
                if stype == "warmup":
                    set_str += " (разминка)"
                set_summaries.append(set_str)

            if is_cardio or cardio_dist > 0:
                km = round(cardio_dist / 1000.0, 2)
                mins = round(cardio_duration_sec / 60.0, 1)
                speed_kmh = round((km / (mins / 60.0)), 1) if mins > 0 else 0.0
                pace_str = ""
                if km > 0 and mins > 0:
                    pace_sec_per_km = cardio_duration_sec / km
                    pace_str = f"{int(pace_sec_per_km // 60)}:{int(pace_sec_per_km % 60):02d} мин/км"

                cardio_info.append({
                    "title": title,
                    "distance_km": km,
                    "duration_minutes": mins,
                    "speed_kmh": speed_kmh,
                    "pace": pace_str
                })
            else:
                total_tonnage += ex_tonnage
                total_working_sets += ex_working_sets
                total_reps += ex_reps
                muscle_tonnage[muscle] = round(muscle_tonnage.get(muscle, 0.0) + ex_tonnage, 1)

                exercises_analysis.append({
                    "title": title,
                    "muscle": muscle,
                    "working_sets": ex_working_sets,
                    "total_reps": ex_reps,
                    "tonnage_kg": round(ex_tonnage, 1),
                    "max_weight_kg": max_weight,
                    "estimated_1rm": best_set_1rm,
                    "sets_formatted": set_summaries
                })

        return {
            "id": workout.get("id"),
            "title": workout.get("title", "Тренировка"),
            "date": start.strftime("%d.%m.%Y") if start else "N/A",
            "start_time": start.strftime("%H:%M") if start else "N/A",
            "duration_minutes": duration_minutes,
            "total_tonnage_kg": round(total_tonnage, 1),
            "total_working_sets": total_working_sets,
            "total_reps": total_reps,
            "muscle_tonnage": muscle_tonnage,
            "exercises": exercises_analysis,
            "cardio": cardio_info
        }

    def track_exercise_progression(self, target_exercise_title: str = "", template_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Finds all occurrences of an exercise across history to evaluate overload by template ID or title."""
        history = []
        target_lower = target_exercise_title.lower().strip() if target_exercise_title else ""

        for w in self.workouts:
            start = parse_iso(w.get("start_time"))
            date_str = start.strftime("%d.%m.%Y") if start else "N/A"

            for ex in w.get("exercises", []):
                title = ex.get("title", "")
                ex_template = ex.get("exercise_template_id")
                
                matched = False
                if template_id and ex_template and template_id == ex_template:
                    matched = True
                elif target_lower and (target_lower in title.lower() or title.lower() in target_lower):
                    matched = True

                if matched:
                    sets = [s for s in ex.get("sets", []) if s.get("type") != "warmup"]
                    max_w = max([float(s.get("weight_kg") or 0) for s in sets], default=0.0)
                    total_tonnage = sum([float(s.get("weight_kg") or 0) * int(s.get("reps") or 0) for s in sets])
                    best_1rm = max([estimate_1rm(float(s.get("weight_kg") or 0), int(s.get("reps") or 0)) for s in sets], default=0.0)
                    set_str = ", ".join([f"{s.get('weight_kg')}x{s.get('reps')}" for s in sets if s.get('weight_kg')])

                    history.append({
                        "workout_title": w.get("title"),
                        "date": date_str,
                        "sets_count": len(sets),
                        "max_weight": max_w,
                        "tonnage": total_tonnage,
                        "estimated_1rm": best_1rm,
                        "sets": set_str
                    })
        return history

    def get_weekly_stats(self) -> Dict[str, Any]:
        """Calculates global metrics across all logged workouts."""
        total_tonnage = 0.0
        total_time_mins = 0.0
        total_cardio_km = 0.0
        muscle_distribution = {}

        for w in self.workouts:
            res = self.analyze_workout(w)
            total_tonnage += res["total_tonnage_kg"]
            total_time_mins += res["duration_minutes"]
            for c in res["cardio"]:
                total_cardio_km += c["distance_km"]
            for m, ton in res["muscle_tonnage"].items():
                muscle_distribution[m] = round(muscle_distribution.get(m, 0.0) + ton, 1)

        return {
            "workouts_count": len(self.workouts),
            "total_tonnage_kg": round(total_tonnage, 1),
            "total_duration_hours": round(total_time_mins / 60.0, 1),
            "total_cardio_km": round(total_cardio_km, 2),
            "muscle_distribution": muscle_distribution
        }
