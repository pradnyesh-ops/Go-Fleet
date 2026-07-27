# Fleet Intelligence Platform

Phase 1 implementation of a multi-domain vehicle telemetry platform with local
fog processing and a low-cost AWS serverless backend.

## Implemented Local Flow

`Sensor generators -> fog processor -> validated MQTT event -> SQLite outbox`

The local implementation supports rental, fleet, and industrial profiles; all
five sensor types; configurable YAML rates; rolling anomaly scoring; ray-cast
geofence checks; domain/category tagging; deterministic event IDs; and ordered
offline replay.

## Quick Start

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m pip install pytest -r infrastructure/requirements.txt
.venv/bin/python -m pytest tests
.venv/bin/python scripts/run_local_demo.py
```

## AWS Deployment Preparation

The CDK stack targets `eu-west-1` and provisions AWS IoT Rule ingress, ingestion
and processing Lambdas, SQS plus DLQ, DynamoDB event/latest-state tables, S3
archive, SNS alerts, a dashboard read API, API Gateway, a private dashboard S3
origin, and a CloudFront HTTPS distribution.

```sh
npx aws-cdk@2 bootstrap aws://ACCOUNT_ID/eu-west-1
npm ci --prefix web
npm run build --prefix web
npx aws-cdk@2 synth --app '.venv/bin/python infrastructure/app.py'
npx aws-cdk@2 deploy --app '.venv/bin/python infrastructure/app.py'
```

Run `cdk diff` before deployment and `cdk destroy` after the assessment to
avoid charges. AWS credentials and IoT certificates are intentionally not
stored in this repository.

## CI/CD Setup

`.github/workflows/validate.yml` runs Python tests, the dashboard production
build, and CDK synthesis for pull requests and changes to `main`.

`.github/workflows/deploy.yml` performs an explicitly triggered deployment via
GitHub OpenID Connect. Before using it:

1. Create an IAM role trusted by `token.actions.githubusercontent.com`, limited
	to this repository.
2. Grant that role the CDK deployment permissions for the bootstrapped account.
3. Run the **Deploy AWS** workflow manually from GitHub Actions and provide the
	role ARN when prompted. An IAM role ARN is not a secret.

The workflow does not use long-lived AWS access keys. After deployment, open the
`DashboardUrl` CloudFormation stack output to use the cloud dashboard. The fog
layer remains a local simulation until AWS IoT certificates are configured.