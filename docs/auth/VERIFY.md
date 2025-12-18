## JWT Verification

Every downstream service that consumes JWTs issued by the **Identity Service** MUST implement JWKS-based verification according to this specification.

---

## 1. JWKS Fetching

* Services that need authentication/authorization
    must verify JWT in header:

      Authorization: Bearer <JWT>
    
* In order to verify JWTs, they must fetch JWKS (public keys)
    from:

  ```
  {IDENTITY_SERVICE_URL}/.well-known/jwks.json
  ```

  in which `IDENTITY_SERVICE_URL` can be obtained
  from environment variables (`.env`).

  Response body format:

  ```ts
  [
    {
      "kid": string, // key ID, UUID-v4
      "kty": string, // key type, must be one of: "RSA"
      "alg": string, // signing algorithm, must be one of: "RS256",
      "public_key": string, // public key to verify JWTs, in PEM format, e.g.
      // -----BEGIN PUBLIC KEY-----\nMIIBIjANBgkq...\n-----END PUBLIC KEY-----
      "use": string, // must be "sig"
    },

    // ... more
  ]
  ```

* Public keys MUST NOT be hard-coded.
* JWKS retrieval MUST be performed:

  * At service startup
  * On a fixed TTL schedule, default 10 minutes, and is configurable via the environment variable `JWKS_TTL_IN_MINUTES`.

* After retrieval, the keys are stored
    in internal variables, not to files.
    Use those variables to verify JWT,
    as specified below.

### Cache Rules

* JWKS cache refresh MUST occur:

  * Only when TTL expires

* JWKS cache refresh MUST NOT occur:

  * On JWT verification failure
  * On unknown `kid`
  * On signature mismatch

This rule is mandatory to prevent DoS attacks.

---

## 3. Verification Flow (Strict)

For **every incoming request**, the downstream service MUST execute the following steps **in order** (after obtaining the JWT from the Authorization header as specified above):

### Step 1: Parse JWT Header

* Extract:

  * `alg`
  * `kid`

* If:

  * `alg` ≠ `RS256`
  * `kid` is missing
    → **Reject with HTTP 401**

### Step 2: Resolve Public Key

* Look up the public key matching `kid` in the **cached JWKS**.
* If no matching key is found:

  * **DO NOT refresh JWKS**
  * **Reject with HTTP 401**

### Step 3: Verify Signature

* Verify the JWT signature using:

  * Resolved public key
  * Algorithm **RS256 only**
* If verification fails:

  * **Reject with HTTP 401**

### Step 4: Validate Claims

The following JWT payload claims MUST be validated:

* `exp` — must not be expired
* `iat` — must be within acceptable skew
* `sub` — user ID - must exist
* `full_name` — user's full name, string
* `email` — email address, string
* `permissions` — optional, array of granted permissions (`Array<string>`).

If any validation fails:

* **Reject with HTTP 401**

## 4. Authorization Using Permissions

* The `permissions` claim, if present, MUST be an array of strings. Eventually, each request (in Python code) must have the permissions array present (by default, no permission at all).

* Authorization decisions MUST rely **exclusively** on the `permissions` claim.

* Downstream services MUST NOT:
  * Query Identity Service for permissions
  * Recompute permissions from roles (which is impossible - JWTs do not include roles)

## 5. Behavior on Key Rotation

When fetching JWKS endpoint, downstream services
MUST assume JWKS response may contain
**multiple active keys**.

---

## 6. Failure Handling

### JWT Invalid

If any verification step fails:

* Return **HTTP 401 Unauthorized**
* Do NOT retry verification
* Do NOT refresh JWKS
* Log the failure for audit purposes

### JWKS Endpoint Unavailable

If JWKS refresh fails during scheduled refresh:

* Continue using cached JWKS (graceful degradation)
* Log warning
* Reject requests only if verification fails with cached keys


