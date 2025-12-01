import os
import requests
import pandas as pd
import sys
from datetime import datetime, timezone

def update_traffic_data(metric_type, filename):
    print(f"--- Processing {metric_type} ---")

    # 1. Setup
    try:
        REPO = os.environ['TARGET_REPO']
        TOKEN = os.environ['TRAFFIC_TOKEN']
    except KeyError as e:
        print(f"Error: Missing environment variable {e}")
        sys.exit(1)

    HEADERS = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github.v3+json"}
    if not os.path.exists('traffic'): os.makedirs('traffic')
    file_path = f"traffic/{filename}"

    # 2. Fetch Data
    url = f"https://api.github.com/repos/{REPO}/traffic/{metric_type}"
    response = requests.get(url, headers=HEADERS)
    data = response.json().get(metric_type, [])

    if not data: return

    # 3. Get Current API State (The Cumulative Total for Today)
    latest_record = data[-1]
    current_target_date = pd.to_datetime(latest_record['timestamp']).strftime('%Y-%m-%d %H:%M:%S+00:00')
    current_count = latest_record['count']
    current_uniques = latest_record['uniques']

    # 4. Read Previous State from File (Crucial for Delta Calc)
    previous_count = 0
    previous_uniques = 0
    is_same_day = False

    if os.path.exists(file_path):
        try:
            # efficient way to read just the last few lines or the whole file
            df_existing = pd.read_csv(file_path)
            if not df_existing.empty:
                last_row = df_existing.iloc[-1]

                # Check if the last row in CSV belongs to the SAME target date as today
                if last_row['target_date'] == current_target_date:
                    is_same_day = True
                    previous_count = last_row['count'] # In your file, this needs to be the CUMULATIVE count if you want to calc delta correctly

                    # WAIT! If your file stores DELTAS, you cannot simply subtract from the last row.
                    # You would need to sum ALL rows for the current day to get the "Previous Total".
                    # To keep it simple: This logic below assumes we are converting Cumulative -> Delta for storage.

                    # To find the total accumulated SO FAR today, we filter the DF:
                    today_rows = df_existing[df_existing['target_date'] == current_target_date]
                    previous_count = today_rows['count'].sum()
                    previous_uniques = today_rows['uniques'].sum()

        except Exception as e:
            print(f"Warning: Could not read existing file: {e}")

    # 5. Calculate Deltas
    # If it's the same day, subtract what we already saved.
    # If it's a new day (is_same_day is False), previous_count is 0, so we save the full amount.

    delta_count = current_count - previous_count
    delta_uniques = current_uniques - previous_uniques

    # Sanity check: GitHub sometimes reduces counts (bot removal). Prevent negative numbers.
    if delta_count < 0: delta_count = 0
    if delta_uniques < 0: delta_uniques = 0

    # 6. Create Row
    new_row = {
        'recorded_at': datetime.now(timezone.utc),
        'target_date': current_target_date,
        'count': delta_count,
        'uniques': delta_uniques
    }

    # Only save if there is new data (Optional, but cleaner for deltas)
    if delta_count == 0 and delta_uniques == 0:
        print(f"No new traffic for {current_target_date}. Skipping write.")
        return

    # 7. Write
    new_df = pd.DataFrame([new_row])
    # Ensure correct column order
    new_df = new_df[['recorded_at', 'target_date', 'count', 'uniques']]

    # Check if header is needed
    header_needed = not os.path.exists(file_path)
    new_df.to_csv(file_path, mode='a', header=header_needed, index=False)
    print(f"Saved delta: +{delta_count} views")

if __name__ == "__main__":
    update_traffic_data('views', 'views_v02.csv')
    update_traffic_data('clones', 'clones_v02.csv')
