# ESI API Documentation URLs

## Purpose

This reference prevents wasted time hitting 404 endpoints when researching EVE Online's ESI API. Claude Code should consult this file BEFORE attempting to fetch ESI documentation.

---

## Working URLs (Use These)

### Primary Documentation Sources

| URL | Type | Use For |
|-----|------|---------|
| `https://developers.eveonline.com/docs` | HTML | Developer portal landing, high-level docs |
| `https://developers.eveonline.com/docs/services/esi/overview/` | HTML | ESI overview and concepts |
| `https://esi.evetech.net/latest/swagger.json` | JSON | **AUTHORITATIVE** - Complete endpoint schema, parameters, scopes |

### Secondary/Reference Sources

| URL | Type | Use For |
|-----|------|---------|
| `https://wiki.eveuniversity.org/EVE_Stable_Infrastructure` | HTML | Community documentation, practical examples |
| `https://login.eveonline.com/.well-known/oauth-authorization-server` | JSON | OAuth metadata and endpoints |

---

## Non-Working URLs (Do NOT Use)

These URLs return 404 errors. Do not attempt to fetch them:

| URL | Status | Why It Fails |
|-----|--------|--------------|
| `https://developers.eveonline.com/docs/esi/` | 404 | Path doesn't exist |
| `https://developers.eveonline.com/docs/services/esi` | 404 | Missing trailing component |
| `https://esi.evetech.net/ui/` | 404 | Swagger UI not hosted at this path |
| `https://esi.evetech.net/docs/` | 404 | No docs endpoint |
| `https://docs.esi.evetech.net/*` | DEPRECATED | Entire domain is deprecated |

---

## Recommended Approach

### For Endpoint Discovery

**Use the Swagger JSON directly:**
```
https://esi.evetech.net/latest/swagger.json
```

This returns the complete OpenAPI schema with:
- All endpoints and their paths
- Required parameters and types
- OAuth scopes needed
- Response schemas

### For Conceptual Understanding

**Use the developer portal overview:**
```
https://developers.eveonline.com/docs/services/esi/overview/
```

This provides:
- Authentication flow explanations
- Rate limiting information
- General usage patterns

### For Practical Examples

**EVE University wiki is reliable:**
```
https://wiki.eveuniversity.org/EVE_Stable_Infrastructure
```

This provides:
- Real-world usage examples
- Community best practices
- Common patterns and gotchas

---

## Implementation Pattern

When ARIA needs to research ESI capabilities:

1. **First**: Check local project files (existing scripts, skill files)
2. **If endpoint details needed**: Fetch `https://esi.evetech.net/latest/swagger.json`
3. **If conceptual docs needed**: Fetch `https://developers.eveonline.com/docs/services/esi/overview/`
4. **Never**: Guess URL paths - they're non-intuitive and often 404

---

## Changelog

- 2026.01.15: Initial creation based on observed 404 patterns
