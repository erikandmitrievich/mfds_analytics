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

    # 3. Prepare the New Record
    latest_record = data[-1]
    new_df = pd.DataFrame([latest_record])

    # Rename and format
    new_df = new_df.rename(columns={'timestamp': 'github_timestamp'})
    new_df['github_timestamp'] = pd.to_datetime(new_df['github_timestamp'])
    new_df['recorded_at'] = datetime.now()

    # 4. File Handling
    file_path = f"traffic/{filename}"

    # Default preferred order (Used only for NEW files or during Migration)
    default_cols = ['recorded_at', 'github_timestamp', 'count', 'uniques']

    if os.path.exists(file_path):
        try:
            # CRITICAL FIX: Read the ACTUAL header from the file
            existing_header = pd.read_csv(file_path, nrows=0).columns.tolist()

            if 'recorded_at' in existing_header:
                # Case A: File is already migrated/correct.
                # WE MUST USE THE FILE'S COLUMN ORDER, NOT OUR OWN.
                cols = existing_header

                # Reorder new data to match existing file structure exactly
                new_df = new_df[cols]

                new_df.to_csv(file_path, mode='a', header=False, index=False)
                print(f"Appended hourly update to {filename} (Matched existing column order).")

            else:
                # Case B: Old Legacy File (Missing 'recorded_at'). Migration needed.
                print(f"Old CSV format detected in {filename}. Migrating database...")
                old_df = pd.read_csv(file_path)

                # Normalize old column names
                if 'date' in old_df.columns:
                    old_df.rename(columns={'date': 'github_timestamp'}, inplace=True)
                elif 'timestamp' in old_df.columns:
                    old_df.rename(columns={'timestamp': 'github_timestamp'}, inplace=True)

                # Create missing 'recorded_at' column (Backfill)
                old_df['recorded_at'] = pd.to_datetime(old_df['github_timestamp'])

                # Apply the NEW default order
                old_df = old_df[default_cols]

                # Overwrite file with corrected structure
                old_df.to_csv(file_path, index=False)
                print("Migration complete. Columns reordered.")

                # Append the new data using the default order
                new_df = new_df[default_cols]
                new_df.to_csv(file_path, mode='a', header=False, index=False)
                print(f"Appended current update to {filename}.")

        except Exception as e:
            print(f"Error updating {filename}: {e}")
            sys.exit(1)
    else:
        # Case C: New File. Create with default order.
        print(f"Creating new file: {filename}")
        new_df = new_df[default_cols]
        new_df.to_csv(file_path, index=False)

if __name__ == "__main__":
    update_traffic_data('views', 'views.csv')
    update_traffic_data('clones', 'clones.csv')
