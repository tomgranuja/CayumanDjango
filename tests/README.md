# Test Fixtures

This document describes the test fixtures available in the Cayuman test suite. All these fixtures are defined in `conftest.py` and are available globally to all tests.

## User Fixtures

### `create_superuser`

Creates a superuser with admin privileges.

```python
def test_something(create_superuser):
    admin = create_superuser
    assert admin.is_superuser
    assert admin.username == "admin"
```

### `create_staff`

Creates a staff user (non-superuser).

```python
def test_something(create_staff):
    staff = create_staff
    assert staff.is_staff
    assert not staff.is_superuser
```

### `create_student`

Creates a student user and adds them to the students group.

```python
def test_something(create_student):
    student = create_student
    assert student.is_student  # Via group membership
```

### `create_teacher`

Creates a teacher user and adds them to the teachers group.

```python
def test_something(create_teacher):
    teacher = create_teacher
    assert teacher.is_teacher  # Via group membership
```

### `create_inactive_user`

Creates an inactive user for testing access restrictions.

```python
def test_something(create_inactive_user):
    user = create_inactive_user
    assert not user.is_active
```

### `create_groups`

Creates both student and teacher groups. Usually not needed directly as it's used by other fixtures.

```python
def test_something(create_groups):
    students_group, teachers_group = create_groups
    assert students_group.name == settings.STUDENTS_GROUP
```

## Period Fixtures

### `create_period`

Creates a test period with configurable dates. Can be used in two ways:

1. Default usage - uses predefined dates in 2025:

```python
def test_something(create_period):
    period = create_period
    assert period.name == "Test Period"
```

2. With custom dates via parametrization:

```python
@pytest.mark.parametrize('create_period', [{
    'preview_date': '2024-01-01',
    'enrollment_start': '2024-01-03',
    'enrollment_end': '2024-01-10',
    'date_start': '2024-01-15',
    'date_end': '2024-02-15'
}], indirect=True)
def test_something(create_period):
    assert period.date_start == date(2024, 1, 15)
```

The fixture automatically:

- Creates the period in the database
- Mocks `Period.objects.current_or_last()` to return this period
- Mocks `period.is_in_the_past()` to return `True` by default

## Request Mocking Fixtures

### `mock_request`

Creates a mock request object for testing middleware and views. Includes:

- Basic request attributes
- Message framework support
- Period handling support

```python
def test_something(mock_request):
    mock_request.path_info = "/some/path"
    mock_request.user = some_user
    # Test your view/middleware
```

### `middleware`

Creates an instance of `CayumanMiddleware` with a mock `get_response`.

```python
def test_something(middleware, mock_request):
    response = middleware(mock_request)
    # Test middleware behavior
```

## Helper Classes

### `MockRequest`

Base class for request mocking. Provides:

- Attribute access via `__getattr__`/`__setattr__`
- Message framework support
- Default anonymous user
- Path info handling

### `MockMessageStorage`

Mock storage for Django's message framework. Used internally by `MockRequest`.
