# Sprite Decompose — vendored dependency

This directory contains the source code from **Fast Sprite Decomposition from Animated Graphics (ECCV 2024)** by CyberAgent AI Lab.

The repository is vendored here because the ABBA pipeline depends on its FSD implementation. Example datasets, generated outputs, demo assets, and sample-only configuration files are intentionally omitted.

See [Original Project](https://github.com/CyberAgentAILab/sprite-decompose) or [Read Paper](https://arxiv.org/abs/2408.03923)

## Usage

Install the bundled package from `fsd`:

```bash
pip install -e fsd
```

The retained `scripts/optimize.sh` is the upstream optimization entry point. Project-specific inputs and generated outputs belong outside this vendor directory.

## License

See `LICENSE` for the original project's license.

