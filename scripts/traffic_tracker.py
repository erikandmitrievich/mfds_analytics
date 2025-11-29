import os
import requests
import pandas as pd
import sys
from datetime import datetime

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

    # 3. Prepare the New Record (The "Hourly" Snapshot)
    # We only care about the latest data point (Today's current status)
    # The API returns a list; the last one is the most current day.
    latest_record = data[-1]

    new_df = pd.DataFrame([latest_record])

    # RENAME GitHub's timestamp to 'github_timestamp' to avoid confusion
    new_df = new_df.rename(columns={'timestamp': 'github_timestamp'})
    new_df['github_timestamp'] = pd.to_datetime(new_df['github_timestamp'])

    # ADD 'recorded_at': This captures the actual Hour/Minute the script ran
    new_df['recorded_at'] = datetime.now()

    # Reorder columns for readability
    cols = ['recorded_at', 'github_timestamp', 'count', 'uniques']
    new_df = new_df[cols]

    # 4. File Handling
    file_path = f"traffic/{filename}"

    if os.path.exists(file_path):
        # --- ONE-TIME MIGRATION CHECK ---
        # We need to peek at the file to see if it supports the new format
        try:
            # Read just the header
            existing_header = pd.read_csv(file_path, nrows=0).columns.tolist()

            if 'recorded_at' not in existing_header:
                print(f"Old CSV format detected in {filename}. Migrating database once...")
                # Read full file
                old_df = pd.read_csv(file_path)

                # Rename old 'timestamp' or 'date' to 'github_timestamp'
                if 'date' in old_df.columns:
                    old_df.rename(columns={'date': 'github_timestamp'}, inplace=True)
                elif 'timestamp' in old_df.columns:
                    old_df.rename(columns={'timestamp': 'github_timestamp'}, inplace=True)

                # Backfill 'recorded_at' with the github timestamp (best guess for old data)
                old_df['recorded_at'] = pd.to_datetime(old_df['github_timestamp'])

                # Save the converted file (Rewriting ONLY happened here for migration)
                old_df.to_csv(file_path, index=False)
                print("Migration complete.")

            # --- APPEND NEW DATA ---
            # mode='a' adds to the end. header=False prevents writing column names again.
            new_df.to_csv(file_path, mode='a', header=False, index=False)
            print(f"Appended hourly update to {filename}.")

        except Exception as e:
            print(f"Error updating {filename}: {e}")
    else:
        # File doesn't exist, create new file with headers
        print(f"Creating new file: {filename}")
        new_df.to_csv(file_path, index=False)

if __name__ == "__main__":
    # Update Views
    update_traffic_data('views', 'views.csv')
    # Update Clones
    update_traffic_data('clones', 'clones.csv')
