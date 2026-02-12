# Example Molecular Properties Dataset

This is a demonstration dataset showing the structure and format for uploading molecular property data to Lighthouse.

## Contents

- `data.csv` - Molecular properties in CSV format
- `metadata.yaml` - Dataset metadata and provenance information

## Data Format

The CSV file contains the following columns:
- **smiles**: Molecular structure in SMILES notation
- **molecular_weight**: Molecular weight in g/mol
- **logp**: Logarithm of partition coefficient (octanol-water)
- **h_bond_donors**: Number of hydrogen bond donors
- **h_bond_acceptors**: Number of hydrogen bond acceptors
- **name**: Common name of the molecule

## Usage

This dataset can be used for:
- Demonstrating property prediction models
- Training simple regression models
- Testing data processing pipelines

## Validation

To validate this dataset, run:
```bash
python validate_training_files.py chemistry chemistry/training/datasets/example-molecular-properties/metadata.yaml
```
