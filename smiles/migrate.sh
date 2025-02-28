#!/bin/bash

# Colors for better output
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default to development mode
ENVIRONMENT="dev"
CAYUMAN_MIGRATION=false
LOG_FILE="migration_$(date +%Y%m%d_%H%M%S).log"

# Parse command line arguments
for arg in "$@"
do
    case $arg in
        --prod)
        ENVIRONMENT="prod"
        shift
        ;;
        --cayuman)
        CAYUMAN_MIGRATION=true
        shift
        ;;
        *)
        # Unknown option
        ;;
    esac
done

# Header
echo -e "${BLUE}=============================================${NC}"
echo -e "${BLUE}          SMILES APP MIGRATION SCRIPT       ${NC}"
if [ "$ENVIRONMENT" == "prod" ]; then
    echo -e "${RED}          *** PRODUCTION MODE ***          ${NC}"
else
    echo -e "${GREEN}          *** DEVELOPMENT MODE ***        ${NC}"
fi
if [ "$CAYUMAN_MIGRATION" == true ]; then
    echo -e "${YELLOW}      *** CAYUMAN MIGRATION ENABLED ***   ${NC}"
fi
echo -e "${BLUE}=============================================${NC}"
echo ""

# Setup logging
exec > >(tee -i $LOG_FILE)
exec 2>&1

echo "Starting migration process at $(date)"
echo "Environment: $ENVIRONMENT"
echo "Cayuman migration: $CAYUMAN_MIGRATION"
echo ""

# Function to run command in development environment (Docker)
run_dev() {
    docker compose exec web poetry run $@
}

# Function to run command in production environment
run_prod() {
    poetry run $@
}

# Function to run appropriate command based on environment
run_cmd() {
    if [ "$ENVIRONMENT" == "prod" ]; then
        run_prod $@
    else
        run_dev $@
    fi
}

# Check Django app configuration
check_app_config() {
    echo -e "${YELLOW}Checking Django app configuration...${NC}"

    # Python script to check app configuration
    CHECK_CONFIG_SCRIPT='
import os
import sys
import django

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cayuman.settings")
django.setup()

try:
    from django.apps import apps
    smiles_app = apps.get_app_config("smiles")
    print(f"Smiles app is registered successfully: {smiles_app.name}")
    sys.exit(0)
except Exception as e:
    print(f"ERROR: {str(e)}")
    sys.exit(1)
'

    # Run the configuration check
    if [ "$ENVIRONMENT" == "prod" ]; then
        python -c "$CHECK_CONFIG_SCRIPT"
    else
        docker compose exec web bash -c "cat > /tmp/check_config.py << 'EOF'
$CHECK_CONFIG_SCRIPT
EOF
poetry run python /tmp/check_config.py"
    fi

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Django app configuration verified!${NC}"
        return 0
    else
        echo -e "${RED}Django app configuration issue detected!${NC}"
        echo -e "${YELLOW}Please check that smiles app is properly configured in INSTALLED_APPS${NC}"
        echo -e "${YELLOW}and that smiles/apps.py exists with the SmilesConfig class.${NC}"
        return 1
    fi
}

# Check environment and prerequisites
if [ "$ENVIRONMENT" == "dev" ]; then
    # Check if Docker is running
    echo -e "${YELLOW}Checking if Docker is running...${NC}"
    if ! docker info > /dev/null 2>&1; then
        echo -e "${RED}Error: Docker is not running or not accessible${NC}"
        echo -e "${YELLOW}Please start Docker and try again${NC}"
        exit 1
    fi
    echo -e "${GREEN}Docker is running!${NC}"
    echo ""

    # Check if the web container is running
    echo -e "${YELLOW}Checking if web container is running...${NC}"
    if ! docker compose ps | grep -q -E "web.+Up [0-9]+"; then
        echo -e "${RED}Error: Web container is not running${NC}"
        echo -e "${YELLOW}Starting containers with docker compose up -d...${NC}"
        docker compose up -d

        echo -e "${YELLOW}Waiting for containers to be ready...${NC}"
        sleep 5
    fi
    echo -e "${GREEN}Web container is running!${NC}"
    echo ""
else
    # Check if we're in a virtual environment (production should use one)
    if [ -z "$VIRTUAL_ENV" ]; then
        echo -e "${YELLOW}Warning: No active virtual environment detected${NC}"
        echo -e "${YELLOW}It's recommended to run this script within a virtual environment in production${NC}"
        read -p "Continue anyway? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        echo -e "${GREEN}Using virtual environment: $VIRTUAL_ENV${NC}"
    fi
    echo ""

    # Check if Django is installed
    echo -e "${YELLOW}Checking Django installation...${NC}"
    if ! python -c "import django" &> /dev/null; then
        echo -e "${RED}Error: Django is not installed${NC}"
        echo -e "${YELLOW}Please install project dependencies and try again${NC}"
        exit 1
    fi
    echo -e "${GREEN}Django is installed!${NC}"
    echo ""
