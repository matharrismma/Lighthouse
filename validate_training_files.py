#!/usr/bin/env python3
"""
Training File Validator for Lighthouse

This script validates training files and metadata before upload to ensure
they comply with the Lighthouse training schema requirements.

Usage:
    python validate_training_files.py <subject> <path_to_metadata.yaml>

Arguments:
    subject: One of [chemistry, mathematics, computer_science]
    path_to_metadata: Path to the metadata.yaml file for the training data
"""

import sys
import os
import yaml
from datetime import datetime
from pathlib import Path


VALID_SUBJECTS = ['chemistry', 'mathematics', 'computer_science']

REQUIRED_METADATA_FIELDS = [
    'dataset_name',
    'author',
    'creation_date',
    'description',
    'source',
    'license',
    'version'
]

REQUIRED_PROVENANCE_FIELDS = [
    'data_source',
    'collection_method',
    'validation_status',
    'last_updated'
]


def load_schema(subject):
    """Load the training schema for the specified subject."""
    schema_paths = {
        'chemistry': 'chemistry/schema/training_schema.yaml',
        'mathematics': 'mathematics/schema/training_schema.yaml',
        'computer_science': 'computer_science/training_schema.yaml'
    }
    
    schema_path = schema_paths.get(subject)
    if not schema_path or not os.path.exists(schema_path):
        print(f"❌ Error: Schema file not found for {subject}")
        return None
    
    with open(schema_path, 'r') as f:
        return yaml.safe_load(f)


def validate_metadata(metadata_path):
    """Validate the metadata file exists and is valid YAML."""
    if not os.path.exists(metadata_path):
        print(f"❌ Error: Metadata file not found at {metadata_path}")
        return None
    
    try:
        with open(metadata_path, 'r') as f:
            metadata = yaml.safe_load(f)
        return metadata
    except yaml.YAMLError as e:
        print(f"❌ Error: Invalid YAML in metadata file: {e}")
        return None


def check_required_fields(metadata):
    """Check that all required metadata fields are present."""
    errors = []
    
    # Check top-level required fields
    for field in REQUIRED_METADATA_FIELDS:
        if field not in metadata:
            errors.append(f"Missing required field: {field}")
        elif not metadata[field] or str(metadata[field]).strip() == '':
            errors.append(f"Field '{field}' is empty")
    
    # Check provenance section
    if 'provenance' not in metadata:
        errors.append("Missing required 'provenance' section")
    else:
        provenance = metadata['provenance']
        for field in REQUIRED_PROVENANCE_FIELDS:
            if field not in provenance:
                errors.append(f"Missing required provenance field: {field}")
            elif not provenance[field] or str(provenance[field]).strip() == '':
                errors.append(f"Provenance field '{field}' is empty")
    
    return errors


def validate_file_formats(subject, metadata_path, schema):
    """Validate that data files have supported formats."""
    if not schema or 'file_formats' not in schema:
        return []
    
    allowed_formats = schema['file_formats']
    errors = []
    
    # Check files in the same directory as metadata
    metadata_dir = os.path.dirname(metadata_path)
    if not metadata_dir:
        metadata_dir = '.'
    
    # Exclude metadata and documentation files from format check
    excluded_files = ['metadata.yaml', 'README.md', 'LICENSE', 'CHANGELOG.md']
    data_files = [f for f in os.listdir(metadata_dir) 
                  if os.path.isfile(os.path.join(metadata_dir, f)) 
                  and f not in excluded_files and not f.startswith('.')]
    
    for file in data_files:
        ext = file.split('.')[-1].lower()
        if ext not in allowed_formats:
            errors.append(f"File '{file}' has unsupported format '.{ext}'. "
                        f"Allowed formats: {', '.join(allowed_formats)}")
    
    return errors


def validate_dates(metadata):
    """Validate that date fields are properly formatted."""
    errors = []
    date_fields = ['creation_date']
    
    if 'provenance' in metadata:
        date_fields.append('last_updated')
    
    for field in date_fields:
        if field == 'last_updated' and 'provenance' in metadata:
            date_value = metadata['provenance'].get(field)
        else:
            date_value = metadata.get(field)
        
        if date_value:
            try:
                datetime.strptime(str(date_value), '%Y-%m-%d')
            except ValueError:
                errors.append(f"Invalid date format for '{field}': {date_value}. "
                            "Expected format: YYYY-MM-DD")
    
    return errors


def main():
    if len(sys.argv) != 3:
        print("Usage: python validate_training_files.py <subject> <path_to_metadata.yaml>")
        print(f"Valid subjects: {', '.join(VALID_SUBJECTS)}")
        sys.exit(1)
    
    subject = sys.argv[1]
    metadata_path = sys.argv[2]
    
    print(f"\n🔍 Validating training files for {subject}...")
    print(f"📄 Metadata file: {metadata_path}\n")
    
    # Validate subject
    if subject not in VALID_SUBJECTS:
        print(f"❌ Error: Invalid subject '{subject}'")
        print(f"Valid subjects: {', '.join(VALID_SUBJECTS)}")
        sys.exit(1)
    
    # Load schema
    schema = load_schema(subject)
    if not schema:
        sys.exit(1)
    
    # Validate metadata file
    metadata = validate_metadata(metadata_path)
    if not metadata:
        sys.exit(1)
    
    print("✅ Metadata file is valid YAML")
    
    # Run validation checks
    all_errors = []
    
    # Check required fields
    errors = check_required_fields(metadata)
    if errors:
        all_errors.extend(errors)
    else:
        print("✅ All required metadata fields present")
    
    # Validate dates
    errors = validate_dates(metadata)
    if errors:
        all_errors.extend(errors)
    else:
        print("✅ Date fields properly formatted")
    
    # Validate file formats
    errors = validate_file_formats(subject, metadata_path, schema)
    if errors:
        all_errors.extend(errors)
    else:
        print("✅ File formats are supported")
    
    # Print results
    print("\n" + "="*60)
    if all_errors:
        print("❌ VALIDATION FAILED\n")
        print("Errors found:")
        for i, error in enumerate(all_errors, 1):
            print(f"  {i}. {error}")
        print("\nPlease fix these errors before uploading.")
        sys.exit(1)
    else:
        print("✅ VALIDATION PASSED")
        print("\nYour training files are ready to upload!")
        print("Next steps:")
        print("  1. Commit your changes")
        print("  2. Push to your fork")
        print("  3. Create a pull request")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
