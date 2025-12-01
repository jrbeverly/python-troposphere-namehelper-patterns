# Examples

The scripts in this directory are runnable examples that use Troposphere to
emit complete CloudFormation templates as JSON.

## Running

Install the optional tooling first:

```bash
make setup
```

From the repository root:

```bash
PYTHONPATH=.python_packages:src python3 examples/minimal.py > minimal-template.json
PYTHONPATH=.python_packages:src python3 examples/template_generation.py > adapter-template.json
```

To pretty-print either template after generation:

```bash
python3 -m json.tool minimal-template.json
python3 -m json.tool adapter-template.json
```

## Example Catalog

### `minimal.py`

Uses the public `NameHelper` API directly to generate exact names for a small
Troposphere `Template` containing:

- an S3 bucket
- an IAM role
- an SSM parameter
- an API Gateway REST API

All names are rendered exactly at generation time. The Troposphere template
stores each `NameResult` in template `Metadata` so you can inspect the rendered
value, certainty, and findings alongside the CloudFormation resources.

### `template_generation.py`

Uses the `TemplateHelper` adapter, `from_context()`, and a Troposphere
`Template` to generate a more realistic stack from context. It produces:

- an IAM role named from region, stack, and service context
- an S3 bucket that carries a visible `practical_uniqueness` warning
- an API Gateway REST API

The bucket example is intentional: generation succeeds, but the warning stays
visible in template `Metadata` so the caller can review the naming tradeoff.

## What To Look For

- `Resources` contains ready-to-use CloudFormation resource definitions.
- `Outputs` exposes the generated names directly.
- `Metadata.NameHelperResults` captures the naming plan and diagnostics for
  each resource.

This keeps the examples useful both as runnable templates and as a reference
for how `namehelper` reasoning can travel with generated infrastructure code.
