# Docker Setup for Cayuman

This document provides instructions for running the Cayuman application using Docker and Docker Compose.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

## Configuration

The Docker setup includes:

1. A MySQL database container
2. A web application container running the Django application

### Environment Variables

The application uses environment variables from your `.env` file. The Docker setup will:

1. Load all environment variables from your existing `.env` file
2. Override only the `DATABASE` setting to use the MySQL container

This means you can keep your local development settings in `.env` and the Docker setup will automatically use them, except for the database configuration which is set to use the MySQL container.

## Getting Started

### 1. Build and Start the Services

```bash
docker compose up -d
```

This command will:

- Build the Docker image for the web application
- Start the MySQL database container
- Start the web application container
- Set up the necessary volumes for data persistence

### 2. Access the Application

Once the containers are running, you can access the application at:

- Web application: `http://localhost:9000`

### 3. Database Access

The MySQL database is exposed on port 3306 and can be accessed with the following credentials:

- Host: localhost
- Port: 3306
- Database: cayuman
- Username: cayuman
- Password: cayuman_password

### 4. Stopping the Services

To stop the services:

```bash
docker compose down
```

To stop the services and remove the volumes (this will delete all data):

```bash
docker compose down -v
```

## Development Workflow

### Live Code Changes

The Docker setup is configured for development with live code reloading:

1. The local project directory is mounted to `/app` in the container
2. Django's development server (`runserver`) is used
3. Any changes you make to your local files will be immediately reflected in the running application

This means you can:

- Edit code on your local machine with your preferred editor/IDE
- Save the changes
- See the changes immediately in the running application (for most changes)
- Django's auto-reload feature will restart the server when needed

For changes that require a manual restart (like adding new dependencies):

```bash
docker compose restart web
```

### Loading a SQL Backup File

If you have a SQL backup file that you want to load into the MySQL container while preserving existing data:

#### Option 1: Direct Import from Host

The simplest method is to import the SQL file directly from your host machine:

```bash
cat your_backup.sql | docker compose exec -T db mysql -ucayuman -pcayuman_password cayuman
```

This pipes the contents of your SQL file directly into the MySQL client running in the container.

#### Option 2: Using docker cp and mysql Command

1. First, copy your SQL file to the container:

   ```bash
   docker cp your_backup.sql $(docker compose ps -q db):/tmp/
   ```

2. Then execute the mysql command inside the container:

   ```bash
   docker compose exec db bash -c "mysql -ucayuman -pcayuman_password cayuman < /tmp/your_backup.sql"
   ```

#### Option 3: Using MySQL Client on Host

If you have the MySQL client installed on your host machine, you can connect directly to the containerized MySQL:

```bash
mysql -h 127.0.0.1 -P 3306 -u cayuman -pcayuman_password cayuman < your_backup.sql
```

### Running Migrations

```bash
docker compose exec web poetry run python manage.py migrate
```

### Creating a Superuser

```bash
docker compose exec web poetry run python manage.py createsuperuser
```

### Running Management Commands

You can run any Django management command using:

```bash
docker compose exec web poetry run python manage.py [command]
```

### Running Tests

```bash
docker compose exec web poetry run pytest
```

### Viewing Logs

```bash
docker compose logs -f
```

To view logs for a specific service:

```bash
docker compose logs -f web
```

or

```bash
docker compose logs -f db
```

## Customization

### Environment Variables

You can customize the environment variables in your `.env` file. The Docker setup will use these variables, with the exception of the `DATABASE` setting which is overridden in the `docker compose.yml` file.

If you need to modify the database configuration, edit the `environment` section in the `docker compose.yml` file:

```yaml
environment:
  DATABASE: '{"ENGINE": "django.db.backends.mysql", "NAME": "cayuman", "USER": "cayuman", "PASSWORD": "cayuman_password", "HOST": "db", "PORT": "3306"}'
```

### Ports

If you need to change the exposed ports, modify the `ports` section in the `docker compose.yml` file:

```yaml
ports:
  - "custom_port:9000"  # For the web application
  - "custom_port:3306"  # For the database
```

## Troubleshooting

### Database Connection Issues

If the web application cannot connect to the database, check:

1. The database container is running:

   ```bash
   docker compose ps
   ```

2. The database credentials in the `docker compose.yml` file match the ones in the web application's settings.

3. The database has been properly initialized:

   ```bash
   docker compose logs db
   ```

### Web Application Issues

If the web application is not starting properly, check:

1. The logs for any errors:

   ```bash
   docker compose logs web
   ```

2. The environment variables are correctly set in your `.env` file and the `docker compose.yml` file.

3. The database connection is working properly.

### File Permission Issues

If you encounter permission issues with the mounted volumes:

1. Check the ownership of the files in the container:

   ```bash
   docker compose exec web ls -la /app
   ```

2. If needed, adjust permissions on your local machine:

   ```bash
   chmod -R 755 .
   ```
