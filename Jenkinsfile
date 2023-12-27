pipeline {
    agent any
    options {
        buildDiscarder(logRotator(numToKeepStr: '30'))
        disableConcurrentBuilds()
    }

    stages {
        stage('Building Docker image') {
            environment {
                DOCKER_BUILD_ARG_PYPI_USER   = "harborn"
                DOCKER_BUILD_ARG_WRITE_SECRET = credentials("harborn_pypi_secret")
                DOCKER_BUILD_ARG_PRIVATE_PYPI_USER = "harborn"
                DOCKER_BUILD_ARG_PRIVATE_PYPI_SECRET = credentials("harborn_pypi_secret")
            }
            steps {
                script {
                    dockerfile.build_and_push()
                }
            }
        }
    }
}