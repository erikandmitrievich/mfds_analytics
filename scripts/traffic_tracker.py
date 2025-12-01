import os
import requests
import pandas as pd
import sys
from datetime import datetime, timezone

def update_traffic_data(metric_type, filename):
    print(f"--- Processing {metric_type} ---")

    # 1. Configuration
    try:
        REPO = os.environ['TARGET_REPO']
        TOKEN = os.environ['TRAFFIC_TOKEN']
    except KeyError as e:
        print(f"Error: Missing environment variable {e}")
        sys.exit(1)

    HEADERS = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    # Ensure traffic folder exists
    if not os.path.exists('traffic'):
        os.makedirs('traffic')

    # 2. Fetch Data from GitHub API
    url = f"https://api.github.com/repos/{REPO}/traffic/{metric_type}"
    response = requests.get(url, headers=HEADERS)

    if response.status_code != 200:
        print(f"Error fetching data: {response.text}")
        return

    data = response.json().get(metric_type, [])
    if not data:
        print(f"No {metric_type} data returned from GitHub.")
        return

    # 3. Process the Latest Record from API
    # GitHub returns a list of days. We only care about the last one (Today/Latest).
    latest_record = data[-1]

    # FIX: Ensure we treat the GitHub timestamp as UTC explicitly
    current_github_ts = pd.to_datetime(latest_record['timestamp']).tz_convert(None) # Remove tz info for safe comparison

    current_total_count = latest_record['count']
    current_total_uniques = latest_record['uniques']

    # 4. Prepare File Path and Defaults
    file_path = f"traffic/{filename}"
    default_cols = ['recorded_at', 'github_timestamp', 'count', 'uniques']

    # Variables to hold what we have already saved for this specific github_timestamp
    accumulated_count = 0
    accumulated_uniques = 0

    # 5. Read Existing Data to Calculate Deltas
    if os.path.exists(file_path):
        try:
            # Load existing data
            df = pd.read_csv(file_path)

            # --- MIGRATION BLOCK (Legacy handling) ---
            migration_needed = False
            if 'recorded_at' not in df.columns:
                print(f"Migrating legacy format for {filename}...")
                # Normalize column names
                if 'date' in df.columns: df.rename(columns={'date': 'github_timestamp'}, inplace=True)
                elif 'timestamp' in df.columns: df.rename(columns={'timestamp': 'github_timestamp'}, inplace=True)
                # Backfill recorded_at
                df['recorded_at'] = pd.to_datetime(df['github_timestamp'])
                df = df[default_cols] # Reorder
                migration_needed = True

            # Ensure timestamps are datetime objects for comparison
            df['github_timestamp'] = pd.to_datetime(df['github_timestamp']).dt.tz_localize(None)

            # --- DELTA LOGIC START ---
            # Filter rows that match the CURRENT GitHub Timestamp (same day)
            # We need to know how many views we have ALREADY saved for this day
            same_day_data = df[df['github_timestamp'] == current_github_ts]

            if not same_day_data.empty:
                accumulated_count = same_day_data['count'].sum()
                accumulated_uniques = same_day_data['uniques'].sum()

            # If we migrated, save the fixed file now
            if migration_needed:
                df.to_csv(file_path, index=False)
                print("Migration complete.")

        except Exception as e:
            print(f"Error reading existing file for delta calculation: {e}")
            # If read fails, we assume 0 accumulation to avoid crashing,
            # though this might duplicate data in worst case.
            pass

    # 6. Calculate Hourly Delta
    # (Current Total from API) - (Sum of all previous hours recorded today)
    hourly_count = current_total_count - accumulated_count
    hourly_uniques = current_total_uniques - accumulated_uniques

    # Edge Case: If GitHub resets data or returns weird cache, don't save negative numbers
    if hourly_count < 0: hourly_count = 0
    if hourly_uniques < 0: hourly_uniques = 0

    print(f"API Total: {current_total_count} | Already Saved: {accumulated_count} | New Hourly Entry: {hourly_count}")

    # If there is no new activity, you might check here if you want to save a 0 row.
    # Current logic: Saves 0 rows to show continuity.

    # 7. Create the New Row
    new_row = {
        'github_timestamp': current_github_ts,
        'count': hourly_count,
        'uniques': hourly_uniques,
        'recorded_at': datetime.now(timezone.utc) # Explicit UTC for recording time
    }

    new_df = pd.DataFrame([new_row])
    new_df = new_df[default_cols]

    # 8. Append to File
    if os.path.exists(file_path):
        new_df.to_csv(file_path, mode='a', header=False, index=False)
    else:
        new_df.to_csv(file_path, index=False)

    print(f"Successfully saved update to {filename}")

if __name__ == "__main__":
    update_traffic_data('views', 'views.csv')
    update_traffic_data('clones', 'clones.csv')
