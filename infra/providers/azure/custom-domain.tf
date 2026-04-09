# -----------------------------
# CUSTOM DOMAIN + MANAGED TLS
# -----------------------------
# Apply 1 — creates TXT verification records alongside all other infrastructure.
# After DNS propagates (~5 min), complete domain binding per environment below.
#
# Production (tailord.app) — CLI:
#   az containerapp hostname add \
#     --name tailord-frontend-prod \
#     --resource-group tailord \
#     --hostname tailord.app
#
#   az containerapp hostname bind \
#     --name tailord-frontend-prod \
#     --resource-group tailord \
#     --hostname tailord.app \
#     --environment tailord-env-prod \
#     --validation-method TXT
#
# Staging (staging.tailord.app) — Portal (azurerm provider does not support serverless cert binding):
#   Azure requires the staging CNAME to resolve directly to the Container App
#   (not through Cloudflare) during validation.
#     1. In Cloudflare, set the `staging` CNAME to DNS Only (grey cloud)
#        and point it at: tailord-frontend-staging.{env-staging-default-domain}
#     2. Wait ~2 min for DNS to propagate
#     3. In the Azure Portal, open tailord-frontend-staging → Custom domains →
#        add staging.tailord.app with 'Managed certificate' and wait for it to be issued.
#
#   After the cert is issued (Succeeded):
#     4. Set the `staging` CNAME back to Proxied pointing at:
#        tailord-frontend-staging.{env-staging-default-domain}
#     5. Set Cloudflare SSL/TLS mode back to Full (Strict)

# TXT records proving domain ownership to Azure.
# Each environment has its own verification ID — prod and staging TXT records
# reference their respective environment.
resource "cloudflare_dns_record" "domain_verification" {
  zone_id = var.cloudflare_zone_id
  name    = "asuid"
  content = "\"${azurerm_container_app_environment.prod.custom_domain_verification_id}\""
  type    = "TXT"
  proxied = false
  ttl     = 300
}

resource "cloudflare_dns_record" "staging_domain_verification" {
  zone_id = var.cloudflare_zone_id
  name    = "asuid.staging"
  content = "\"${azurerm_container_app_environment.staging.custom_domain_verification_id}\""
  type    = "TXT"
  proxied = false
  ttl     = 300
}
