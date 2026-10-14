export interface MealProduct {
  name: string;
  amount: number;
  calories: number;
  protein?: number;
  fat?: number;
  carbs?: number;
}

export interface MealCategory {
  title: string;
  calories: number;
  products: MealProduct[];
}

export interface NutritionData {
  calories: number;
  calories_goal: number;
  protein: number;
  protein_goal: number;
  carbs: number;
  fat: number;
  water_ml: number;
  meals: Record<string, MealCategory>;
}

export interface WorkoutExercise {
  title: string;
  sets_count: number;
  best_set?: string;
}

export interface NextRoutinePreview {
  routine_title: string;
  exercises: { title: string; target_sets: number; target_reps: string; last_weight: string }[];
}

export interface TodayWorkout {
  title: string;
  total_tonnage_kg: number;
  total_working_sets: number;
  date: string;
}

export interface WorkoutStatus {
  today_completed: boolean;
  today_workout?: TodayWorkout | null;
  next_routine?: NextRoutinePreview | null;
}

export interface WeightEntry {
  date: string;
  weight: number;
}

export interface UserProfile {
  current_weight: number;
  start_weight: number;
  goal_weight: number;
  weight_history: WeightEntry[];
}

export interface DashboardData {
  date: string;
  weekday: string;
  time: string;
  nutrition: NutritionData;
  workout: WorkoutStatus;
  profile: UserProfile;
}

export interface RoutineItem {
  id: string;
  title: string;
  exercises: { title: string; sets_count: number }[];
}

export interface AnalyzedWorkoutItem {
  title: string;
  date: string;
  total_tonnage_kg: number;
  total_working_sets: number;
}

export interface WorkoutsResponse {
  workouts: AnalyzedWorkoutItem[];
  routines: RoutineItem[];
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'coach';
  text: string;
  timestamp: string;
}

export interface WeeklyDayItem {
  date: string;
  weekday: string;
  calories: number;
  protein: number;
  fat: number;
  carbs: number;
}

export interface WeeklyResponse {
  report_markdown: string;
  days: WeeklyDayItem[];
  averages: {
    calories: number;
    protein: number;
    fat: number;
    carbs: number;
    tracked_days: number;
  };
}

export interface HabitItem {
  id: string;
  title: string;
  category: string;
  target_days: number;
  history: Record<string, boolean>;
  created_at: string;
  current_streak: number;
  record_streak: number;
}

export interface HabitsResponse {
  habits: HabitItem[];
  today_summary: string;
}

export interface BookItem {
  id: string;
  title: string;
  author: string;
  category: string;
  status: 'reading' | 'finished' | 'planned';
  current_page?: number;
  total_pages?: number;
  rating?: number;
  notes?: string;
  finished_date?: string;
  created_at: string;
}

export interface BooksResponse {
  books: BookItem[];
  stats: {
    total: number;
    finished: number;
    reading: number;
    planned: number;
    total_pages_read: number;
    library_total_pages?: number;
  };
}
