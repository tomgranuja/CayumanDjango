# Caching in the Smiles App

This document describes the caching strategy used in the Smiles application to optimize performance.

## Overview

The Smiles app uses Python's `functools.lru_cache` decorator to cache the results of expensive method calls. This helps reduce database queries and computation time for frequently accessed data.

## Cached Methods

### Term Model and TermService

- `TermService.current()`: Caches the current term to avoid repeated database queries.
- `TermService.current_or_last()`: Caches the current or last term.
- `TermService.get_term_by_date()`: Caches term lookups by date.
- `TermService.other_terms()`: Caches the list of terms other than the current one.

### MemberGroupAssignment Model

- `subject_offerings_by_time_slot()`: Caches the mapping of time slots to subject offerings for a member's group assignment. This is an expensive operation that involves multiple database queries across related models.
- `subject_offerings_by_term()`: Caches the set of subject offerings for a member in a specific term.
- `is_schedule_full()`: Caches the result of checking if a member's schedule is full for a given term, which requires counting time slots and comparing with enrolled offerings.

## Cache Clearing

Caches are cleared in two ways:

1. **Model save() methods**: When a model instance is saved, its own caches are cleared.
2. **Signal handlers**: When related models change, signal handlers clear the caches of affected models.

### Signal Handlers

The following signal handlers are implemented in `signals.py`:

- `clear_term_caches`: Clears Term-related caches when a Term is saved or deleted.
- `clear_member_group_assignment_caches`: Clears MemberGroupAssignment caches when the subject_offerings many-to-many relationship changes.
- `clear_subject_offering_caches`: Clears caches of MemberGroupAssignments when a SubjectOffering is saved.
- `clear_time_slot_caches`: Clears caches of MemberGroupAssignments when a TimeSlot is saved.

## Cache Sizes

All caches use `maxsize=None`, which means there is no limit to the number of entries that can be stored in the cache. This is appropriate for our use case because:

1. The number of terms, groups, and subject offerings is relatively small.
2. The caches are cleared when the underlying data changes.
3. The memory usage is negligible compared to the performance benefits.

## Performance Considerations

The caching strategy significantly improves performance for operations that:

1. Are called frequently (e.g., checking if a term is current).
2. Involve complex queries across multiple related models (e.g., finding subject offerings by time slot).
3. Require expensive calculations (e.g., checking if a schedule is full).

## Testing

The caching implementation should be tested to ensure:

1. Cache hits occur as expected.
2. Caches are properly cleared when data changes.
3. Performance improvements are measurable.

Test cases for cache clearing are available in the test suite.
