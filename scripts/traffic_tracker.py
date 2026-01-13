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
    # Endpoints:
    #   .../traffic/views -> returns { "views": [ {timestamp, count, uniques}, ... ] }
    #   .../traffic/clones -> returns { "clones": [ {timestamp, count, uniques}, ... ] }
    url = f"https://api.github.com/repos/{REPO}/traffic/{metric_type}"
    response = requests.get(url, headers=HEADERS)

    if response.status_code != 200:
        print(f"Error fetching data: {response.text}")
        return

    # Dynamic key access: 'views' or 'clones' matches metric_type
    data = response.json().get(metric_type, [])

    if not data:
        print(f"No {metric_type} data returned from GitHub.")
        return

    # 3. Get Current API State (The Cumulative Total for Today)
    latest_record = data[-1]

    # Normalize timestamp to string for consistent CSV comparison
    current_target_date = pd.to_datetime(latest_record['timestamp']).strftime('%Y-%m-%d %H:%M:%S+00:00')
    current_count = latest_record['count']
    current_uniques = latest_record['uniques']

    # 4. Read Previous State from File to Calculate Deltas
    previous_count = 0
    previous_uniques = 0

    file_path = f"traffic/{filename}"

    if os.path.exists(file_path):
        try:
            df_existing = pd.read_csv(file_path)
            if not df_existing.empty:
                # Filter rows that belong to the SAME target date (Today)
                # Since we are storing deltas, we must SUM all previous entries for today
                # to know how much traffic we have already accounted for.
                today_rows = df_existing[df_existing['target_date'] == current_target_date]

                if not today_rows.empty:
                    previous_count = today_rows['count'].sum()
                    previous_uniques = today_rows['uniques'].sum()

        except Exception as e:
            print(f"Warning: Could not read existing file for delta calculation: {e}")

    # 5. Calculate Deltas
    # (Total from API) - (Sum of parts already saved) = New Traffic since last run
    delta_count = current_count - previous_count
    delta_uniques = current_uniques - previous_uniques

    # Sanity check: prevent negative numbers if GitHub adjusts totals downwards (e.g. removing bots)
    if delta_count < 0: delta_count = 0
    if delta_uniques < 0: delta_uniques = 0

    print(f"[{metric_type}] API Total: {current_count} | Saved Today: {previous_count} | Delta: {delta_count}")

    # 6. Create Row
    new_row = {
        'recorded_at': datetime.now(timezone.utc),
        'target_date': current_target_date,
        'count': delta_count,
        'uniques': delta_uniques
    }

    # Optional: Skip writing if there is 0 new activity to save disk space
    if delta_count == 0 and delta_uniques == 0:
        print(f"No new {metric_type} for {current_target_date}. Skipping write.")
        return

    # 7. Write to File
    new_df = pd.DataFrame([new_row])
    new_df = new_df[['recorded_at', 'target_date', 'count', 'uniques']] # Ensure order

    # Add header only if file didn't exist
    header_needed = not os.path.exists(file_path)

    try:
        new_df.to_csv(file_path, mode='a', header=header_needed, index=False)
        print(f"Successfully saved delta to {filename}")
    except Exception as e:
        print(f"Error writing to file: {e}")

if __name__ == "__main__":
    # Ensure env vars are set: TARGET_REPO and TRAFFIC_TOKEN
    update_traffic_data('views', 'views.csv')
    update_traffic_data('clones', 'clones.csv')
