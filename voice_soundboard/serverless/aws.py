"""
AWS Lambda Handler - AWS-optimized serverless TTS.

Features:
    - Lambda Layers support for models
    - S3 integration for large outputs
    - CloudWatch metrics
    - X-Ray tracing
"""

from __future__ import annotations

import os
import json
from dataclasses import dataclass
from typing import Any, Callable

from voice_soundboard.serverless.handler import (
    ServerlessHandler,
    ServerlessConfig,
    ServerlessRequest,
    ServerlessResponse,
)


@dataclass
class LambdaConfig(ServerlessConfig):
    """AWS Lambda specific configuration."""
    
    # Lambda settings
    memory_mb: int = 1024
    timeout_seconds: float = 30.0
    
    # S3 settings
    s3_bucket: str | None = None
    s3_prefix: str = "voice-soundboard/"
    presigned_url_expiry: int = 3600
    
    # Lambda Layers
    use_model_layer: bool = True
    model_layer_path: str = "/opt/models"
    
    # CloudWatch
    emit_metrics: bool = True
    metric_namespace: str = "VoiceSoundboard"
    
    # X-Ray
    enable_xray: bool = True


class LambdaHandler(ServerlessHandler):
    """AWS Lambda optimized handler."""
    
    def __init__(self, config: LambdaConfig | None = None):
        self.lambda_config = config or LambdaConfig()
        super().__init__(self.lambda_config)
        
        # Set model path from Lambda Layer
        if self.lambda_config.use_model_layer:
            os.environ.setdefault(
                "VOICE_SOUNDBOARD_MODEL_PATH",
                self.lambda_config.model_layer_path,
            )
    
    def handle_lambda_event(
        self,
        event: dict[str, Any],
        context: Any,
    ) -> dict[str, Any]:
        """
        Handle AWS Lambda event.
        
        Supports:
            - API Gateway (REST and HTTP)
            - Direct invocation
            - ALB
        """
        # Extract body from different event sources
        body = self._extract_body(event)
        
        # Parse request
        request = ServerlessRequest.from_dict(body)
        
        # Handle with tracing
        if self.lambda_config.enable_xray:
            response = self._handle_with_xray(request, context)
        else:
            response = self.handle(request)
        
        # Emit metrics
        if self.lambda_config.emit_metrics:
            self._emit_metrics(response, context)
        
        # Format response for API Gateway
        return self._format_response(response)
    
    def _extract_body(self, event: dict[str, Any]) -> dict[str, Any]:
        """Extract request body from different event formats."""
        # API Gateway
        if "body" in event:
            body = event["body"]
            if isinstance(body, str):
                # Check for base64 encoding
                if event.get("isBase64Encoded"):
                    import base64
                    body = base64.b64decode(body).decode()
                return json.loads(body)
            return body
        
        # Direct invocation
        if "text" in event:
            return event
        
        # ALB
        if "requestContext" in event and "elb" in event.get("requestContext", {}):
            body = event.get("body", "{}")
            return json.loads(body)
        
        return event
    
    def _handle_with_xray(
        self,
        request: ServerlessRequest,
        context: Any,
    ) -> ServerlessResponse:
        """Handle with X-Ray tracing."""
        try:
            from aws_xray_sdk.core import xray_recorder
            
            with xray_recorder.in_subsegment("synthesize"):
                xray_recorder.put_annotation("voice", request.voice or self.config.voice)
                xray_recorder.put_annotation("text_length", len(request.text))
                
                response = self.handle(request)
                
                xray_recorder.put_annotation("success", response.success)
                xray_recorder.put_metadata("duration_seconds", response.duration_seconds)
                
                return response
        except ImportError:
            return self.handle(request)
    
    def _emit_metrics(self, response: ServerlessResponse, context: Any) -> None:
        """Emit CloudWatch metrics."""
        try:
            import boto3
            
            cloudwatch = boto3.client("cloudwatch")
            
            metrics = [
                {
                    "MetricName": "SynthesisLatency",
                    "Value": response.processing_time_ms,
                    "Unit": "Milliseconds",
                },
                {
                    "MetricName": "SynthesisSuccess",
                    "Value": 1 if response.success else 0,
                    "Unit": "Count",
                },
            ]
            
            if response.success:
                metrics.append({
                    "MetricName": "AudioDuration",
                    "Value": response.duration_seconds,
                    "Unit": "Seconds",
                })
            
            if response.cold_start:
                metrics.append({
                    "MetricName": "ColdStarts",
                    "Value": 1,
                    "Unit": "Count",
                })
            
            cloudwatch.put_metric_data(
                Namespace=self.lambda_config.metric_namespace,
                MetricData=metrics,
            )
        except Exception:
            pass
    
    def _format_response(self, response: ServerlessResponse) -> dict[str, Any]:
        """Format response for API Gateway."""
        return {
            "statusCode": 200 if response.success else 400,
            "headers": {
                "Content-Type": "application/json",
                "X-Processing-Time-Ms": str(int(response.processing_time_ms)),
                "X-Cold-Start": str(response.cold_start).lower(),
            },
            "body": response.to_json(),
        }
    
    def upload_to_s3(self, audio_bytes: bytes, key: str) -> str:
        """Upload audio to S3 and return presigned URL."""
        import boto3
        
        s3 = boto3.client("s3")
        
        full_key = f"{self.lambda_config.s3_prefix}{key}"
        
        s3.put_object(
            Bucket=self.lambda_config.s3_bucket,
            Key=full_key,
            Body=audio_bytes,
            ContentType="audio/mpeg",
        )
        
        url = s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.lambda_config.s3_bucket,
                "Key": full_key,
            },
            ExpiresIn=self.lambda_config.presigned_url_expiry,
        )
        
        return url


def create_lambda_handler(
    backend: str = "kokoro",
    voice: str = "af_bella",
    s3_bucket: str | None = None,
    **kwargs: Any,
) -> Callable:
    """
    Create an AWS Lambda handler function.
    
    Args:
        backend: TTS backend
        voice: Default voice
        s3_bucket: Optional S3 bucket for large outputs
        **kwargs: Additional config
        
    Returns:
        Lambda handler function
        
    Usage:
        handler = create_lambda_handler(backend="kokoro")
        
        # In SAM/CloudFormation:
        # Handler: my_module.handler
    """
    config = LambdaConfig(
        backend=backend,
        voice=voice,
        s3_bucket=s3_bucket,
        **kwargs,
    )
    
    lambda_handler = LambdaHandler(config)
    
    def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
        return lambda_handler.handle_lambda_event(event, context)
    
    return handler
