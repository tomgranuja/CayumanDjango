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
