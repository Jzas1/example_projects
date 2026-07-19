import boto3
import pandas as pd
import io
import os
import smtplib
from email.mime.text import MIMEText
from google.cloud import bigquery
from google.oauth2 import service_account

credentials = service_account.Credentials.from_service_account_file(
	'service_account.json'
)

GMAIL_USER = os.environ['GMAIL_USER']
GMAIL_APP_PASSWORD = os.environ['GMAIL_APP_PASSWORD']

def send_email(subject, body):
	msg = MIMEText(body)
	msg['Subject'] = subject
	msg['From'] = GMAIL_USER
	msg['To'] = GMAIL_USER
	with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
		server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
		server.send_message(msg)

try:
	s3 = boto3.client('s3')
	files = s3.list_objects_v2(Bucket='viant', Prefix='exports')
	x = sorted(files['Contents'], key= lambda x: x['LastModified'], reverse=True)[0]
	file = s3.get_object(Bucket='viant', Key=x['Key'])
	df = pd.read_csv(io.BytesIO(file['Body'].read()), parse_dates=['date'])
	df_a = df[df['Attribution_Window'].notna()]
	df_s = df[df['Attribution_Window'].isna()]

	max_date_a = df_a['date'].max()
	min_date_a = df_a['date'].min()
	max_date_s = df_s['date'].max()
	min_date_s = df_s['date'].min()

	client = bigquery.Client(credentials=credentials, project='my-gcp-project')
	job_config = bigquery.LoadJobConfig(autodetect=True, write_disposition='WRITE_TRUNCATE')

	job = client.load_table_from_dataframe(df_a, 'my-gcp-project.test.staging_attribution', job_config=job_config)
	job.result()

	promote_a = f"""
	BEGIN TRANSACTION;

	DELETE FROM `my-gcp-project.test.viant_attribution`
	WHERE date BETWEEN '{min_date_a}' AND '{max_date_a}';

	INSERT INTO `my-gcp-project.test.viant_attribution`
	SELECT * FROM `my-gcp-project.test.staging_attribution`;

	COMMIT TRANSACTION;
	"""
	job = client.query(promote_a)
	job.result()
	print(f'rows appended for {min_date_a} to {max_date_a}')


	#spend table
	job = client.load_table_from_dataframe(df_s, 'my-gcp-project.test.staging_spend', job_config=job_config)
	job.result()

	promote_s = f"""
	BEGIN TRANSACTION;

	DELETE FROM `my-gcp-project.test.viant_spend`
	WHERE date BETWEEN '{min_date_s}' AND '{max_date_s}';

	INSERT INTO `my-gcp-project.test.viant_spend`
	SELECT * FROM `my-gcp-project.test.staging_spend`;

	COMMIT TRANSACTION;
	"""
	job = client.query(promote_s)
	job.result()
	print(f'spend rows for {min_date_s} to {max_date_s}')
	send_email('viant load success', f'attribution {min_date_a} to {max_date_a}, spend {min_date_s} to {max_date_s}')
except Exception as e:
	send_email('viant load FAILED', str(e))
	raise

result = (client.query(f"""
                   SELECT Advertiser_Name,
                   SUM(spend) as total_spend,
                   FROM`my-gcp-project.test.viant_spend`
                   GROUP BY Advertiser_Name

             """

)).result()
for row in result:
    print(row.Advertiser_Name, row.total_spend)
