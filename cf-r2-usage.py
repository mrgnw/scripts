#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "python-dotenv",
#     "requests",
# ]
# ///
# Usage:
#   CLOUDFLARE_ACCOUNT_ID=xxx CLOUDFLARE_API_TOKEN=xxx uv run cf-r2-usage.py [bucket_name]
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

def try_s3_api():
	"""Try using S3-compatible API to get bucket info"""
	try:
		# Try to get bucket location/info via S3 API
		s3_url = f"https://{account_id}.r2.cloudflarestorage.com"
		headers = {"Authorization": f"Bearer {api_token}"}
		
		print(f"Trying S3 API: {s3_url}")
		resp = requests.get(s3_url, headers=headers)
		print(f"S3 API response: {resp.status_code}")
		if resp.status_code == 200:
			print(f"S3 API response body: {resp.text[:200]}")
		else:
			print(f"S3 API failed: {resp.text[:200]}")
	except Exception as e:
		print(f"S3 API error: {e}")

def try_rest_analytics():
	"""Try REST API analytics endpoints"""
	try:
		# Try different analytics endpoints
		endpoints = [
			f"accounts/{account_id}/r2/analytics",
			f"accounts/{account_id}/analytics/r2",
			f"accounts/{account_id}/analytics",
		]
		
		for endpoint in endpoints:
			url = f"https://api.cloudflare.com/client/v4/{endpoint}"
			headers = {"Authorization": f"Bearer {api_token}"}
			
			print(f"Trying REST endpoint: {url}")
			resp = requests.get(url, headers=headers)
			print(f"Status: {resp.status_code}")
			
			if resp.status_code == 200:
				data = resp.json()
				print(f"Success! Response: {json.dumps(data, indent=2)}")
				return data
			else:
				print(f"Failed: {resp.text[:200]}")
				
	except Exception as e:
		print(f"REST API error: {e}")
	
	return None


def build_query(variant: str) -> str:
	if variant == "introspect":
		return """
		query {
		  __schema {
		    types {
		      name
		      fields {
		        name
		        type { name }
		      }
		    }
		  }
		}
		"""
	elif variant == "simple":
		return f"""
		query {{
			viewer {{
				accounts(filter: {{ accountTag: \"{account_id}\" }}) {{
					r2StorageAdaptiveGroups(
						filter: {{ date_geq: \"{last_month_start}\", date_lt: \"{first_of_this_month}\" }}
						limit: 1000
					) {{
						dimensions {{ bucketName }}
					}}
					r2OperationsAdaptiveGroups(
						filter: {{ date_geq: \"{last_month_start}\", date_lt: \"{first_of_this_month}\" }}
						limit: 1000
					) {{
						dimensions {{ bucketName }}
					}}
				}}
			}}
		}}
		"""
	else:
		raise ValueError("Unknown variant")


def run_query(q: str) -> dict:
	r = requests.post(
		"https://api.cloudflare.com/client/v4/graphql",
		headers={"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"},
		json={"query": q},
	)
	r.raise_for_status()
	return r.json()


