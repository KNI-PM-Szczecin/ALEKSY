pipeline {
    agent any

    environment {
        PATH = "/usr/local/bin:/opt/homebrew/bin:${env.PATH}"
    }

    stages {
        stage('Build image') {
            steps {
                sh "docker build -t aleksy-bot ."
            }
        }

        stage('Deploy') {
            steps {
                sh """
                    mkdir -p ~/Containers/ALEKSY

                    cp .env ~/Containers/ALEKSY/.env

                    cat > ~/Containers/ALEKSY/docker-compose.yml << 'COMPOSE'
name: aleksy

services:
  aleksy:
    image: aleksy-bot:latest
    container_name: ALEKSY
    restart: unless-stopped
    env_file:
      - .env
    environment:
      TIMEZONE: \${TIMEZONE:-Europe/Warsaw}
COMPOSE

                    docker compose -f ~/Containers/ALEKSY/docker-compose.yml up -d --force-recreate
                """
            }
        }
    }
}
