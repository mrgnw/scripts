#!/usr/bin/env -S uv run --script

# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "boto3",
# ]
# ///
"""
DynamoDB utilities for converting AWS DynamoDB JSON format to simple Python dictionaries.

Clean, Pythonic approach using recursion and type converters.
"""

from decimal import Decimal
from typing import Any, Dict, List, Union


def deserialize_dynamodb_value(value: Dict[str, Any]) -> Any:
	"""
	Convert a DynamoDB value to Python value using clean recursive approach.

	Args:
	    value: DynamoDB value like {"S": "hello"}, {"N": "42"}, {"L": [...]}

	Returns:
	    Native Python value
	"""
	if not isinstance(value, dict) or len(value) != 1:
		return value

	type_key, type_value = next(iter(value.items()))

	# Type converter mapping - much cleaner than if/elif chain
	converters = {
		"S": str,  # String
		"N": lambda x: int(x) if "." not in x else float(x),  # Number (smart int/float)
		"B": bytes,  # Binary
		"BOOL": bool,  # Boolean
		"NULL": lambda x: None,  # Null
		"SS": list,  # String Set
		"NS": lambda x: [int(n) if "." not in n else float(n) for n in x],  # Number Set
		"BS": list,  # Binary Set
		"L": lambda x: [deserialize_dynamodb_value(item) for item in x],  # List
		"M": lambda x: {k: deserialize_dynamodb_value(v) for k, v in x.items()},  # Map
	}

	converter = converters.get(type_key, lambda x: x)
	return converter(type_value)


def deserialize_dynamodb_item(item: Dict[str, Any]) -> Dict[str, Any]:
	"""
	Convert a DynamoDB item to a clean Python dict.

	Args:
	    item: DynamoDB item with typed attributes

	Returns:
	    Clean Python dict with native values
	"""
	return {key: deserialize_dynamodb_value(value) for key, value in item.items()}


def deserialize_dynamodb_response(response: Dict[str, Any]) -> List[Dict[str, Any]]:
	"""
	Convert a DynamoDB query/scan response to clean Python list of dicts.

	Args:
	    response: DynamoDB response like {"Items": [{"id": {"S": "value"}}], "Count": 1}

	Returns:
	    List of clean Python dicts like [{"id": "value"}]
	"""
	items = response.get("Items", [])
	return [deserialize_dynamodb_item(item) for item in items]


def deserialize_dynamodb_json(json_data: Union[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
	"""
	Convert DynamoDB JSON (string or dict) to clean Python list of dicts.

	Args:
	    json_data: JSON string or dict containing DynamoDB response

	Returns:
	    List of clean Python dicts
	"""
	import json

	if isinstance(json_data, str):
		try:
			response = json.loads(json_data)
		except json.JSONDecodeError as e:
			raise ValueError(f"Invalid JSON string: {e}")
	else:
		response = json_data

	return deserialize_dynamodb_response(response)


# Alternative: Use boto3's built-in deserializer (if boto3 is available)
def deserialize_with_boto3(response: Dict[str, Any]) -> List[Dict[str, Any]]:
	"""
	Use boto3's built-in TypeDeserializer for the most accurate conversion.
	This is the "official" way but requires boto3 dependency.
	"""
	try:
		from boto3.dynamodb.types import TypeDeserializer

		deserializer = TypeDeserializer()
		items = response.get("Items", [])
		return [{k: deserializer.deserialize(v) for k, v in item.items()} for item in items]

	except ImportError:
		# Fallback to our custom implementation
		return deserialize_dynamodb_response(response)


def main():
	"""CLI interface for converting DynamoDB JSON files to clean format."""
	import argparse
	import json
	import sys
	from pathlib import Path

	parser = argparse.ArgumentParser(description="Convert DynamoDB JSON format to clean Python dictionaries")
	parser.add_argument("file", help="Path to DynamoDB JSON file to convert")
	parser.add_argument(
		"--use-boto3",
		action="store_true",
		help="Use boto3's TypeDeserializer instead of custom implementation",
	)

	args = parser.parse_args()

	# Check if file exists
	file_path = Path(args.file)
	if not file_path.exists():
		print(f"Error: File '{args.file}' not found", file=sys.stderr)
		sys.exit(1)

	try:
		# Load the DynamoDB JSON file
		with open(file_path, "r") as f:
			raw_data = f.read()

		# Convert to clean format
		if args.use_boto3:
			# Parse JSON first, then use boto3
			response = json.loads(raw_data)
			clean_data = deserialize_with_boto3(response)
		else:
			# Use our custom implementation
			clean_data = deserialize_dynamodb_json(raw_data)

		# Output clean JSON
		print(json.dumps(clean_data, indent=2, default=str))

	except json.JSONDecodeError as e:
		print(f"Error: Invalid JSON in file '{args.file}': {e}", file=sys.stderr)
		sys.exit(1)
	except Exception as e:
		print(f"Error processing file '{args.file}': {e}", file=sys.stderr)
		sys.exit(1)


if __name__ == "__main__":
	main()
