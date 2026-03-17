# Data is stored in Firebase Firestore.
# Collection layout (all data lives under users/{uid}):
#
#   users/{uid}                        – user profile (email, display_name, streak, longest_streak, created_at)
#   users/{uid}/habits/{habit_id}      – habits (name, category, target_minutes, created_at)
#   users/{uid}/activity_logs/{log_id} – activity log entries (habit_id, habit_name, minutes_spent, log_date)
#   users/{uid}/daily_summaries/{date} – per-day summary (document ID = YYYY-MM-DD)
#   users/{uid}/notes/{date}           – daily notes    (document ID = YYYY-MM-DD)