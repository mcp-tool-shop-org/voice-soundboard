"""
Voice Soundboard v2.4 - Serverless Module

Cloud function handlers for AWS Lambda, Google Cloud Functions, and Azure Functions.

Features:
    - Cold start optimization
    - Automatic model caching
    - Stateless execution
    - Warm pool support

Usage:
    from voice_soundboard.serverless import create_handler

    handler = create_handler(
        backend="kokoro",
        cold_start_optimization=True,
        max_duration_seconds=30,
    )

    # Deploy to AWS Lambda, GCP Cloud Functions, or Azure Functions
"""

from voice_soundboard.serverless.handler import (
    create_handler,
    ServerlessHandler,
    ServerlessConfig,
    ServerlessRequest,
    ServerlessResponse,
)

from voice_soundboard.serverless.aws import (
    create_lambda_handler,
    LambdaConfig,
)

from voice_soundboard.serverless.gcp import (
    create_cloud_function_handler,
    CloudFunctionConfig,
)

from voice_soundboard.serverless.azure import (
    create_azure_function_handler,
    AzureFunctionConfig,
)

__all__ = [
    # Core
    "create_handler",
    "ServerlessHandler",
    "ServerlessConfig",
    "ServerlessRequest",
    "ServerlessResponse",
    # AWS
    "create_lambda_handler",
    "LambdaConfig",
    # GCP
    "create_cloud_function_handler",
    "CloudFunctionConfig",
    # Azure
    "create_azure_function_handler",
    "AzureFunctionConfig",
]
