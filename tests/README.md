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

### `create_user`

Creates a basic user without any special permissions.

```python
def test_something(create_user):
    user = create_user
    assert user.username == "11111111"
```

### `create_groups`

Creates both student and teacher groups. Usually not needed directly as it's used by other fixtures.

```python
def test_something(create_groups):
    students_group, teachers_group = create_groups
    assert students_group.name == settings.STUDENTS_GROUP
```

## Authenticated Client Fixtures

### `client_authenticated_superuser`

Returns a client logged in as a superuser.

```python
def test_something(client_authenticated_superuser):
    response = client_authenticated_superuser.get('/admin/')
    assert response.status_code == 200
```

### `client_authenticated_staff`

Returns a client logged in as a staff user.

```python
def test_something(client_authenticated_staff):
    response = client_authenticated_staff.get('/admin/')
    assert response.status_code == 403  # Staff without permissions
```

### `client_authenticated_teacher`

Returns a client logged in as a teacher.

```python
def test_something(client_authenticated_teacher):
    response = client_authenticated_teacher.get('/some/teacher/view/')
    assert response.status_code == 200
```

### `client_authenticated_student`

Returns a client logged in as a student.

```python
def test_something(client_authenticated_student):
    response = client_authenticated_student.get('/some/student/view/')
    assert response.status_code == 200
```

## Period and Schedule Fixtures

### `create_period`

Creates a test period with fixed dates:

- date_start: 2023-01-01
- date_end: 2023-12-31
- enrollment_start: 2022-12-23
- enrollment_end: 2022-12-27

```python
def test_something(create_period):
    period = create_period
    assert period.name == "Period 1"
```

### `create_schedule`

Creates a schedule for Monday from 10:15 to 11:15.

```python
def test_something(create_schedule):
    schedule = create_schedule
    assert schedule.day == "Monday"
```

## Workshop Fixtures

### `create_workshops`

Creates three sample workshops: Fractangulos, Comics, and Ingles.

```python
def test_something(create_workshops):
    workshops = create_workshops
    assert len(workshops) == 3
```

### `create_cycles`

Creates three sample cycles: Avellanos, Ulmos, and Canelos.

```python
def test_something(create_cycles):
    cycles = create_cycles
    assert len(cycles) == 3
```

## Request Mocking Fixtures

### `mock_request`

Creates a request object with session and message support for testing middleware.

```python
def test_something(mock_request):
    mock_request.user = some_user
    # Test your view/middleware with full session and message support
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
