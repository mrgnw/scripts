#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "python-dotenv",
#     "requests",
# ]
# ///
# r2_single_bucket_usage.py
# Usage:
#   CLOUDFLARE_ACCOUNT_ID=xxx CLOUDFLARE_API_TOKEN=xxx uv run cf-r2-single-bucket.py [bucket_name]
#   Default bucket: meu

import os
import requests
import dotenv
import sys
import json

from datetime import date, timedelta

dotenv.load_dotenv()

# Get environment variables with better error handling
account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
api_token = os.environ.get("CLOUDFLARE_API_TOKEN")

if not account_id:
	print("Error: CLOUDFLARE_ACCOUNT_ID environment variable not set")
	sys.exit(1)

if not api_token:
	print("Error: CLOUDFLARE_API_TOKEN environment variable not set")
	sys.exit(1)

# Get bucket name from command line or default to 'meu'
bucket_name = sys.argv[1] if len(sys.argv) > 1 else "meu"
print(f"Getting analytics for bucket: {bucket_name}")

today = date.today()
first_of_this_month = today.replace(day=1)
last_month_end = first_of_this_month - timedelta(days=1)
last_month_start = last_month_end.replace(day=1)

print(f"Date range: {last_month_start} to {first_of_this_month}")

def try_analytics_engine_sql():
	"""Try Analytics Engine with SQL queries for R2 data"""
	queries_to_try = [
		# Basic R2 storage query
		f"SELECT * FROM r2_storage WHERE bucketName = '{bucket_name}' LIMIT 10",
		# Basic R2 operations query  
		f"SELECT * FROM r2_operations WHERE bucketName = '{bucket_name}' LIMIT 10",
		# Time-based query
		f"SELECT * FROM r2_storage WHERE bucketName = '{bucket_name}' AND timestamp >= '{last_month_start}' AND timestamp < '{first_of_this_month}' LIMIT 10",
	]
	
	for query in queries_to_try:
		try:
			url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/analytics_engine/sql"
			headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
			
			print(f"\nTrying SQL: {query}")
			resp = requests.post(url, headers=headers, json={"query": query})
			print(f"Status: {resp.status_code}")
			
			if resp.status_code == 200:
				data = resp.json()
				print(f"Success! Response: {json.dumps(data, indent=2)}")
				if data.get("result", {}).get("data"):
					return data
			else:
				try:
					error_data = resp.json()
					print(f"Error: {json.dumps(error_data, indent=2)}")
				except Exception:
					print(f"Error: {resp.text[:200]}")
		except Exception as e:
			print(f"SQL query error: {e}")
	
	return None
	"""Try Cloudflare Analytics API with various endpoints"""
	endpoints_to_try = [
		f"accounts/{account_id}/analytics_engine/sql",
		f"accounts/{account_id}/analytics",
		f"accounts/{account_id}/r2/analytics", 
		f"accounts/{account_id}/analytics/r2",
	]
	
	for endpoint in endpoints_to_try:
		url = f"https://api.cloudflare.com/client/v4/{endpoint}"
		headers = {"Authorization": f"Bearer {api_token}"}
		
		print(f"\nTrying: {url}")
		
		try:
			resp = requests.get(url, headers=headers)
			print(f"Status: {resp.status_code}")
			
			if resp.status_code == 200:
				data = resp.json()
				print(f"Success! Response: {json.dumps(data, indent=2)}")
				return data
			elif resp.status_code == 404:
				print("Endpoint not found")
			else:
				try:
					error_data = resp.json()
					print(f"Error response: {json.dumps(error_data, indent=2)}")
				except:
					print(f"Error response: {resp.text[:200]}")
		except Exception as e:
			print(f"Request failed: {e}")
	
	return None

def try_graphql_with_count():
	"""Try GraphQL with count aggregation"""
	query = f"""
	query {{
		viewer {{
			accounts(filter: {{ accountTag: \"{account_id}\" }}) {{
				r2StorageAdaptiveGroups(
					filter: {{ 
						date_geq: \"{last_month_start}\", 
						date_lt: \"{first_of_this_month}\",
						bucketName: \"{bucket_name}\"
					}}
					limit: 10
				) {{
					dimensions {{ bucketName }}
					count
				}}
				r2OperationsAdaptiveGroups(
					filter: {{ 
						date_geq: \"{last_month_start}\", 
						date_lt: \"{first_of_this_month}\",
						bucketName: \"{bucket_name}\"
					}}
					limit: 10
				) {{
					dimensions {{ bucketName }}
					count
				}}
			}}
		}}
	}}
	"""
	
	try:
		resp = requests.post(
			"https://api.cloudflare.com/client/v4/graphql",
			headers={"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"},
			json={"query": query},
		)
		resp.raise_for_status()
		data = resp.json()
		
		if data.get("errors"):
			print(f"GraphQL errors: {json.dumps(data['errors'], indent=2)}")
			return None
		
		print(f"GraphQL response: {json.dumps(data, indent=2)}")
		return data
		
	except Exception as e:
		print(f"GraphQL error: {e}")
		return None

def try_r2_rest_api():
	"""Try R2-specific REST endpoints"""
	# Try to list buckets first
	try:
		url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/r2/buckets"
		headers = {"Authorization": f"Bearer {api_token}"}
		
		print(f"\nTrying R2 buckets list: {url}")
		resp = requests.get(url, headers=headers)
		print(f"Status: {resp.status_code}")
		
		if resp.status_code == 200:
			data = resp.json()
			print(f"Buckets list: {json.dumps(data, indent=2)}")
			
			# If we can list buckets, try to get specific bucket info
			bucket_url = f"{url}/{bucket_name}"
			print(f"\nTrying specific bucket: {bucket_url}")
			bucket_resp = requests.get(bucket_url, headers=headers)
			print(f"Bucket status: {bucket_resp.status_code}")
			
			if bucket_resp.status_code == 200:
				bucket_data = bucket_resp.json()
				print(f"Bucket data: {json.dumps(bucket_data, indent=2)}")
				return bucket_data
			else:
				try:
					error_data = bucket_resp.json()
					print(f"Bucket error: {json.dumps(error_data, indent=2)}")
				except:
					print(f"Bucket error: {bucket_resp.text[:200]}")
			
			return data
		else:
			try:
				error_data = resp.json()
				print(f"Error: {json.dumps(error_data, indent=2)}")
			except:
				print(f"Error: {resp.text[:200]}")
				
	except Exception as e:
		print(f"R2 REST API error: {e}")
	
	return None

# Try all approaches
print("=== Trying Analytics Engine SQL ===")
sql_result = try_analytics_engine_sql()

print("\n=== Trying R2 REST API ===")
r2_result = try_r2_rest_api()

print("\n=== Trying GraphQL with Count ===")
graphql_result = try_graphql_with_count()

print(f"\n=== Summary for bucket '{bucket_name}' ===")
if sql_result or r2_result or graphql_result:
	print("Got some data! Check the output above for details.")
else:
	print("No usage data available through the APIs we tried.")
	print("This might be due to:")
	print("- Token permissions (need 'Account Analytics: Read' and 'R2: Read')")
	print("- API endpoints not available for your account type")
	print("- Bucket name doesn't exist or has no activity in the time period")
