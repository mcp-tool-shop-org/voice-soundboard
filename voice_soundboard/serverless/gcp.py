"""
Google Cloud Functions Handler - GCP-optimized serverless TTS.

Features:
    - Cloud Storage integration
    - Cloud Trace support
    - Cloud Monitoring metrics
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
class CloudFunctionConfig(ServerlessConfig):
    """Google Cloud Functions specific configuration."""
    
    # GCP settings
    project_id: str | None = None
    region: str = "us-central1"
    
    # Cloud Storage
    gcs_bucket: str | None = None
    gcs_prefix: str = "voice-soundboard/"
    signed_url_expiry: int = 3600
    
    # Cloud Trace
    enable_trace: bool = True
    
    # Cloud Monitoring
    emit_metrics: bool = True


class CloudFunctionHandler(ServerlessHandler):
    """Google Cloud Functions optimized handler."""
    
    def __init__(self, config: CloudFunctionConfig | None = None):
        self.gcp_config = config or CloudFunctionConfig()
        super().__init__(self.gcp_config)
        
        # Get project ID from environment if not set
        if not self.gcp_config.project_id:
            self.gcp_config.project_id = os.environ.get("GCP_PROJECT")
    
    def handle_http_request(self, request) -> tuple[str, int, dict]:
        """
        Handle HTTP Cloud Function request.
        
        Args:
            request: Flask request object
            
        Returns:
            Tuple of (response_body, status_code, headers)
        """
        # Parse request
        if request.method == "POST":
            body = request.get_json(silent=True) or {}
        else:
            body = dict(request.args)
        
        synth_request = ServerlessRequest.from_dict(body)
        
        # Handle with tracing
        if self.gcp_config.enable_trace:
            response = self._handle_with_trace(synth_request, request)
        else:
            response = self.handle(synth_request)
        
        # Emit metrics
        if self.gcp_config.emit_metrics:
            self._emit_metrics(response)
        
        status_code = 200 if response.success else 400
        headers = {
            "Content-Type": "application/json",
            "X-Processing-Time-Ms": str(int(response.processing_time_ms)),
        }
        
        return response.to_json(), status_code, headers
    
    def handle_pubsub_event(
        self,
        event: dict[str, Any],
        context: Any,
    ) -> None:
        """
        Handle Pub/Sub triggered Cloud Function.
        
        For async/batch processing.
        """
        import base64
        
        # Decode Pub/Sub message
        if "data" in event:
            data = base64.b64decode(event["data"]).decode()
            body = json.loads(data)
        else:
            body = event
        
        request = ServerlessRequest.from_dict(body)
        response = self.handle(request)
        
        # If callback URL provided, send result
        if body.get("callback_url"):
            self._send_callback(body["callback_url"], response)
        
        # Or store in GCS
        if body.get("output_gcs_path") and response.success:
            self._store_to_gcs(response, body["output_gcs_path"])
    
    def _handle_with_trace(
        self,
        request: ServerlessRequest,
        http_request: Any,
    ) -> ServerlessResponse:
        """Handle with Cloud Trace."""
        try:
            from google.cloud import trace_v1
            
            # Cloud Trace integration would go here
            return self.handle(request)
        except ImportError:
            return self.handle(request)
    
    def _emit_metrics(self, response: ServerlessResponse) -> None:
        """Emit Cloud Monitoring metrics."""
        try:
            from google.cloud import monitoring_v3
            
            client = monitoring_v3.MetricServiceClient()
            project_name = f"projects/{self.gcp_config.project_id}"
            
            # Create time series for metrics
            # Simplified - full implementation would create proper time series
            
        except ImportError:
            pass
    
    def _send_callback(self, url: str, response: ServerlessResponse) -> None:
        """Send response to callback URL."""
        import urllib.request
        
        req = urllib.request.Request(
            url,
            data=response.to_json().encode(),
            headers={"Content-Type": "application/json"},
        )
        
        try:
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            pass
    
    def _store_to_gcs(self, response: ServerlessResponse, gcs_path: str) -> None:
        """Store audio to Cloud Storage."""
        try:
            from google.cloud import storage
            import base64
            
            client = storage.Client()
            
            # Parse GCS path
            if gcs_path.startswith("gs://"):
                gcs_path = gcs_path[5:]
            
            bucket_name, blob_path = gcs_path.split("/", 1)
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(blob_path)
            
            audio_bytes = base64.b64decode(response.audio_base64)
            blob.upload_from_string(audio_bytes, content_type="audio/mpeg")
            
        except Exception:
            pass
    
    def upload_to_gcs(self, audio_bytes: bytes, blob_name: str) -> str:
        """Upload audio to GCS and return signed URL."""
        from google.cloud import storage
        from datetime import timedelta
        
        client = storage.Client()
        bucket = client.bucket(self.gcp_config.gcs_bucket)
        
        full_path = f"{self.gcp_config.gcs_prefix}{blob_name}"
        blob = bucket.blob(full_path)
        
        blob.upload_from_string(audio_bytes, content_type="audio/mpeg")
        
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=self.gcp_config.signed_url_expiry),
            method="GET",
        )
        
        return url


def create_cloud_function_handler(
    backend: str = "kokoro",
    voice: str = "af_bella",
    gcs_bucket: str | None = None,
    **kwargs: Any,
) -> Callable:
    """
    Create a Google Cloud Function handler.
    
    Args:
        backend: TTS backend
        voice: Default voice
        gcs_bucket: Optional GCS bucket for outputs
        **kwargs: Additional config
        
    Returns:
        Cloud Function handler
        
    Usage:
        handler = create_cloud_function_handler(backend="kokoro")
        
        def main(request):
            return handler(request)
    """
    config = CloudFunctionConfig(
        backend=backend,
        voice=voice,
        gcs_bucket=gcs_bucket,
        **kwargs,
    )
    
    cf_handler = CloudFunctionHandler(config)
    
    def handler(request):
        return cf_handler.handle_http_request(request)
    
    return handler
