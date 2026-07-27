# Fleet Intelligence Platform
a multi-domain vehicle telemetry platform with local
fog processing and a low-cost AWS serverless backend.

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
