resource "cloudflare_dns_record" "acm_validation" {
  for_each = {
    for dvo in aws_acm_certificate.app.domain_validation_options :
    dvo.domain_name => {
      name  = dvo.resource_record_name
      type  = dvo.resource_record_type
      value = trimsuffix(dvo.resource_record_value, ".")
    }
  }

  zone_id = var.cloudflare_zone_id
  name    = each.value.name
  type    = each.value.type
  content = each.value.value

  ttl     = 300
  proxied = false
}

resource "cloudflare_dns_record" "app" {
  zone_id = var.cloudflare_zone_id
  content = aws_lb.alb.dns_name
  name    = var.domain_name
  type    = "CNAME"
  proxied = true
  ttl     = 1
}

resource "cloudflare_dns_record" "www" {
  zone_id = var.cloudflare_zone_id
  content = var.domain_name
  name    = "www"
  type    = "CNAME"
  proxied = true
  ttl     = 1
}

data "cloudflare_ip_ranges" "cloudflare" {}
