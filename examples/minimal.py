"""Emit a minimal CloudFormation template using Troposphere.

Install the optional tooling first::

    make setup

Then run::

    PYTHONPATH=.python_packages:src python3 examples/minimal.py > minimal-template.json
"""

from __future__ import annotations

import sys

from namehelper import NameHelper
from namehelper.components import literal

try:
    from troposphere import Output, Template, apigateway, iam, s3, ssm
except ModuleNotFoundError as exc:  # pragma: no cover - import guard
    raise SystemExit(
        "Troposphere is required for this example. "
        "Install it with: make setup"
    ) from exc


def _finding_payload(result) -> list[dict[str, str]]:
    payload: list[dict[str, str]] = []
    for finding in result.findings:
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


def _result_payload(result) -> dict[str, object]:
    return {
        "certainty": result.certainty.value,
        "findings": _finding_payload(result),
        "rendered": result.rendered,
    }


def _require_rendered(helper: NameHelper, result, *, label: str) -> str:
    evaluation = helper.evaluate(result.findings)
    if evaluation.blocked or result.rendered is None:
        codes = ", ".join(f.code for f in result.findings) or "unresolved"
        raise RuntimeError(f"{label} name could not be rendered ({codes})")
    return result.rendered


def build_template() -> Template:
    """Build a small CloudFormation template with exact names."""
    helper = NameHelper()

    bucket_result = helper.name(
        literal("svc", "payments"),
        literal("env", "prod"),
        literal("purpose", "assets"),
        resource="s3-bucket",
    )
    role_result = helper.name(
        literal("svc", "payments"),
        literal("env", "prod"),
        literal("purpose", "app"),
        resource="iam-role",
    )
    parameter_result = helper.name(
        literal("path", "/payments/prod/app/config"),
        resource="ssm-parameter",
    )
    api_result = helper.name(
        literal("svc", "payments"),
        literal("env", "prod"),
        literal("kind", "api"),
        resource="apigateway-restapi",
    )

    bucket_name = _require_rendered(helper, bucket_result, label="AppBucket")
    role_name = _require_rendered(helper, role_result, label="AppRole")
    parameter_name = _require_rendered(
        helper, parameter_result, label="ConfigParameter"
    )
    api_name = _require_rendered(helper, api_result, label="ServiceApi")

    template = Template()
    template.set_version("2010-09-09")
    template.set_description(
        "Minimal CloudFormation template generated with exact names from "
        "namehelper."
    )
    template.set_metadata(
        {
            "GeneratedBy": f"namehelper {NameHelper.version()}",
            "NameHelperResults": {
                "AppBucket": _result_payload(bucket_result),
                "AppRole": _result_payload(role_result),
                "ConfigParameter": _result_payload(parameter_result),
                "ServiceApi": _result_payload(api_result),
            },
        }
    )

    template.add_resource(
        s3.Bucket(
            "AppBucket",
            BucketName=bucket_name,
        )
    )
    template.add_resource(
        iam.Role(
            "AppRole",
            AssumeRolePolicyDocument={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {
                            "Service": ["lambda.amazonaws.com"],
                        },
                        "Action": ["sts:AssumeRole"],
                    }
                ],
            },
            RoleName=role_name,
        )
    )
    template.add_resource(
        ssm.Parameter(
            "ConfigParameter",
            Name=parameter_name,
            Type="String",
            Value="enabled",
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
    template.add_output(Output("ParameterName", Value=parameter_name))
    template.add_output(Output("ApiName", Value=api_name))
    return template


def main() -> None:
    sys.stdout.write(build_template().to_json(indent=2, sort_keys=True))
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