fi

# Check app configuration
check_app_config || exit 1

# Step 1: Show current migration status
echo -e "${YELLOW}Current migration status:${NC}"
run_cmd python manage.py showmigrations smiles
echo ""

# Step 2: Make migrations if there are any pending model changes
if [ "$CAYUMAN_MIGRATION" == false ]; then
    echo -e "${YELLOW}Checking for model changes...${NC}"
    run_cmd python manage.py makemigrations smiles
    echo -e "${GREEN}Model changes checked!${NC}"
    echo ""
else
    echo -e "${YELLOW}Skipping makemigrations as we're running Cayuman migration${NC}"
    echo ""
fi

# Step 3: Apply migrations
echo -e "${YELLOW}Applying migrations...${NC}"
if run_cmd python manage.py migrate smiles; then
    echo -e "${GREEN}Migrations applied successfully!${NC}"
else
    echo -e "${RED}Error applying migrations${NC}"
    echo -e "${YELLOW}You may need to fix issues before retrying${NC}"
    exit 1
fi
echo ""

# Step 4: Verify migrations were applied
echo -e "${YELLOW}Verifying migrations...${NC}"
run_cmd python manage.py showmigrations smiles
echo -e "${GREEN}Verification complete!${NC}"
echo ""

# Step 5: Verify Cayuman migration if enabled
if [ "$CAYUMAN_MIGRATION" == true ]; then
    echo -e "${YELLOW}Running Cayuman to Smiles migration verification...${NC}"

    # Create the Python verification script to check migration counts
    VERIFICATION_SCRIPT='
import os
import sys
import django
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cayuman.settings")
django.setup()

try:
    from django.apps import apps

    # Check counts of migrated models
    Group = apps.get_model("smiles", "Group")
    Subject = apps.get_model("smiles", "Subject")
    Term = apps.get_model("smiles", "Term")
    TimeSlot = apps.get_model("smiles", "TimeSlot")
    SubjectOffering = apps.get_model("smiles", "SubjectOffering")
    MemberGroupAssignment = apps.get_model("smiles", "MemberGroupAssignment")
    Event = apps.get_model("smiles", "Event")
    Activity = apps.get_model("smiles", "Activity")
    ScheduleTemplate = apps.get_model("smiles", "ScheduleTemplate")
    ScheduleAssignment = apps.get_model("smiles", "ScheduleAssignment")

    # And original models for comparison
    Cycle = apps.get_model("cayuman", "Cycle")
    Workshop = apps.get_model("cayuman", "Workshop")
    Period = apps.get_model("cayuman", "Period")
    Schedule = apps.get_model("cayuman", "Schedule")
    WorkshopPeriod = apps.get_model("cayuman", "WorkshopPeriod")
    StudentCycle = apps.get_model("cayuman", "StudentCycle")

    # Compare record counts
    logger.info("Verifying migration results...")

    cycle_count = Cycle.objects.count()
    group_count = Group.objects.filter(group_type="Cycle").count()
    logger.info(f"Cycles: {cycle_count} → Groups: {group_count}")

    workshop_count = Workshop.objects.count()
    subject_count = Subject.objects.filter(type__name="Workshop").count()
    logger.info(f"Workshops: {workshop_count} → Subjects: {subject_count}")

    period_count = Period.objects.count()
    term_count = Term.objects.filter(term_type="Workshop Period").count()
    logger.info(f"Periods: {period_count} → Terms: {term_count}")

    schedule_count = Schedule.objects.count()
    timeslot_count = TimeSlot.objects.count()
    logger.info(f"Schedules: {schedule_count} → TimeSlots: {timeslot_count}")

    wp_count = WorkshopPeriod.objects.count()
    so_count = SubjectOffering.objects.count()
    logger.info(f"WorkshopPeriods: {wp_count} → SubjectOfferings: {so_count}")

    sc_count = StudentCycle.objects.count()
    mga_count = MemberGroupAssignment.objects.filter(group__group_type="Cycle").count()
    logger.info(f"StudentCycles: {sc_count} → MemberGroupAssignments: {mga_count}")

    event_count = Event.objects.count()
    logger.info(f"Events created: {event_count}")

    enrollment_event_count = Event.objects.filter(type__name="Enrollment").count()
    logger.info(f"Enrollment events: {enrollment_event_count}")

    activity_count = Activity.objects.filter(type__name="Workshop Session").count()
    logger.info(f"Workshop activities: {activity_count}")

    template_count = ScheduleTemplate.objects.count()
    logger.info(f"Schedule templates: {template_count}")

    assignment_count = ScheduleAssignment.objects.count()
    logger.info(f"Schedule assignments: {assignment_count}")

    # Check for any issues with integrity
    if any([
        cycle_count != group_count,
        workshop_count != subject_count,
        period_count != term_count,
        schedule_count != timeslot_count,
        wp_count != so_count,
        sc_count != mga_count
    ]):
        logger.warning("DATA COUNT MISMATCH DETECTED. Migration may be incomplete.")
        sys.exit(1)
    else:
        logger.info("MIGRATION VERIFICATION COMPLETE. All record counts match.")
        sys.exit(0)

