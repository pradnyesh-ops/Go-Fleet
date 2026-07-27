#!/usr/bin/env python3
"""CDK entry point for the Fleet Intelligence Platform."""

import aws_cdk as cdk

from fleet_stack import FleetPlatformStack


app = cdk.App()
FleetPlatformStack(
    app,
    "FleetIntelligencePlatform",
    env=cdk.Environment(region="eu-west-1"),
)
app.synth()