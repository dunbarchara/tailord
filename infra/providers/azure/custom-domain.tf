# -----------------------------
# CUSTOM DOMAIN + MANAGED TLS
# -----------------------------
# Apply 1 — creates TXT verification records alongside all other infrastructure.
# After DNS propagates (~5 min), complete domain binding via CLI (see below).
#
# Production (tailord.app):
#   az containerapp hostname add \
#     --name tailord-frontend \
#     --resource-group tailord \
#     --hostname tailord.app
#
#   az containerapp hostname bind \
#     --name tailord-frontend \
#     --resource-group tailord \
#     --hostname tailord.app \
#     --environment tailord-env \
#     --validation-method TXT
#
# Staging (staging.tailord.app):
#   Prerequisite: Azure requires the staging CNAME to resolve directly to the
#   Container App (not through Cloudflare) during validation. Before running
#   the commands below:
#     1. In Cloudflare, set the `staging` CNAME to DNS Only (grey cloud)
#        and point it at: tailord-frontend.{env-default-domain}
#        (the main app FQDN, not the label URL)
#     2. Wait ~2 min for DNS to propagate
#
#   az containerapp hostname add \
#     --name tailord-frontend \
#     --resource-group tailord \
#     --hostname staging.tailord.app
#
#   az containerapp hostname bind \
#     --name tailord-frontend \
#     --resource-group tailord \
#     --hostname staging.tailord.app \
#     --environment tailord-env \
#     --validation-method TXT
#
#   After the cert is issued (Succeeded):
#     3. Set the `staging` CNAME back to Proxied and point it at the label URL:
#        tailord-frontend---staging.{env-default-domain}
#     4. Set Cloudflare SSL/TLS mode back to Full (Strict)
#
# Each command provisions a free Azure-managed cert and binds it.

# TXT records proving domain ownership to Azure.
# Azure checks: asuid.{domain} = container_app_environment.custom_domain_verification_id
resource "cloudflare_dns_record" "domain_verification" {
  zone_id = var.cloudflare_zone_id
  name    = "asuid.${var.domain_name}"
  content = "\"${azurerm_container_app_environment.tailord.custom_domain_verification_id}\""
  type    = "TXT"
  proxied = false
  ttl     = 300
}

resource "cloudflare_dns_record" "staging_domain_verification" {
  zone_id = var.cloudflare_zone_id
  name    = "asuid.staging.${var.domain_name}"
  content = "\"${azurerm_container_app_environment.tailord.custom_domain_verification_id}\""
  type    = "TXT"
  proxied = false
  ttl     = 300
}