# Try a simple query first to see what data structure we get
print("Querying Cloudflare R2 analytics...")
data = run_query(build_query("simple"))
errs = data.get("errors")
if errs:
	print("Cloudflare GraphQL returned errors:")
	for err in errs:
		msg = err.get("message", "<no message>")
		path_seq = err.get("path") or []
		if not isinstance(path_seq, (list, tuple)):
			path_seq = [path_seq]
		path = ".".join(str(p) for p in path_seq if p is not None)
		code = (err.get("extensions") or {}).get("code")
		extra = []
		if path:
			extra.append(f"path: {path}")
		if code:
			extra.append(f"code: {code}")
		extra_str = f" ({'; '.join(extra)})" if extra else ""
		print(f"- {msg}{extra_str}")
	print("\nFalling back to REST API for usage data...")
	
	# Fallback to REST API for actual usage data
	try:
		# Get account analytics via REST API
		analytics_url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/analytics/stored"
		params = {
			"query": json.dumps({
				"dimensions": ["bucketName"],
				"metrics": ["objectSize", "objectCount", "requests"],
				"since": last_month_start.isoformat(),
				"until": first_of_this_month.isoformat()
			})
		}
		
		import json
				
		import json
		analytics_resp = requests.get(
			analytics_url,
			headers={"Authorization": f"Bearer {api_token}"},
			params=params
		)
		analytics_resp.raise_for_status()
		analytics_data = analytics_resp.json()
		
		if analytics_data.get("success"):
			result = analytics_data.get("result", {})
			storage = {}
			ops = {}
			
			for row in result.get("data", []):
				bucket = row.get("bucketName", "unknown")
				storage[bucket] = {
					"bytes": row.get("objectSize", 0),
					"objects": row.get("objectCount", 0)
				}
				ops[bucket] = row.get("requests", 0)
		else:
			print("REST API also failed, using GraphQL bucket list with zero values")
			# Continue with GraphQL fallback below
			data = None
	except Exception as e:
		print(f"REST API failed: {e}")
		print("Using GraphQL bucket list with zero values")
		data = None
		
if data is None:
	# REST API failed, continue with GraphQL minimal data
	data = run_query(build_query("simple"))

root = data.get("data") or {}
viewer = root.get("viewer") or {}
accounts = viewer.get("accounts") or []
if not accounts:
	print(
		"No accounts data returned. Verify CLOUDFLARE_ACCOUNT_ID and token permissions (Account Analytics: Read)."
	)
	# Optional debug dump of top-level keys
	print("Response keys:", list(root.keys()))
	sys.exit(1)

acct = accounts[0] or {}
storage_groups = acct.get("r2StorageAdaptiveGroups") or []
ops_groups = acct.get("r2OperationsAdaptiveGroups") or []

if not storage_groups and not ops_groups:
	print("No R2 usage data for the selected period. Check that R2 is in use and token has access.")
	# continue with empty dicts so we still print a header

# Since we can only get dimensions for now, create empty storage/ops dicts
storage = {}
ops = {}
buckets_from_storage = {(b.get("dimensions") or {}).get("bucketName") for b in storage_groups if (b.get("dimensions") or {}).get("bucketName")}
buckets_from_ops = {(o.get("dimensions") or {}).get("bucketName") for o in ops_groups if (o.get("dimensions") or {}).get("bucketName")}

# Initialize empty data for discovered buckets
for bucket in buckets_from_storage:
	storage[bucket] = {"bytes": 0, "objects": 0}

for bucket in buckets_from_ops:
	ops[bucket] = 0

print(f"Found {len(buckets_from_storage)} buckets with storage data, {len(buckets_from_ops)} with operations data")
print("Note: Actual usage numbers not available due to Cloudflare schema limitations")

all_buckets = sorted(set(storage.keys()) | set(ops.keys()))

# Determine column widths
bucket_width = max(len("bucket"), *(len(b) for b in all_buckets))
mb_width = len("MB")
objects_width = max(
	len("objects"), *(len(str(storage.get(b, {"objects": 0})["objects"])) for b in all_buckets)
)
requests_width = max(len("requests"), *(len(str(ops.get(b, 0))) for b in all_buckets))

# Print header
print(
	f"{'bucket':<{bucket_width}}\t{'MB':>{mb_width}}\t{'objects':>{objects_width}}\t{'requests':>{requests_width}}"
)

# Print rows
for bucket in all_buckets:
	s = storage.get(bucket, {"bytes": 0, "objects": 0})
	mb = s["bytes"] / (1024 * 1024)
	print(
		f"{bucket:<{bucket_width}}\t"
		f"{mb:>{mb_width}.1f}\t"
		f"{s['objects']:>{objects_width}}\t"
		f"{ops.get(bucket, 0):>{requests_width}}"
	)
