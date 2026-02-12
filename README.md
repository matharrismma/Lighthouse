# Lighthouse

This repository contains various resources and frameworks related to different topics including chemistry.

## Training Files

Lighthouse now supports uploading and managing training files for machine learning and computational research across multiple disciplines:

- **Chemistry**: Molecular structures, reaction data, spectroscopy, thermodynamic properties
- **Mathematics**: Problem sets, solutions, proofs, numerical data
- **Computer Science**: Code samples, algorithms, benchmarks, datasets

### Quick Start

To upload training files:

1. Review the subject-specific schema in `/[subject]/schema/training_schema.yaml`
2. Prepare your data according to the supported formats
3. Create a metadata file (see templates in subject training directories)
4. Submit a pull request

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines on contributing training files.

### Training Directory Structure

```
[subject]/
  └── training/
      ├── datasets/    # Raw and processed datasets
      ├── models/      # Trained models and configurations
      └── README.md    # Subject-specific guidelines
```

## Subjects

- [Chemistry](chemistry/)
- [Computer Science](computer_science/)
- [Mathematics](mathematics/)
- [Physics](physics/)
- [Engineering](engineering/)
- [Statistics](statistics_canon_v1.0/)

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on contributing training files and other resources.