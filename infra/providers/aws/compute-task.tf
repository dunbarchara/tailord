resource "aws_ecs_task_definition" "task" {
  family                   = "${var.project_name}-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["EC2"]
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn
  cpu                      = "512"
  memory                   = "1024"

  container_definitions = jsonencode([
    {
      name      = "frontend"
      image     = "${aws_ecr_repository.repo.repository_url}:latest"
      essential = true

      cpu    = 256
      memory = 512

      portMappings = [{
        containerPort = var.container_port
        hostPort      = var.container_port
        protocol      = "tcp"
      }]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.log_group.name
          awslogs-region        = var.region
          awslogs-stream-prefix = "ecs-frontend"
        }
      }
    },
    {
      name      = "backend"
      image     = var.backend_image_uri != "" ? var.backend_image_uri : "${aws_ecr_repository.repo.repository_url}-backend:latest"
      essential = true

      cpu    = 256
      memory = 512

      portMappings = [{
        containerPort = 8000
        hostPort      = 8000
        protocol      = "tcp"
      }]

      environment = [
        { name = "DATABASE_URL",      value = "postgresql+psycopg://${var.db_username}:${var.db_password}@${aws_db_instance.postgres.address}/tailord" },
        { name = "API_KEY",           value = var.api_key },
        { name = "STORAGE_PROVIDER",  value = "aws" },
        { name = "S3_UPLOADS_BUCKET", value = aws_s3_bucket.uploads.bucket },
        { name = "AWS_REGION",        value = var.region },
        { name = "LLM_MODEL",         value = var.llm_model },
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.log_group.name
          awslogs-region        = var.region
          awslogs-stream-prefix = "ecs-backend"
        }
      }
    }
  ])
}
