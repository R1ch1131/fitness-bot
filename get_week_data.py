from yazio_client import YazioManager
from datetime import date

ym = YazioManager()
for day_num in range(13, 20):
    d = date(2026, 9, day_num)
    s = ym.get_daily_summary(d)
    cal = s.get("calories", 0)
    prot = s.get("protein", 0)
    fat = s.get("fat", 0)
    carb = s.get("carbs", 0)
    water = s.get("water_ml", 0)
    print(f"{d} ({d.strftime('%A')}): {cal:.0f} kcal | P: {prot:.1f}g, F: {fat:.1f}g, C: {carb:.1f}g | Water: {water}ml")
