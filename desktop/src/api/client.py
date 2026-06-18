"""API client for backend communication"""

import httpx
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import json


@dataclass
class APIResponse:
    """API response wrapper"""
    success: bool
    data: Any = None
    error: str = ""
    status_code: int = 200


class APIClient:
    """HTTP client for API communication"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.access_token: Optional[str] = None
        self.client = httpx.Client(timeout=60.0)
    
    def set_token(self, token: str):
        """Set access token"""
        self.access_token = token
    
    def clear_token(self):
        """Clear access token"""
        self.access_token = None
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers
    
    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> APIResponse:
        """Make HTTP request"""
        
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()
        
        try:
            if method == "GET":
                response = self.client.get(url, headers=headers, params=params)
            elif method == "POST":
                response = self.client.post(
                    url, headers=headers, json=data, params=params
                )
            elif method == "PATCH":
                response = self.client.patch(
                    url, headers=headers, json=data, params=params
                )
            elif method == "DELETE":
                response = self.client.delete(url, headers=headers, params=params)
            else:
                return APIResponse(False, error=f"Unsupported method: {method}")
            
            # Parse response
            try:
                response_data = response.json()
            except json.JSONDecodeError:
                response_data = None
            
            if response.status_code >= 200 and response.status_code < 300:
                return APIResponse(
                    success=True,
                    data=response_data,
                    status_code=response.status_code,
                )
            else:
                error_msg = "Unknown error"
                if isinstance(response_data, dict):
                    error_msg = response_data.get("detail", error_msg)
                return APIResponse(
                    success=False,
                    error=error_msg,
                    status_code=response.status_code,
                )
        
        except httpx.ConnectError:
            return APIResponse(
                success=False,
                error="Cannot connect to server. Please check your internet connection.",
                status_code=0,
            )
        except httpx.TimeoutException:
            return APIResponse(
                success=False,
                error="Request timed out. Please try again.",
                status_code=0,
            )
        except Exception as e:
            return APIResponse(
                success=False,
                error=f"Request failed: {str(e)}",
                status_code=0,
            )

    def _request_multipart(
        self,
        endpoint: str,
        data: Dict[str, Any],
        file_field: str,
        file_path: str,
    ) -> APIResponse:
        """POST multipart/form-data with a single file."""

        url = f"{self.base_url}{endpoint}"
        headers = {"Accept": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        try:
            with open(file_path, "rb") as f:
                files = {file_field: (file_path, f, "application/octet-stream")}
                response = self.client.post(url, headers=headers, data=data, files=files, timeout=120.0)

            try:
                response_data = response.json()
            except json.JSONDecodeError:
                response_data = None

            if 200 <= response.status_code < 300:
                return APIResponse(True, data=response_data, status_code=response.status_code)

            error_msg = "Unknown error"
            if isinstance(response_data, dict):
                error_msg = response_data.get("detail", error_msg)
            return APIResponse(False, error=error_msg, status_code=response.status_code)

        except Exception as e:
            return APIResponse(False, error=f"Request failed: {e}", status_code=0)
    
    # Authentication
    def register(self, email: str, password: str, full_name: str = "") -> APIResponse:
        """Register new user"""
        return self._request(
            "POST",
            "/auth/register",
            data={"email": email, "password": password, "full_name": full_name},
        )
    
    def login(self, email: str, password: str) -> APIResponse:
        """Login user"""
        return self._request(
            "POST",
            "/auth/login",
            data={"email": email, "password": password},
        )
    
    def refresh_token(self, refresh_token: str) -> APIResponse:
        """Refresh access token"""
        return self._request(
            "POST",
            "/auth/refresh",
            data={"refresh_token": refresh_token},
        )
    
    # User
    def get_current_user(self) -> APIResponse:
        """Get current user profile"""
        return self._request("GET", "/users/me")
    
    def update_user(self, data: Dict) -> APIResponse:
        """Update user profile"""
        return self._request("PATCH", "/users/me", data=data)
    
    def get_user_stats(self) -> APIResponse:
        """Get user statistics"""
        return self._request("GET", "/users/me/stats")
    
    # Generations
    def generate_image(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        style: Optional[str] = None,
    ) -> APIResponse:
        """Generate image"""
        data = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
        }
        if style:
            data["style"] = style
        return self._request("POST", "/generations/images", data=data)

    def generate_image_img2img(
        self,
        image_path: str,
        prompt: str,
        negative_prompt: str = "",
        strength: float = 0.65,
        style: Optional[str] = None,
        size: Optional[str] = None,
    ) -> APIResponse:
        """Generate an image from an input image (img2img)."""

        data: Dict[str, Any] = {
            "prompt": prompt,
            "negative_prompt": negative_prompt or "",
            "strength": str(strength),
        }
        if style:
            data["style"] = style
        if size:
            data["size"] = size

        return self._request_multipart(
            "/generations/image/img2img",
            data=data,
            file_field="image",
            file_path=image_path,
        )
    
    def generate_video(
        self,
        prompt: str,
        negative_prompt: str = "",
        duration: int = 4,
        width: int = 1024,
        height: int = 576,
    ) -> APIResponse:
        """Generate video"""
        return self._request(
            "POST",
            "/generations/videos",
            data={
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "duration": duration,
                "width": width,
                "height": height,
            },
        )

    def generate_video_img2vid(
        self,
        image_path: str,
        prompt: Optional[str] = None,
        motion_strength: int = 50,
        duration: int = 4,
        resolution: str = "1024x576",
    ) -> APIResponse:
        """Generate a video from an input image (img2vid)."""

        data: Dict[str, Any] = {
            "motion_strength": str(int(motion_strength)),
            "duration": str(int(duration)),
            "resolution": resolution,
        }
        if prompt is not None:
            data["prompt"] = prompt

        return self._request_multipart(
            "/generations/video/img2vid",
            data=data,
            file_field="image",
            file_path=image_path,
        )

    def list_generations(
        self,
        generation_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> APIResponse:
        """List generations"""
        params = {"page": page, "page_size": page_size}
        if generation_type:
            params["generation_type"] = generation_type
        return self._request("GET", "/generations/", params=params)
    
    def get_generation(self, generation_id: int) -> APIResponse:
        """Get specific generation"""
        return self._request("GET", f"/generations/{generation_id}")
    
    def delete_generation(self, generation_id: int) -> APIResponse:
        """Delete generation"""
        return self._request("DELETE", f"/generations/{generation_id}")
    
    # Credits
    def get_credit_balance(self) -> APIResponse:
        """Get credit balance"""
        return self._request("GET", "/credits/balance")
    
    def get_credit_packages(self) -> APIResponse:
        """Get available credit packages"""
        return self._request("GET", "/credits/packages")
    
    def purchase_credits(self, package_id: str) -> APIResponse:
        """Purchase credits"""
        return self._request(
            "POST",
            "/credits/purchase",
            data={"package_id": package_id},
        )
    
    def get_credit_history(self, limit: int = 50) -> APIResponse:
        """Get credit transaction history"""
        return self._request(
            "GET",
            "/credits/history",
            params={"limit": limit},
        )
    
    # Subscriptions
    def get_subscription_plans(self) -> APIResponse:
        """Get subscription plans"""
        return self._request("GET", "/subscriptions/plans")
    
    def get_current_subscription(self) -> APIResponse:
        """Get current subscription"""
        return self._request("GET", "/subscriptions/current")
    
    def subscribe(self, tier: str) -> APIResponse:
        """Create subscription"""
        return self._request(
            "POST",
            "/subscriptions/subscribe",
            data={"tier": tier},
        )
    
    def cancel_subscription(self) -> APIResponse:
        """Cancel subscription"""
        return self._request("POST", "/subscriptions/cancel")


# Singleton instance
_api_client: Optional[APIClient] = None


def get_api_client(base_url: str = "") -> APIClient:
    """Get or create API client singleton"""
    global _api_client
    if _api_client is None:
        _api_client = APIClient(base_url)
    return _api_client
