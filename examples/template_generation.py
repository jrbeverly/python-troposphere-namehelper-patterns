"""Emit a CloudFormation template through Troposphere and ``TemplateHelper``.

Install the optional tooling first::

    make setup

Then run::

    PYTHONPATH=.python_packages:src python3 examples/template_generation.py > adapter-template.json
"""

from __future__ import annotations

import sys

from namehelper import NameHelper
from namehelper.adapters import TemplateHelper, from_context
from namehelper.components import literal, unique_id

try:
    from troposphere import Output, Template, apigateway, iam, s3
except ModuleNotFoundError as exc:  # pragma: no cover - import guard
    raise SystemExit(
        "Troposphere is required for this example. "
        "Install it with: make setup"
    ) from exc


def _finding_payload(findings) -> list[dict[str, str]]:
    payload: list[dict[str, str]] = []
    for finding in findings:
        item = {
            "code": finding.code,
            "message": finding.message,
            "severity": finding.severity.value,
        }
        if finding.certainty is not None:
            item["certainty"] = finding.certainty.value
        if finding.component is not None:
            item["component"] = finding.component
        payload.append(item)
    return payload


def _result_payload(helper: TemplateHelper, result) -> dict[str, object]:
    evaluation = helper.evaluate(result.findings)
    return {
        "blocked": evaluation.blocked,
        "certainty": result.certainty.value,
        "confidence_codes": [
            item.finding.code for item in evaluation.confidence
        ],
        "fatal_codes": [item.finding.code for item in evaluation.fatal],
        "findings": _finding_payload(result.findings),
        "rendered": result.rendered,
        "segments": [
            {
                "certainty": segment.certainty.value,
                "form": (
                    segment.form.value if segment.form is not None else None
                ),
                "role": segment.role,
                "value": segment.value,
            }
            for segment in result.plan.segments
        ],
        "structural_codes": [
            item.finding.code for item in evaluation.structural
        ],
        "warning_codes": [item.finding.code for item in evaluation.warnings],
    }


def _require_generated(helper: TemplateHelper, result, *, label: str) -> str:
    emitted = helper.generate_or_block(result)
    if emitted is None:
        codes = ", ".join(f.code for f in result.findings) or "unresolved"
        raise RuntimeError(f"{label} name could not be emitted ({codes})")
    return emitted


def build_template() -> Template:
    """Build a realistic CloudFormation template with adapter diagnostics."""
    helper = TemplateHelper()
    context = from_context(
        region_code="us-east-1",
        stack="orders-prod",
    )

    role_result = helper.name(
        *context.values(),
        literal("svc", "payments"),
        resource="iam-role",
    )
    bucket_result = helper.name(
        literal("svc", "payments"),
        literal("env", "prod"),
        unique_id("suffix", "artifacts01"),
        resource="s3-bucket",
    )
    api_result = helper.name(
        literal("svc", "payments"),
        literal("env", "prod"),
        literal("kind", "api"),
        resource="apigateway-restapi",
    )

    role_name = _require_generated(helper, role_result, label="ExecutionRole")
    bucket_name = _require_generated(
        helper, bucket_result, label="ArtifactsBucket"
    )
    api_name = _require_generated(helper, api_result, label="ServiceApi")

    template = Template()
    template.set_version("2010-09-09")
    template.set_description(
        "CloudFormation template generated through the namehelper "
        "TemplateHelper adapter."
    )
    template.set_metadata(
        {
            "GeneratedBy": f"namehelper {NameHelper.version()}",
            "NameHelperResults": {
                "ArtifactsBucket": _result_payload(helper, bucket_result),
                "ExecutionRole": _result_payload(helper, role_result),
                "ServiceApi": _result_payload(helper, api_result),
            },
        }
    )

    template.add_resource(
        s3.Bucket(
            "ArtifactsBucket",
            BucketName=bucket_name,
        )
    )
    template.add_resource(
        iam.Role(
            "ExecutionRole",
            AssumeRolePolicyDocument={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {
                            "Service": ["ecs-tasks.amazonaws.com"],
                        },
                        "Action": ["sts:AssumeRole"],
                    }
                ],
            },
            ManagedPolicyArns=[
                "arn:aws:iam::aws:policy/service-role/"
                "AmazonECSTaskExecutionRolePolicy"
            ],
            RoleName=role_name,
        )
    )
    template.add_resource(
        apigateway.RestApi(
            "ServiceApi",
            Name=api_name,
        )
    )

    template.add_output(Output("BucketName", Value=bucket_name))
    template.add_output(Output("RoleName", Value=role_name))
    template.add_output(Output("ApiName", Value=api_name))
    return template


def main() -> None:
    sys.stdout.write(build_template().to_json(indent=2, sort_keys=True))
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
