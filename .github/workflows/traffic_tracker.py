import os
import requests
import pandas as pd
from datetime import datetime

def run_traffic_job():
    # 1. Configuration
    try:
        REPO = os.environ['TARGET_REPO']
        TOKEN = os.environ['TRAFFIC_TOKEN']
    except KeyError as e:
        print(f"Error: Missing environment variable {e}")
        exit(1)

    HEADERS = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    # Ensure traffic folder exists
    if not os.path.exists('traffic'):
        os.makedirs('traffic')

    # 2. Fetch Views Data from GitHub API
    url = f"https://api.github.com/repos/{REPO}/traffic/views"
    response = requests.get(url, headers=HEADERS)

    if response.status_code != 200:
        print(f"Error fetching data: {response.text}")
        return

    data = response.json().get('views', [])
    if not data:
        print("No traffic data returned from GitHub.")
        return

    # --- PART A: UPDATE DAILY HISTORY (views.csv) ---
    new_df = pd.DataFrame(data)
    new_df['timestamp'] = pd.to_datetime(new_df['timestamp'])

    file_path = "traffic/views.csv"
    if os.path.exists(file_path):
        try:
            old_df = pd.read_csv(file_path)
            # Compatibility fix for old data formats
            if 'date' in old_df.columns:
                old_df = old_df.rename(columns={'date': 'timestamp'})

            old_df['timestamp'] = pd.to_datetime(old_df['timestamp'])

            # Merge and Deduplicate
            combined = pd.concat([old_df, new_df])
            combined = combined.drop_duplicates(subset=['timestamp'], keep='last')
            combined = combined.sort_values(by='timestamp')
        except Exception as e:
            print(f"Error reading existing file: {e}. Starting fresh.")
            combined = new_df
    else:
        combined = new_df

    combined.to_csv(file_path, index=False)
    print("Successfully updated daily views.csv")

    # --- PART B: LOG HOURLY SNAPSHOT (hourly_raw.csv) ---
    # Get the count for 'Today' right now
    todays_data = data[-1]

    snapshot = {
        'execution_time': datetime.now().isoformat(),
        'github_day': todays_data['timestamp'],
        'count_so_far': todays_data['count'],
        'uniques_so_far': todays_data['uniques']
    }

    hourly_file = "traffic/hourly_raw.csv"
    hourly_df = pd.DataFrame([snapshot])

    # Append to the file (don't overwrite)
    if os.path.exists(hourly_file):
        hourly_df.to_csv(hourly_file, mode='a', header=False, index=False)
    else:
        hourly_df.to_csv(hourly_file, index=False)

    print(f"Logged hourly snapshot: {snapshot['count_so_far']} views so far today.")

if __name__ == "__main__":
    run_traffic_job()
