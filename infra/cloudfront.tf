variable "alb_dns_name" {
  description = "DNS name of the shared ALB created by the Kubernetes Ingresses. Set this after both Ingresses are available."
  type        = string
  default     = ""
}

resource "aws_cloudfront_distribution" "portfolio" {
  count = var.alb_dns_name == "" ? 0 : 1

  enabled             = true
  comment             = "Portfolio frontend and API"
  default_root_object = "index.html"

  origin {
    domain_name = var.alb_dns_name
    origin_id   = "portfolio-alb"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "portfolio-alb"
    viewer_protocol_policy = "redirect-to-https"
    cache_policy_id        = "658327ea-f89d-4fab-a63d-7e88639e58f6"
  }

  ordered_cache_behavior {
    path_pattern             = "/api*"
    allowed_methods          = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods           = ["GET", "HEAD"]
    target_origin_id         = "portfolio-alb"
    viewer_protocol_policy   = "redirect-to-https"
    cache_policy_id          = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"
    origin_request_policy_id = "b689b0a8-53d0-40ab-baf2-68738e2966ac"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = {
    Name = "devops-portfolio-cloudfront"
  }
}

output "cloudfront_domain_name" {
  description = "CloudFront domain for the portfolio; null until alb_dns_name is set."
  value       = var.alb_dns_name == "" ? null : aws_cloudfront_distribution.portfolio[0].domain_name
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID; null until alb_dns_name is set."
  value       = var.alb_dns_name == "" ? null : aws_cloudfront_distribution.portfolio[0].id
}
