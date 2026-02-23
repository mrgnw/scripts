#!/usr/bin/env python3
# /// script
# dependencies = ["boto3", "requests"]
# ///

"""
Cloudflare R2 Billing Debug Tool
Helps investigate unexpected R2 charges by analyzing bucket contents and storage classes.
"""

import boto3
import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Any

def get_r2_client():
	"""Create R2 client using environment variables."""
	access_key = os.getenv('CLOUDFLARE_ACCESS_KEY_ID')
	secret_key = os.getenv('CLOUDFLARE_SECRET_ACCESS_KEY')
	account_id = os.getenv('CLOUDFLARE_ACCOUNT_ID')
	
	if not all([access_key, secret_key, account_id]):
		print("Missing required environment variables:")
		print("- CLOUDFLARE_ACCESS_KEY_ID")
		print("- CLOUDFLARE_SECRET_ACCESS_KEY")
		print("- CLOUDFLARE_ACCOUNT_ID")
		sys.exit(1)
	
	return boto3.client(
		's3',
		endpoint_url=f'https://{account_id}.r2.cloudflarestorage.com',
		aws_access_key_id=access_key,
		aws_secret_access_key=secret_key,
		region_name='auto'
	)

def analyze_bucket_storage(client, bucket_name: str) -> Dict[str, Any]:
	"""Analyze storage usage and classes in a bucket."""
	try:
		print(f"\n🔍 Analyzing bucket: {bucket_name}")
		
		# Get bucket metadata
		try:
			bucket_info = client.head_bucket(Bucket=bucket_name)
			print(f"✓ Bucket exists and accessible")
		except Exception as e:
			print(f"✗ Cannot access bucket: {e}")
			return {}
		
		# List all objects
		objects = []
		total_size = 0
		storage_classes = {}
		
		paginator = client.get_paginator('list_objects_v2')
		page_iterator = paginator.paginate(Bucket=bucket_name)
		
		for page in page_iterator:
			if 'Contents' in page:
				for obj in page['Contents']:
					objects.append(obj)
					size = obj['Size']
					total_size += size
					
					# Track storage classes
					storage_class = obj.get('StorageClass', 'STANDARD')
					if storage_class not in storage_classes:
						storage_classes[storage_class] = {'count': 0, 'size': 0}
					storage_classes[storage_class]['count'] += 1
					storage_classes[storage_class]['size'] += size
		
		print(f"📊 Objects: {len(objects):,}")
		print(f"📏 Total size: {total_size:,} bytes ({total_size / (1024**3):.3f} GB)")
		
		# Storage class breakdown
		print(f"\n📦 Storage Classes:")
		for storage_class, data in storage_classes.items():
			size_gb = data['size'] / (1024**3)
			print(f"  {storage_class}: {data['count']:,} objects, {size_gb:.3f} GB")
			
			# Calculate potential costs
			if storage_class == 'STANDARD':
				monthly_cost = size_gb * 0.015  # $0.015 per GB-month
				print(f"    Estimated monthly storage cost: ${monthly_cost:.3f}")
			elif storage_class in ['INFREQUENT_ACCESS', 'IA']:
				monthly_cost = size_gb * 0.01  # $0.01 per GB-month
				print(f"    Estimated monthly storage cost: ${monthly_cost:.3f}")
				print(f"    ⚠️  IA storage has higher operation costs!")
		
		# Look for large objects that might have used multipart uploads
		large_objects = [obj for obj in objects if obj['Size'] > 100 * 1024 * 1024]  # > 100MB
		if large_objects:
			print(f"\n📁 Large objects (>100MB) that likely used multipart uploads:")
			for obj in large_objects:
				size_mb = obj['Size'] / (1024**2)
				print(f"  {obj['Key']}: {size_mb:.1f} MB")
				# Estimate multipart operations (rough calculation)
				parts = max(1, obj['Size'] // (100 * 1024 * 1024))
				print(f"    Estimated multipart operations: ~{parts}")
		
		# Check for recently modified objects
		recent_objects = []
		for obj in objects:
			days_old = (datetime.now(timezone.utc) - obj['LastModified']).days
			if days_old <= 30:  # Objects modified in last 30 days
				recent_objects.append((obj, days_old))
		
		if recent_objects:
			print(f"\n🕒 Recently modified objects (last 30 days):")
			for obj, days_old in sorted(recent_objects, key=lambda x: x[1]):
				size_mb = obj['Size'] / (1024**2)
				print(f"  {obj['Key']}: {size_mb:.1f} MB ({days_old} days ago)")
		
		return {
			'bucket_name': bucket_name,
			'object_count': len(objects),
			'total_size_gb': total_size / (1024**3),
			'storage_classes': storage_classes,
			'large_objects': len(large_objects),
			'recent_objects': len(recent_objects)
		}
		
	except Exception as e:
		print(f"✗ Error analyzing bucket {bucket_name}: {e}")
		return {}

def estimate_operation_costs(bucket_data: Dict[str, Any]) -> None:
	"""Estimate potential operation costs based on bucket analysis."""
	print(f"\n💰 Potential Operation Cost Analysis:")
	
	object_count = bucket_data.get('object_count', 0)
	large_objects = bucket_data.get('large_objects', 0)
	
	# Estimate Class A operations (uploads, copies, etc.)
	# Each object = at least 1 upload operation
	# Large objects might use multipart = multiple operations
	estimated_class_a = object_count + (large_objects * 5)  # Rough estimate
	
	print(f"📤 Estimated Class A operations: {estimated_class_a:,}")
	if estimated_class_a > 1000000:  # Over free tier
		cost = (estimated_class_a - 1000000) * 4.50 / 1000000
		print(f"   Cost above free tier: ${cost:.2f}")
	
	# Check for storage classes that have higher operation costs
	storage_classes = bucket_data.get('storage_classes', {})
	for storage_class, data in storage_classes.items():
		if storage_class in ['INFREQUENT_ACCESS', 'IA']:
			ia_operations = data['count']
			if ia_operations > 0:
				cost = ia_operations * 9.00 / 1000000  # $9 per million for IA
				print(f"   ⚠️  IA Class A operations: {ia_operations:,} (${cost:.2f})")

def main():
	if len(sys.argv) > 1:
		bucket_name = sys.argv[1]
		target_buckets = [bucket_name]
	else:
		target_buckets = None
	
	client = get_r2_client()
	
	print("🔍 Cloudflare R2 Billing Debug Tool")
	print("=" * 50)
	
	# List all buckets
	try:
		response = client.list_buckets()
		buckets = response.get('Buckets', [])
		print(f"📦 Found {len(buckets)} buckets")
		
		if target_buckets:
			buckets = [b for b in buckets if b['Name'] in target_buckets]
			if not buckets:
				print(f"❌ Bucket '{target_buckets[0]}' not found")
				return
	except Exception as e:
		print(f"❌ Error listing buckets: {e}")
		return
	
	# Analyze each bucket
	total_analysis = {
		'total_objects': 0,
		'total_size_gb': 0,
		'buckets_with_ia': 0,
		'total_large_objects': 0
	}
	
	for bucket in buckets:
		bucket_data = analyze_bucket_storage(client, bucket['Name'])
		if bucket_data:
			total_analysis['total_objects'] += bucket_data.get('object_count', 0)
			total_analysis['total_size_gb'] += bucket_data.get('total_size_gb', 0)
			total_analysis['total_large_objects'] += bucket_data.get('large_objects', 0)
			
			# Check for IA storage
			storage_classes = bucket_data.get('storage_classes', {})
			if any(sc in ['INFREQUENT_ACCESS', 'IA'] for sc in storage_classes.keys()):
				total_analysis['buckets_with_ia'] += 1
			
			estimate_operation_costs(bucket_data)
			print("-" * 50)
	
	# Summary
	print(f"\n📋 SUMMARY:")
	print(f"Total objects across all buckets: {total_analysis['total_objects']:,}")
	print(f"Total storage: {total_analysis['total_size_gb']:.3f} GB")
	print(f"Large objects (likely multipart): {total_analysis['total_large_objects']:,}")
	print(f"Buckets with Infrequent Access storage: {total_analysis['buckets_with_ia']}")
	
	if total_analysis['buckets_with_ia'] > 0:
		print(f"\n⚠️  WARNING: Infrequent Access storage has much higher operation costs!")
		print(f"   Class A operations: $9.00 per million (vs $4.50 for Standard)")
	
	print(f"\n💡 Tips to investigate $9 charge:")
	print(f"1. Check Cloudflare dashboard billing section for detailed breakdown")
	print(f"2. Look for large file uploads that used multipart (many Class A ops)")
	print(f"3. Check if any storage accidentally used Infrequent Access class")
	print(f"4. Verify if you performed many list/copy operations")

if __name__ == "__main__":
	main()
