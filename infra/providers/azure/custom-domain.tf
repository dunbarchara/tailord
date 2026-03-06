# -----------------------------
# CUSTOM DOMAIN + MANAGED TLS
# -----------------------------
# Apply 1 — creates TXT verification record alongside all other infrastructure.
# After DNS propagates (~5 min), complete domain binding via CLI (see below).
#
# Post-apply CLI steps:
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
# The second command provisions a free Azure-managed cert and binds it.
# Once complete, set Cloudflare SSL/TLS mode to Full (Strict).

# TXT record proving domain ownership to Azure.
# Azure checks: asuid.{domain} = container_app_environment.custom_domain_verification_id
resource "cloudflare_dns_record" "domain_verification" {
  zone_id = var.cloudflare_zone_id
  name    = "asuid.${var.domain_name}"
  content = "\"${azurerm_container_app_environment.tailord.custom_domain_verification_id}\""
  type    = "TXT"
  proxied = false
  ttl     = 300
}
