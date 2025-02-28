# Migration Plan: Cayuman to Smiles

This document outlines the comprehensive plan for migrating functionality from the Cayuman application to Smiles. The migration will reuse the existing Member model in Smiles and integrate all the workshop enrollment functionality from Cayuman.

## 1. Model Mapping and Integration

Before implementing views and templates, we need to map the Cayuman models to their corresponding Smiles models or create new ones within Smiles.

### Model Equivalents

| Cayuman Model | Smiles Equivalent/Action |
|---------------|--------------------------|
| Member | Use existing Member in smiles/models.py |
| Workshop | Map to Subject or create Workshop subclass of Subject |
| Schedule | Map to TimeSlot model |
| Period | Map to Term model |
| Cycle | Map to Group model (group_type="Cycle") |
| WorkshopPeriod | Map to SubjectOffering model |
| StudentCycle | Create new MemberGroupAssignment with enrollment data |
| Period.enrollment_start/end | Map to Event model (type="Enrollment") |

### Model Descriptions

#### Core Models
1. **BaseModel**: Abstract base model providing common fields (created_at, updated_at) for all models.

2. **Member**: Extends Django's User model with additional properties for student/teacher roles and current cycle information.

3. **Group**: Represents any type of grouping in the school (grades, cycles, teams, etc.). Replaces Cayuman's Cycle model, using group_type="Cycle" for workshop cycles.
   - Key fields: name, group_type, description, is_primary, properties (JSON), metadata (JSON), parent (self-reference)

4. **Term**: Replaces Period model, representing specific time periods in the school calendar (semesters, quarters, workshop periods).
   - Key fields: name, term_type, description, has_enrollment_period, date_start, date_end, metadata (JSON with enrollment_periods)
   - Methods for checking if term is current, in past/future, enabled for preview/enrollment

5. **SubjectType**: Defines types of subjects offered (Workshop, Academic, etc.) with properties specific to each type.
   - Key fields: name, description, is_selectable, properties (JSON)

6. **Subject**: Replaces Workshop model, representing specific subjects taught at school.
   - Key fields: name, type (FK to SubjectType), description, metadata (JSON)

7. **SubjectOffering**: Replaces WorkshopPeriod, representing a specific offering of a subject during a term.
   - Key fields: subject, term, teacher, max_students, eligible_groups (M2M), enrollment_event (FK to Event)
   - Methods for counting students, calculating remaining quota, checking enrollment status

#### Schedule Models
8. **TimeSlot**: Replaces Schedule model, representing recurring time slots in the weekly schedule.
   - Key fields: name, day_of_week, time_start, time_end, metadata (JSON)
   - Includes validation to prevent overlapping time slots on the same day

9. **ActivityType**: Defines types of activities that can be scheduled (Class Session, Lunch, etc.).
   - Key fields: name, description, is_selectable, requires_attendance, metadata (JSON)

10. **Activity**: Represents a specific activity that can be scheduled, linked to a subject offering.
    - Key fields: name, type (FK to ActivityType), description, subject_offering (FK), applicable_groups (M2M)

11. **ScheduleTemplate**: Defines templates for schedules that can be applied to groups.
    - Key fields: name, description, applicable_groups (M2M), applicable_terms (M2M)

12. **ScheduleAssignment**: Maps time slots to activities within a schedule template.
    - Key fields: template (FK), time_slot (FK), activity (FK)

13. **MemberSchedule**: Represents an individual member's schedule for a term.
    - Key fields: member (FK), term (FK), template (FK), is_custom

14. **MemberScheduleOverride**: Represents an override to a member's schedule.
    - Key fields: member_schedule (FK), date, time_slot (FK), activity (FK), reason

15. **SpecialDay**: Represents a special day in the school calendar that may override regular schedules.
    - Key fields: name, date, affects_groups (M2M), is_school_closed, alternate_schedule (FK)

#### Enrollment Models
16. **MemberGroupAssignment**: Replaces StudentCycle, associating a member with a group and tracking enrollment.
    - Key fields: member (FK), group (FK), date_assigned, subject_offerings (M2M), is_active
    - Methods for getting subject offerings by time slot/term, checking if schedule is full

17. **Attendance**: Tracks attendance for scheduled activities.
    - Key fields: member (FK), date, time_slot (FK), activity (FK), attended, early_dismissal_time, late_arrival_time

#### Event Models
18. **EventType**: Defines types of events in the academic calendar (Enrollment, Evaluation, etc.).
    - Key fields: name, description, metadata (JSON)

19. **Event**: New model replacing Period's enrollment functionality, representing scheduled events.
    - Key fields: name, type (FK), term (FK), preview_date, date_start, date_end, affects_groups (M2M), affects_subjects (M2M), is_active
    - Methods for checking if event is current, if preview/enrollment is enabled

20. **EnrollmentService**: Service class for handling enrollment-related operations.
    - Methods for getting available offerings, checking if a member can enroll

### Additional Model Work

1. **Add Required Fields**:
   - Add necessary fields to SubjectOffering to match WorkshopPeriod functionality
   - Ensure TimeSlot has the same time constraint validation as Schedule

2. **Cache Mechanisms**:
   - Implement the caching strategies from Cayuman in the Smiles models
   - Move the `@lru_cache` decorators and cache clearing signals

3. **Custom Methods**:
   - Add necessary methods to Member, Group, and SubjectOffering classes
   - Ensure all functionality from Cayuman models is preserved

## 2. View Implementation

Implement views to replace all Cayuman functionality:

### Core Views

1. **Workshop Listing/Dashboard**:
   ```python
   # Create equivalent of cayuman's workshop listing in smiles/views.py
   def workshop_dashboard(request):
       # Implement logic to show available workshops
       # Consider current period, user's cycle, etc.
   ```

