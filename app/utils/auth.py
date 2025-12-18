import jwt
import requests
from functools import wraps
from flask import request, jsonify
import os
import time
import threading
from typing import Optional, Dict

class JWTVerifier:
    """
    JWT verification service that fetches and caches JWKS from Identity Service.
    Implements the verification flow according to VERIFY.md specification.
    """
    
    def __init__(self):
        self.identity_service_url = os.getenv("IDENTITY_SERVICE_URL", "")
        self.jwks_ttl_minutes = int(os.getenv("JWKS_TTL_IN_MINUTES", "10"))
        self.jwks_cache: Optional[Dict] = None
        self.jwks_cache_time: float = 0
        self.cache_lock = threading.Lock()
        
        # Fetch JWKS at startup
        self._fetch_jwks()
        
        # Start background thread to refresh JWKS periodically
        self.refresh_thread = threading.Thread(target=self._jwks_refresh_worker, daemon=True)
        self.refresh_thread.start()
    
    def _fetch_jwks(self):
        """
        Fetch JWKS from Identity Service.
        Updates cache only if fetch succeeds.
        """
        try:
            jwks_url = f"{self.identity_service_url}/.well-known/jwks.json"
            response = requests.get(jwks_url, timeout=5)
            response.raise_for_status()
            jwks_data = response.json()
            
            with self.cache_lock:
                self.jwks_cache = jwks_data
                self.jwks_cache_time = time.time()
                
            print(f"[JWTVerifier] JWKS fetched successfully from {jwks_url}")
        except Exception as e:
            print(f"[JWTVerifier] Failed to fetch JWKS: {e}")
            # Continue with cached keys if available (graceful degradation)
    
    def _jwks_refresh_worker(self):
        """
        Background worker that refreshes JWKS cache on TTL expiration.
        """
        while True:
            time.sleep(60)  # Check every minute
            
            with self.cache_lock:
                cache_age_minutes = (time.time() - self.jwks_cache_time) / 60
            
            if cache_age_minutes >= self.jwks_ttl_minutes:
                self._fetch_jwks()
    
    def _get_cached_jwks(self) -> Optional[Dict]:
        """Get cached JWKS in a thread-safe manner."""
        with self.cache_lock:
            return self.jwks_cache
    
    def verify_token(self, token: str) -> Dict:
        """
        Verify JWT token according to VERIFY.md specification.
        
        Returns:
            Dict with user claims if successful
            
        Raises:
            Exception with error message if verification fails
        """
        # Step 1: Parse JWT Header
        try:
            unverified_header = jwt.get_unverified_header(token)
        except Exception:
            raise Exception("Invalid JWT format")
        
        alg = unverified_header.get("alg")
        kid = unverified_header.get("kid")
        
        if alg != "RS256":
            raise Exception("Invalid algorithm, must be RS256")
        
        if not kid:
            raise Exception("Missing kid in JWT header")
        
        # Step 2: Resolve Public Key
        jwks = self._get_cached_jwks()
        if not jwks:
            raise Exception("JWKS not available")
        
        if jwks.get("kid") != kid:
            raise Exception("Unknown kid")
        
        public_key_pem = jwks.get("public_key")
        if not public_key_pem:
            raise Exception("Public key not found in JWKS")
        
        # Step 3: Verify Signature
        try:
            payload = jwt.decode(
                token,
                public_key_pem,
                algorithms=["RS256"],
                options={"verify_exp": True, "verify_iat": True}
            )
        except jwt.ExpiredSignatureError:
            raise Exception("Token has expired")
        except jwt.InvalidTokenError as e:
            raise Exception(f"Invalid token: {str(e)}")
        
        # Step 4: Validate Claims
        required_claims = ["sub", "full_name", "email", "exp", "iat"]
        for claim in required_claims:
            if claim not in payload:
                raise Exception(f"Missing required claim: {claim}")
        
        # Ensure permissions is an array (default to empty if not present)
        if "permissions" not in payload:
            payload["permissions"] = []
        elif not isinstance(payload["permissions"], list):
            raise Exception("permissions must be an array")
        
        return payload


# Global JWT verifier instance
_jwt_verifier: Optional[JWTVerifier] = None

def get_jwt_verifier() -> JWTVerifier:
    """Get or create the global JWT verifier instance."""
    global _jwt_verifier
    if _jwt_verifier is None:
        _jwt_verifier = JWTVerifier()
    return _jwt_verifier


def require_auth(f):
    """
    Decorator for Flask routes that require JWT authentication.
    Verifies JWT token and adds user claims to request context.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        
        if not auth_header.startswith("Bearer "):
            return {
                "status": "error",
                "error_code": "UNAUTHORIZED",
                "message": "Authentication token is invalid or expired"
            }, 401
        
        token = auth_header[7:]  # Remove "Bearer " prefix
        
        try:
            verifier = get_jwt_verifier()
            claims = verifier.verify_token(token)
            
            # Add user claims to request context
            request.user = claims
            
            return f(*args, **kwargs)
        except Exception as e:
            print(f"[Auth] JWT verification failed: {e}")
            return {
                "status": "error",
                "error_code": "UNAUTHORIZED",
                "message": "Authentication token is invalid or expired"
            }, 401
    
    return decorated_function
