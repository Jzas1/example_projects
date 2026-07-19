import requests
import io
import base64
from datetime import date, timedelta
import time
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

credentials = service_account.Credentials.from_service_account_file(
	'service_account.json'
)

base_url = 'https://papi.innovid.com/v3'
Username = 'user@example.com'
Password = 'fake_password'


creds =f'{Username}:{Password}'
b64 = base64.b64encode(creds.encode()).decode()
headers = {'Authorization': f'Basic {b64}'}

yesterday = date.today() - timedelta(days=1)

adv = requests.get(f"{base_url}/advertisers", headers=headers).json()
print(adv)

all_dfs = []

for a in adv['data']['clients']:
    for b in a['advertisers']:
        print(f"{b['name']}, {b['id']}, {a['id']}" )
        
        try:
            resp = requests.get(f"{base_url}/clients/{a['id']}/advertisers/{b['id']}/reports/delivery/dateFrom/{yesterday}/dateTo/{yesterday}", headers=headers).json()
            token = resp['data']['reportStatusToken']

            for attempt in range(30):
                status = requests.get(f'{base_url}/reports/{token}/status', headers=headers).json()
                if status['data']['reportStatus'] == 'READY':
                    df = pd.read_csv(status['data']['reportUrl'], compression='zip')
                    all_dfs.append(df)
                    break
                if status['data']['reportStatus'] == 'FAIL':
                    print(f"Report failed for {b['id']}")
                    break
                time.sleep(30)
        except Exception as e:
            print(e)

final_df = pd.concat(all_dfs, ignore_index=True)
try:
    client = bigquery.Client(credentials=credentials, project='my-gcp-project')
    delete = client.query(f"DELETE FROM `my-gcp-project.test.innovid` WHERE date = '{yesterday}'")
    delete.result()
    job_config = bigquery.LoadJobConfig(autodetect=True)
    job = client.load_table_from_dataframe(final_df, 'my-gcp-project.test.innovid', job_config=job_config)
    job.result()
    print(f"{job.output_rows} rows loaded ")
except Exception as e:
    print(f"failed:{e}")
result = (client.query(f"""
                   SELECT Advertiser_Name, 
                   SUM(spend) as total_spend
                   FROM `my-gcp-project.test.innovid` 
                   GROUP BY Advertiser_Name
             """

)).result()
for row in result:
    print(row.Advertiser_Name, row.total_spend)


