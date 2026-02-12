# Chemistry Training Files

This directory contains training datasets and models for chemistry-related machine learning and computational tasks.

## Directory Structure

- `datasets/` - Raw training data and processed datasets
- `models/` - Trained models and model configurations

## Uploading Training Files

### Prerequisites
- Ensure your data complies with the schema defined in `/chemistry/schema/training_schema.yaml`
- Include proper metadata for provenance tracking

### Supported File Formats
- CSV (Comma-separated values)
- JSON (JavaScript Object Notation)
- SDF (Structure-Data File)
- MOL2 (Tripos Mol2)
- PDB (Protein Data Bank)

### Upload Process

1. **Prepare your data**: Ensure data is clean, validated, and properly formatted
2. **Create metadata file**: Use `metadata.yaml` template (see example below)
3. **Place files in appropriate directory**:
   - Raw datasets → `datasets/`
   - Trained models → `models/`
4. **Submit via pull request** with clear description

### Metadata Template

Create a `metadata.yaml` file alongside your training files:

```yaml
dataset_name: "My Chemistry Dataset"
author: "Your Name"
creation_date: "2026-02-12"
description: "Description of the dataset and its purpose"
source: "Original source or institution"
license: "MIT" # or appropriate license
version: "1.0"

provenance:
  data_source: "Original data collection method"
  collection_method: "Experimental/Computational/Literature"
  validation_status: "Validated/Pending"
  last_updated: "2026-02-12"
```

## Examples of Training Data Types

- **Molecular Structures**: 3D coordinates, bond information
- **Reaction Data**: Reactants, products, conditions, yields
- **Spectroscopy Data**: NMR, IR, Mass spec data
- **Thermodynamic Properties**: Enthalpies, free energies, etc.

## Contact

For questions about uploading training files, please open an issue in this repository.