except Exception as e:
    logger.error(f"An error occurred during migration verification: {str(e)}")
    sys.exit(1)
'

    # Run the verification script
    if [ "$ENVIRONMENT" == "prod" ]; then
        echo -e "${YELLOW}Running verification in production environment...${NC}"
        python -c "$VERIFICATION_SCRIPT"
    else
        echo -e "${YELLOW}Running verification in development environment...${NC}"
        docker compose exec web bash -c "cat > /tmp/verify_migration.py << 'EOF'
$VERIFICATION_SCRIPT
EOF
poetry run python /tmp/verify_migration.py"
    fi

    # Check the verification result
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Cayuman migration verification passed!${NC}"
    else
        echo -e "${RED}Cayuman migration verification failed!${NC}"
        echo -e "${YELLOW}Please check the logs for details and fix any issues.${NC}"
    fi
    echo ""
fi

# Step 6: Run a data integrity check
echo -e "${YELLOW}Running data integrity check...${NC}"

# Create the Python integrity check script
INTEGRITY_CHECK_SCRIPT='
import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cayuman.settings")
django.setup()
from smiles.models import MemberGroupAssignment, SubjectOffering, Event, Term, Subject, Activity

# Print key statistics
print(MemberGroupAssignment.objects.count())  # Line 1: Assignment count
print(SubjectOffering.objects.count())       # Line 2: Offering count
print(Event.objects.filter(type__name="Enrollment").count())  # Line 3: Enrollment events
print(Term.objects.count())                  # Line 4: Terms
print(Subject.objects.filter(type__name="Workshop").count())  # Line 5: Workshop subjects
print(Activity.objects.filter(type__name="Workshop Session").count())  # Line 6: Workshop activities
'

# Run the integrity check based on environment
if [ "$ENVIRONMENT" == "prod" ]; then
    COUNTS=$(python -c "$INTEGRITY_CHECK_SCRIPT")
    ASSIGNMENT_COUNT=$(echo "$COUNTS" | sed -n '1p')
    OFFERING_COUNT=$(echo "$COUNTS" | sed -n '2p')
    ENROLLMENT_COUNT=$(echo "$COUNTS" | sed -n '3p')
    TERM_COUNT=$(echo "$COUNTS" | sed -n '4p')
    WORKSHOP_COUNT=$(echo "$COUNTS" | sed -n '5p')
    ACTIVITY_COUNT=$(echo "$COUNTS" | sed -n '6p')
else
    COUNTS=$(docker compose exec web bash -c "cat > /tmp/integrity_check.py << 'EOF'
$INTEGRITY_CHECK_SCRIPT
EOF
poetry run python /tmp/integrity_check.py")
    ASSIGNMENT_COUNT=$(echo "$COUNTS" | sed -n '1p')
    OFFERING_COUNT=$(echo "$COUNTS" | sed -n '2p')
    ENROLLMENT_COUNT=$(echo "$COUNTS" | sed -n '3p')
    TERM_COUNT=$(echo "$COUNTS" | sed -n '4p')
    WORKSHOP_COUNT=$(echo "$COUNTS" | sed -n '5p')
    ACTIVITY_COUNT=$(echo "$COUNTS" | sed -n '6p')
fi

echo -e "${BLUE}MemberGroupAssignment records: ${ASSIGNMENT_COUNT}${NC}"
echo -e "${BLUE}SubjectOffering records: ${OFFERING_COUNT}${NC}"
echo -e "${BLUE}Enrollment Events: ${ENROLLMENT_COUNT}${NC}"
echo -e "${BLUE}Terms: ${TERM_COUNT}${NC}"
echo -e "${BLUE}Workshop Subjects: ${WORKSHOP_COUNT}${NC}"
echo -e "${BLUE}Workshop Activities: ${ACTIVITY_COUNT}${NC}"

# Check if data is present
if [ -n "$ASSIGNMENT_COUNT" ] && [ -n "$OFFERING_COUNT" ] && [ -n "$ENROLLMENT_COUNT" ] && \
   [ "$ASSIGNMENT_COUNT" -gt 0 ] && [ "$OFFERING_COUNT" -gt 0 ] && [ "$ENROLLMENT_COUNT" -gt 0 ]; then
    echo -e "${GREEN}Data integrity check passed!${NC}"
else
    echo -e "${YELLOW}Warning: Some data may not have been migrated correctly.${NC}"
    echo -e "${YELLOW}Please review the migration logs for errors.${NC}"
fi
echo ""

# Done
echo -e "${BLUE}=============================================${NC}"
echo -e "${GREEN}Migration process completed!${NC}"
echo -e "${BLUE}Migration log saved to: ${LOG_FILE}${NC}"
echo -e "${BLUE}=============================================${NC}"
