"""OIDC bearer-token verification for single sign-on.

The identity provider authenticates; the local users table authorises. Users are
matched by a username claim and must already be provisioned and active, so roles
and tenants never come from identity-provider claims.
"""

from functools import lru_cache

import jwt

from regintel.core.config import get_settings

ALLOWED_ALGORITHMS = ["RS256", "RS384", "RS512", "ES256", "ES384", "PS256"]  # never HS* or none


class OIDCVerifier:

    def __init__(self, *, issuer: str, audience: str, jwks_url: str, username_claim: str = "preferred_username",
                 key_resolver=None, leeway_seconds: int = 30):
        if not issuer.startswith("https://") or not jwks_url.startswith("https://"):
            raise ValueError("OIDC issuer and JWKS URL must use HTTPS")
        self.issuer, self.audience, self.username_claim, self.leeway = issuer, audience, username_claim, leeway_seconds
        # Resolver maps a token to its signing key; PyJWKClient caches the provider's JWKS.
        self.key_resolver = key_resolver or jwt.PyJWKClient(jwks_url, cache_keys=True, lifespan=3600).get_signing_key_from_jwt

    def verify(self, token: str) -> str:
        """Return the username claim of a valid token, or raise ValueError."""
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") not in ALLOWED_ALGORITHMS:
                raise ValueError("Disallowed token algorithm")
            key = self.key_resolver(token)
            claims = jwt.decode(
                token, getattr(key, "key", key), algorithms=ALLOWED_ALGORITHMS,
                audience=self.audience, issuer=self.issuer, leeway=self.leeway,
                options={"require": ["iss", "aud", "exp", "iat", "sub"]},
            )
        except (jwt.InvalidTokenError, jwt.PyJWKClientError) as exc:
            raise ValueError("Invalid identity-provider token") from exc
        username = claims.get(self.username_claim)
        if not isinstance(username, str) or not username.strip():
            raise ValueError("Token has no usable username claim")
        return username.strip()


@lru_cache(maxsize=1)
def get_oidc_verifier() -> OIDCVerifier | None:
    settings = get_settings()
    if not settings.oidc_issuer:
        return None
    if not settings.oidc_audience or not settings.oidc_jwks_url:
        raise RuntimeError("OIDC_ISSUER requires OIDC_AUDIENCE and OIDC_JWKS_URL")
    return OIDCVerifier(issuer=settings.oidc_issuer, audience=settings.oidc_audience,
                        jwks_url=settings.oidc_jwks_url, username_claim=settings.oidc_username_claim)
