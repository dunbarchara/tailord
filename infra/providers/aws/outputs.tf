output "load_balancer_dns" {
  value = aws_lb.alb.dns_name
}

output "ecr_repo_url" {
  value = aws_ecr_repository.repo.repository_url
}

output "db_endpoint" {
  value = aws_db_instance.postgres.address
}