2. **Workshop Enrollment**:
   ```python
   def enroll_workshop(request, offering_id):
       # Implement the enrollment logic
       # Include validation, quota checking, etc.
   ```

3. **Schedule Views**:
   ```python
   def student_schedule(request, member_id=None):
       # Display a student's current workshop schedule
       # Include options to modify if applicable
   ```

4. **Admin Views**:
   - Workshop management
   - Period/Term management
   - Enrollment statistics and reporting

### Implementation Process

1. Analyze each view in Cayuman to understand its:
   - Core functionality
   - Required models
   - Permissions and access controls
   - Business logic and validation

2. Reimplement using:
   - Smiles models
   - Django class-based views where appropriate
   - The same permission structure

3. Create a mapping document for each view:
   ```
   Cayuman View: workshop_list
   Smiles Equivalent: subject_offerings
   Models Required: SubjectOffering, Member, Term
   Template: workshops/list.html
   Notes: Add filtering for workshop-type subjects
   ```

## 3. Template Reimplementation

### Template Structure

Create a parallel template structure in Smiles:

```
smiles/templates/
├── workshops/
│   ├── dashboard.html
│   ├── enrollment.html
│   ├── details.html
│   └── schedule.html
├── admin/
│   ├── workshop_management.html
│   ├── enrollment_stats.html
│   └── period_management.html
└── includes/
    ├── workshop_card.html
    ├── schedule_block.html
    └── enrollment_form.html
```

### Implementation Steps

1. **Copy and Adapt**:
   - Begin with Cayuman templates
   - Modify to use Smiles models and terminology
   - Update URL references

2. **Consolidate Template Tags**:
   - Move custom template tags from Cayuman to Smiles
   - Update for new model structure

3. **Style Integration**:
   - Ensure CSS classes are compatible
   - Adapt to Smiles styling conventions

4. **Mobile Responsiveness**:
   - Verify all templates work on mobile devices
   - Test across different screen sizes

## 4. URL Configuration

1. Create equivalent URL patterns in Smiles:
   ```python
   # smiles/urls.py
   urlpatterns = [
       path('workshops/', views.workshop_list, name='workshop_list'),
       path('workshops/<int:workshop_id>/', views.workshop_detail, name='workshop_detail'),
       path('enrollment/<int:offering_id>/', views.enroll_workshop, name='enroll_workshop'),
       path('schedule/', views.student_schedule, name='student_schedule'),
       # Admin URLs
       path('admin/workshops/', views.admin_workshop_list, name='admin_workshop_list'),
       # etc.
   ]
   ```

2. Update references in templates and views
3. Implement redirects for old Cayuman URLs if needed

## 5. Data Migration

### Migration Strategy

1. **Create Data Migration Files**:
   ```bash
   python manage.py makemigrations smiles --empty --name=migrate_from_cayuman
   ```

2. **Implement Forward Migration**:
   ```python
   def migrate_workshops(apps, schema_editor):
       # Get models from both apps
       OldWorkshop = apps.get_model('cayuman', 'Workshop')
       NewSubject = apps.get_model('smiles', 'Subject')
       SubjectType = apps.get_model('smiles', 'SubjectType')

       # Get or create workshop subject type
       workshop_type, _ = SubjectType.objects.get_or_create(
           name='Workshop',
           is_selectable=True
       )

       # Migrate each workshop
       for old_workshop in OldWorkshop.objects.all():
           NewSubject.objects.create(
               name=old_workshop.name,
               type=workshop_type,
               description=old_workshop.description,
               metadata={'full_name': old_workshop.full_name}
           )
   ```

3. **Migration Order**:
   1. First migrate supporting data (Cycles → Groups, Periods → Terms)
   2. Then migrate core entities (Workshops → Subjects)
   3. Finally migrate relationships (WorkshopPeriod → SubjectOffering, StudentCycle → MemberGroupAssignment)

### Testing Migration

1. Create a test environment with a copy of production data
2. Run migrations and validate:
   - Record counts match between old and new models
   - Sample records have correct data
   - Relationships are preserved

3. Verify application functionality with migrated data

## 6. Implementation Timeline

1. **Phase 1: Model Preparation (Week 1)**
   - Complete model mapping
   - Add necessary fields to Smiles models
   - Implement required methods

2. **Phase 2: Core Views and Templates (Weeks 2-3)**
   - Implement dashboard and listing views
   - Create enrollment functionality
   - Develop schedule views

3. **Phase 3: Admin Interface (Week 4)**
   - Implement admin views
   - Create management interfaces
   - Develop reporting tools

4. **Phase 4: Data Migration (Week 5)**
   - Create migration scripts
   - Test in staging environment
   - Validate data integrity

5. **Phase 5: Testing and Deployment (Week 6)**
   - Comprehensive testing
   - User acceptance testing
   - Production deployment

## 7. Validation and Quality Assurance

### Testing Procedures

1. **Unit Tests**:
   - Create tests for all new models and views
   - Verify business logic works as expected

2. **Functional Tests**:
   - Test enrollment process end-to-end
   - Verify schedule display is correct
   - Test period transitions

3. **Performance Testing**:
   - Test with production-scale data
   - Verify cache mechanisms work efficiently

### Acceptance Criteria

1. All functionality from Cayuman is available in Smiles
2. Data migration is complete with no loss of information
3. Performance is equal to or better than the original implementation
4. User experience is improved or maintained

## 8. Rollback Plan

In case issues arise after migration:

1. Keep Cayuman code and database tables available
2. Implement feature flags to switch between implementations
3. Prepare database rollback scripts

## 9. Documentation

1. Update all documentation to reflect new structure
2. Create new user guides for affected functionality
3. Document model relationships and key architectural decisions
