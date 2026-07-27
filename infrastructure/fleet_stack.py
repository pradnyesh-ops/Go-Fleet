"""Low-cost Phase 1 AWS resources for fleet telemetry processing."""

from pathlib import Path

import aws_cdk as cdk
from aws_cdk import (
    Duration,
    RemovalPolicy,
    aws_apigateway as apigateway,
    aws_cloudwatch as cloudwatch,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as cloudfront_origins,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_iot as iot,
    aws_lambda as lambda_,
    aws_lambda_event_sources as lambda_event_sources,
    aws_s3 as s3,
    aws_s3_deployment as s3_deployment,
    aws_sns as sns,
    aws_sqs as sqs,
)
from constructs import Construct


class FleetPlatformStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs: object) -> None:
        super().__init__(scope, construct_id, **kwargs)
        project_root = Path(__file__).parents[1]

        archive_bucket = s3.Bucket(
            self,
            "RawEventArchive",
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,
            lifecycle_rules=[s3.LifecycleRule(expiration=Duration.days(180))],
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )
        events_table = dynamodb.Table(
            self,
            "Events",
            partition_key=dynamodb.Attribute(name="vehicle_id", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="timestamp_event_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="ttl",
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )
        events_table.add_global_secondary_index(
            index_name="domain-category-index",
            partition_key=dynamodb.Attribute(name="domain", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="category_timestamp", type=dynamodb.AttributeType.STRING),
        )
        latest_table = dynamodb.Table(
            self,
            "LatestVehicleState",
            partition_key=dynamodb.Attribute(name="vehicle_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )
        alerts = sns.Topic(self, "HighSeverityAlerts")
        dead_letter_queue = sqs.Queue(
            self,
            "TelemetryDeadLetterQueue",
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            retention_period=Duration.days(4),
        )
        queue = sqs.Queue(
            self,
            "TelemetryQueue",
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            visibility_timeout=Duration.seconds(30),
            dead_letter_queue=sqs.DeadLetterQueue(max_receive_count=3, queue=dead_letter_queue),
        )

        processor = lambda_.Function(
            self,
            "Processor",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="services.processor.app.handler",
            code=lambda_.Code.from_asset(
                str(project_root),
                exclude=[".venv", ".pytest_cache", "cdk.out", "tests", "web"],
            ),
            timeout=Duration.seconds(30),
            memory_size=512,
            environment={
                "EVENTS_TABLE_NAME": events_table.table_name,
                "LATEST_TABLE_NAME": latest_table.table_name,
                "ARCHIVE_BUCKET_NAME": archive_bucket.bucket_name,
                "ALERT_TOPIC_ARN": alerts.topic_arn,
            },
        )
        events_table.grant_write_data(processor)
        latest_table.grant_write_data(processor)
        archive_bucket.grant_put(processor)
        alerts.grant_publish(processor)
        processor.add_event_source(
            lambda_event_sources.SqsEventSource(queue, batch_size=10, report_batch_item_failures=True)
        )

        ingestion = lambda_.Function(
            self,
            "Ingestion",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="services.ingestion.app.handler",
            code=lambda_.Code.from_asset(
                str(project_root),
                exclude=[".venv", ".pytest_cache", "cdk.out", "tests", "web"],
            ),
            timeout=Duration.seconds(10),
            environment={"QUEUE_URL": queue.queue_url},
        )
        queue.grant_send_messages(ingestion)
        ingestion.add_permission(
            "AllowIotRuleInvocation",
            principal=iam.ServicePrincipal("iot.amazonaws.com"),
            action="lambda:InvokeFunction",
        )
        iot.CfnTopicRule(
            self,
            "TelemetryIngressRule",
            topic_rule_payload=iot.CfnTopicRule.TopicRulePayloadProperty(
                sql="SELECT *, topic() AS mqtt_topic FROM 'fleet/v1/#'",
                actions=[
                    iot.CfnTopicRule.ActionProperty(
                        lambda_=iot.CfnTopicRule.LambdaActionProperty(
                            function_arn=ingestion.function_arn
                        )
                    )
                ],
                rule_disabled=False,
            ),
        )

        dashboard_api = lambda_.Function(
            self,
            "DashboardApi",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="services.api.app.handler",
            code=lambda_.Code.from_asset(
                str(project_root),
                exclude=[".venv", ".pytest_cache", "cdk.out", "tests", "web"],
            ),
            timeout=Duration.seconds(10),
            environment={
                "EVENTS_TABLE_NAME": events_table.table_name,
                "LATEST_TABLE_NAME": latest_table.table_name,
            },
        )
        events_table.grant_read_data(dashboard_api)
        latest_table.grant_read_data(dashboard_api)
        api = apigateway.LambdaRestApi(
            self,
            "DashboardApiGateway",
            handler=dashboard_api,
            proxy=False,
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
            ),
        )
        vehicle = api.root.add_resource("vehicles").add_resource("{vehicleId}")
        vehicle.add_method("GET")
        vehicle.add_resource("latest").add_method("GET")

        dashboard_bucket = s3.Bucket(
            self,
            "DashboardSite",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )
        dashboard_distribution = cloudfront.Distribution(
            self,
            "DashboardDistribution",
            default_root_object="index.html",
            default_behavior=cloudfront.BehaviorOptions(
                origin=cloudfront_origins.S3BucketOrigin.with_origin_access_control(
                    dashboard_bucket
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            ),
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.minutes(1),
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.minutes(1),
                ),
            ],
        )
        s3_deployment.BucketDeployment(
            self,
            "DeployDashboard",
            sources=[s3_deployment.Source.asset(str(project_root / "web" / "dist"))],
            destination_bucket=dashboard_bucket,
            distribution=dashboard_distribution,
            distribution_paths=["/*"],
        )
        cloudwatch.Alarm(
            self,
            "DeadLetterMessages",
            metric=dead_letter_queue.metric_approximate_number_of_messages_visible(),
            threshold=1,
            evaluation_periods=1,
        )

        cdk.CfnOutput(self, "QueueUrl", value=queue.queue_url)
        cdk.CfnOutput(self, "EventsTableName", value=events_table.table_name)
        cdk.CfnOutput(self, "ArchiveBucketName", value=archive_bucket.bucket_name)
        cdk.CfnOutput(self, "DashboardApiUrl", value=api.url)
        cdk.CfnOutput(
            self,
            "DashboardUrl",
            value=f"https://{dashboard_distribution.distribution_domain_name}",
        )