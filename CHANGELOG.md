# Changelog

## v1.0.0 — TBD

### API
- Initial public release
- Endpoints: GET /api/grains, GET /api/grains/{grain_id}, GET /api/changelog, POST /api/register
- API key authentication via X-API-Key header
- Rate limiting: 100 requests per hour per key

### Data
- 9 grain classes supported: CWRS, CWAD, CPSR, CANOLA, BARLEY_GP_CW, BARLEY_GP_CE, CORN_CW, CORN_CE, SOYBEANS
- Source: CGC Official Grain Grading Guide, effective crop year 2025/26