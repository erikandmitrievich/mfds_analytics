import os
import requests
import pandas as pd
import sys

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

    # 3. Process New Data
    new_df = pd.DataFrame(data)
    new_df['timestamp'] = pd.to_datetime(new_df['timestamp'])

    # 4. Load & Merge with Existing History
    file_path = f"traffic/{filename}"

    if os.path.exists(file_path):
        print(f"Found existing {filename}, merging...")
        try:
            old_df = pd.read_csv(file_path)

            # Fix column name compatibility (if moving from old action)
            if 'date' in old_df.columns:
                old_df = old_df.rename(columns={'date': 'timestamp'})

            old_df['timestamp'] = pd.to_datetime(old_df['timestamp'])

            # MERGE LOGIC:
            # 1. Stack old and new data
            combined = pd.concat([old_df, new_df])
            # 2. If 'Today' exists in both, keep the 'new' one (latest count)
            combined = combined.drop_duplicates(subset=['timestamp'], keep='last')
            # 3. Sort chronologically
            combined = combined.sort_values(by='timestamp')

        except Exception as e:
            print(f"CRITICAL ERROR reading {filename}: {e}")
            print("Stopping to prevent data loss.")
            sys.exit(1)
    else:
        print(f"No existing {filename} found. Creating new one.")
        combined = new_df

    # 5. Save safely
    combined.to_csv(file_path, index=False)
    print(f"Successfully updated {filename}. Total records: {len(combined)}")

if __name__ == "__main__":
    # Update Views
    update_traffic_data('views', 'views.csv')
    # Update Clones (Optional, but good to have)
    update_traffic_data('clones', 'clones.csv')
