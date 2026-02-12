# Contributing Training Files to Lighthouse

Thank you for your interest in contributing training files to the Lighthouse repository! This guide will help you upload training datasets and models to support machine learning and computational research across various disciplines.

## Overview

Lighthouse supports training files for the following subjects:
- **Chemistry** - Molecular data, reactions, spectroscopy, thermodynamics
- **Mathematics** - Problem sets, proofs, numerical data, computational results
- **Computer Science** - Code samples, algorithms, benchmarks, performance metrics

## Getting Started

### 1. Choose the Appropriate Subject Directory

Navigate to the relevant subject directory:
- `/chemistry/training/`
- `/mathematics/training/`
- `/computer_science/training/`

### 2. Review the Schema

Each subject has a training schema that defines:
- Supported data types
- Accepted file formats
- Required metadata fields
- Provenance requirements

Schema locations:
- Chemistry: `/chemistry/schema/training_schema.yaml`
- Mathematics: `/mathematics/schema/training_schema.yaml`
- Computer Science: `/computer_science/schema/training_schema.yaml`

## Upload Process

### Step 1: Prepare Your Data

Ensure your data meets these requirements:
- **Clean and validated**: Remove errors, inconsistencies, duplicates
- **Properly formatted**: Follow the accepted file formats for your subject
- **Well-documented**: Include clear descriptions of the data
- **Legally compliant**: Ensure you have rights to share the data

### Step 2: Create Metadata File

Create a `metadata.yaml` file alongside your training files:

```yaml
dataset_name: "Descriptive Name of Your Dataset"
author: "Your Name or Organization"
creation_date: "2026-02-12"
description: |
  A comprehensive description of the dataset including:
  - What the data represents
  - How it was collected
  - What it can be used for
  - Any limitations or considerations
source: "Original source, publication, or institution"
license: "MIT"  # Choose appropriate: MIT, Apache-2.0, CC-BY-4.0, etc.
version: "1.0"

provenance:
  data_source: "Describe where the data came from"
  collection_method: "Describe how the data was collected"
  validation_status: "Validated"  # or "Pending"
  last_updated: "2026-02-12"
```

### Step 3: Organize Files

Place your files in the appropriate subdirectory:

**For datasets:**
```
subject/training/datasets/
  └── your-dataset-name/
      ├── metadata.yaml
      ├── data.csv (or other format)
      └── README.md (optional, additional documentation)
```

**For models:**
```
subject/training/models/
  └── your-model-name/
      ├── metadata.yaml
      ├── model.pkl (or other format)
      ├── config.json
      └── README.md (optional, additional documentation)
```

### Step 4: Submit via Pull Request

1. **Fork the repository** (if you haven't already)
2. **Create a new branch**: `git checkout -b add-training-dataset-name`
3. **Add your files**: Place files in the appropriate directory
4. **Commit your changes**: 
   ```bash
   git add .
   git commit -m "Add [dataset/model name] training files for [subject]"
   ```
5. **Push to your fork**: `git push origin add-training-dataset-name`
6. **Create a Pull Request** with:
   - Clear title describing the contribution
   - Detailed description of the data/model
   - Reference to any related issues

## File Format Guidelines

### Chemistry
- **CSV**: Structured data (reactions, properties)
- **JSON**: Complex nested data structures
- **SDF/MOL2/PDB**: Molecular structure files

### Mathematics
- **CSV**: Numerical data, tabular results
- **JSON**: Structured problem sets, solutions
- **TEX**: LaTeX documents with proofs
- **IPYNB**: Jupyter notebooks with computations

### Computer Science
- **CSV**: Tabular datasets, benchmarks
- **JSON**: Structured data, configurations
- **PY/JS**: Code samples, implementations
- **PARQUET**: Large-scale datasets

## Best Practices

### Data Quality
- ✅ Remove duplicates and errors
- ✅ Normalize formats and units
- ✅ Include data validation checks
- ✅ Document any data preprocessing steps

### Documentation
- ✅ Provide clear, comprehensive descriptions
- ✅ Include usage examples
- ✅ Document data limitations
- ✅ Cite original sources

### Licensing
- ✅ Choose an appropriate open-source license
- ✅ Respect original data licenses
- ✅ Attribute sources properly
- ✅ Include license information in metadata

### File Organization
- ✅ Use descriptive file and directory names
- ✅ Keep related files together
- ✅ Include README for complex datasets
- ✅ Limit file sizes (< 100MB; use Git LFS for larger files)

## Large Files

For datasets larger than 100MB:
1. Consider using [Git LFS](https://git-lfs.github.com/)
2. Or provide download links in your metadata
3. Contact maintainers for alternative hosting

## Review Process

After submission, your contribution will be reviewed for:
- **Schema compliance**: Matches the subject's training schema
- **Data quality**: Clean, validated, and properly formatted
- **Documentation**: Complete metadata and clear descriptions
- **Licensing**: Appropriate license with proper attribution

## Questions?

If you have questions about contributing training files:
- Open an issue with the `question` label
- Review existing issues for similar questions
- Contact the repository maintainers

Thank you for contributing to Lighthouse!
