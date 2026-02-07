"""
Azure Functions Handler - Azure-optimized serverless TTS.

Features:
    - Azure Blob Storage integration
    - Application Insights telemetry
    - Durable Functions support
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
class AzureFunctionConfig(ServerlessConfig):
    """Azure Functions specific configuration."""
    
    # Azure settings
    storage_account: str | None = None
    storage_container: str = "voice-soundboard"
    
    # Blob storage
    blob_sas_expiry: int = 3600
    
    # Application Insights
    enable_insights: bool = True
    instrumentation_key: str | None = None
    
    # Durable Functions
    enable_durable: bool = False


class AzureFunctionHandler(ServerlessHandler):
    """Azure Functions optimized handler."""
    
    def __init__(self, config: AzureFunctionConfig | None = None):
        self.azure_config = config or AzureFunctionConfig()
        super().__init__(self.azure_config)
        
        # Get instrumentation key from environment
        if not self.azure_config.instrumentation_key:
            self.azure_config.instrumentation_key = os.environ.get(
                "APPINSIGHTS_INSTRUMENTATIONKEY"
            )
    
    def handle_http_trigger(self, req) -> Any:
        """
        Handle HTTP-triggered Azure Function.
        
        Args:
            req: Azure Functions HttpRequest
            
        Returns:
            Azure Functions HttpResponse
        """
        try:
            import azure.functions as func
            
            # Parse request body
            try:
                body = req.get_json()
            except ValueError:
                body = dict(req.params)
            
            synth_request = ServerlessRequest.from_dict(body)
            
            # Handle with telemetry
            if self.azure_config.enable_insights:
                response = self._handle_with_insights(synth_request)
            else:
                response = self.handle(synth_request)
            
            return func.HttpResponse(
                body=response.to_json(),
                status_code=200 if response.success else 400,
                mimetype="application/json",
                headers={
                    "X-Processing-Time-Ms": str(int(response.processing_time_ms)),
                },
            )
            
        except ImportError:
            # Fallback for testing without Azure SDK
            return {
                "status_code": 500,
                "body": json.dumps({"error": "Azure Functions SDK not available"}),
            }
    
    def handle_queue_trigger(self, msg) -> None:
        """
        Handle Queue-triggered Azure Function.
        
        For async processing.
        """
        # Parse queue message
        if hasattr(msg, "get_body"):
            body = json.loads(msg.get_body().decode())
        else:
            body = msg if isinstance(msg, dict) else json.loads(msg)
        
        request = ServerlessRequest.from_dict(body)
        response = self.handle(request)
        
        # Handle output
        if body.get("callback_url"):
            self._send_callback(body["callback_url"], response)
        
        if body.get("output_blob_path") and response.success:
            self._store_to_blob(response, body["output_blob_path"])
    
    def handle_blob_trigger(self, blob, name: str) -> bytes | None:
        """
        Handle Blob-triggered Azure Function.
        
        Process text files and output audio.
        """
        # Read text from blob
        text = blob.read().decode()
        
        request = ServerlessRequest(text=text)
        response = self.handle(request)
        
        if response.success and response.audio_base64:
            import base64
            return base64.b64decode(response.audio_base64)
        
        return None
    
    def _handle_with_insights(self, request: ServerlessRequest) -> ServerlessResponse:
        """Handle with Application Insights telemetry."""
        try:
            from opencensus.ext.azure import metrics_exporter
            from opencensus.stats import aggregation, measure, stats, view
            
            # Track the request
            response = self.handle(request)
            
            # Log telemetry (simplified)
            # Full implementation would use proper OpenCensus integration
            
            return response
            
        except ImportError:
            return self.handle(request)
    
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
    
    def _store_to_blob(self, response: ServerlessResponse, blob_path: str) -> None:
        """Store audio to Azure Blob Storage."""
        try:
            from azure.storage.blob import BlobServiceClient
            import base64
            
            connection_string = os.environ.get("AzureWebJobsStorage")
            if not connection_string:
                return
            
            blob_service = BlobServiceClient.from_connection_string(connection_string)
            
            container_client = blob_service.get_container_client(
                self.azure_config.storage_container
            )
            
            blob_client = container_client.get_blob_client(blob_path)
            
            audio_bytes = base64.b64decode(response.audio_base64)
            blob_client.upload_blob(audio_bytes, overwrite=True)
            
        except Exception:
            pass
    
    def upload_to_blob(self, audio_bytes: bytes, blob_name: str) -> str:
        """Upload audio to Blob Storage and return SAS URL."""
        from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
        from datetime import datetime, timedelta
        
        connection_string = os.environ.get("AzureWebJobsStorage")
        blob_service = BlobServiceClient.from_connection_string(connection_string)
        
        container_client = blob_service.get_container_client(
            self.azure_config.storage_container
        )
        
        blob_client = container_client.get_blob_client(blob_name)
        blob_client.upload_blob(audio_bytes, overwrite=True)
        
        # Generate SAS URL
        sas_token = generate_blob_sas(
            account_name=blob_service.account_name,
            container_name=self.azure_config.storage_container,
            blob_name=blob_name,
            account_key=blob_service.credential.account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(seconds=self.azure_config.blob_sas_expiry),
        )
        
        return f"{blob_client.url}?{sas_token}"


def create_azure_function_handler(
    backend: str = "kokoro",
    voice: str = "af_bella",
    storage_container: str = "voice-soundboard",
    **kwargs: Any,
) -> Callable:
    """
    Create an Azure Function handler.
    
    Args:
        backend: TTS backend
        voice: Default voice
        storage_container: Blob storage container
        **kwargs: Additional config
        
    Returns:
        Azure Function handler
        
    Usage:
        handler = create_azure_function_handler(backend="kokoro")
        
        def main(req: func.HttpRequest) -> func.HttpResponse:
            return handler(req)
    """
    config = AzureFunctionConfig(
        backend=backend,
        voice=voice,
        storage_container=storage_container,
        **kwargs,
    )
    
    azure_handler = AzureFunctionHandler(config)
    
    def handler(req):
        return azure_handler.handle_http_trigger(req)
    
    return handler
