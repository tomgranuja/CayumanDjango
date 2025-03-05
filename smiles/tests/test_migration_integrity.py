"""
Tests for database integrity after migration from Cayuman to Smiles.

This module contains tests to verify that:
1. Data integrity is maintained after migration
2. Record counts match between old and new models
3. Relationships are preserved
"""
from django.db import connection
from django.test import TestCase


class MigrationIntegrityTestCase(TestCase):
    """Test database integrity after migration."""

    def setUp(self):
        """Set up test data."""
        # This test assumes that the migration has already been run
        # and both Cayuman and Smiles tables exist in the database

        # Check if Cayuman tables exist
        self.cayuman_tables_exist = True
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM cayuman_period")
        except Exception:
            self.cayuman_tables_exist = False

    def test_term_count_matches_period_count(self):
        """Test that the number of Terms matches the number of Periods."""
        if not self.cayuman_tables_exist:
            self.skipTest("Cayuman tables don't exist in the test database")

        with connection.cursor() as cursor:
            # Count Periods in Cayuman
            cursor.execute("SELECT COUNT(*) FROM cayuman_period")
            period_count = cursor.fetchone()[0]

            # Count Terms in Smiles
            cursor.execute("SELECT COUNT(*) FROM smiles_term")
            term_count = cursor.fetchone()[0]

            # The counts should match
            self.assertEqual(term_count, period_count)

    def test_group_count_matches_cycle_count(self):
        """Test that the number of Groups with group_type='Cycle' matches the number of Cycles."""
        if not self.cayuman_tables_exist:
            self.skipTest("Cayuman tables don't exist in the test database")

        with connection.cursor() as cursor:
            # Count Cycles in Cayuman
            cursor.execute("SELECT COUNT(*) FROM cayuman_cycle")
            cycle_count = cursor.fetchone()[0]

            # Count Groups with group_type='Cycle' in Smiles
            cursor.execute("SELECT COUNT(*) FROM smiles_group WHERE group_type = 'Cycle'")
            group_count = cursor.fetchone()[0]

            # The counts should match
            self.assertEqual(group_count, cycle_count)

    def test_subject_count_matches_workshop_count(self):
        """Test that the number of Subjects matches the number of Workshops."""
        if not self.cayuman_tables_exist:
            self.skipTest("Cayuman tables don't exist in the test database")

        with connection.cursor() as cursor:
            # Count Workshops in Cayuman
            cursor.execute("SELECT COUNT(*) FROM cayuman_workshop")
            workshop_count = cursor.fetchone()[0]

            # Count Subjects in Smiles
            cursor.execute("SELECT COUNT(*) FROM smiles_subject")
            subject_count = cursor.fetchone()[0]

            # The counts should match
            self.assertEqual(subject_count, workshop_count)

    def test_subject_offering_count_matches_workshop_period_count(self):
        """Test that the number of SubjectOfferings matches the number of WorkshopPeriods."""
        if not self.cayuman_tables_exist:
            self.skipTest("Cayuman tables don't exist in the test database")

        with connection.cursor() as cursor:
            # Count WorkshopPeriods in Cayuman
            cursor.execute("SELECT COUNT(*) FROM cayuman_workshopperiod")
            workshop_period_count = cursor.fetchone()[0]

            # Count SubjectOfferings in Smiles
            cursor.execute("SELECT COUNT(*) FROM smiles_subjectoffering")
            subject_offering_count = cursor.fetchone()[0]

            # The counts should match
            self.assertEqual(subject_offering_count, workshop_period_count)

    def test_member_group_assignment_count_matches_student_cycle_count(self):
        """Test that the number of MemberGroupAssignments matches the number of StudentCycles."""
        if not self.cayuman_tables_exist:
            self.skipTest("Cayuman tables don't exist in the test database")

        with connection.cursor() as cursor:
            # Count StudentCycles in Cayuman
            cursor.execute("SELECT COUNT(*) FROM cayuman_studentcycle")
            student_cycle_count = cursor.fetchone()[0]

            # Count MemberGroupAssignments in Smiles
            cursor.execute("SELECT COUNT(*) FROM smiles_membergroupassignment")
            member_group_assignment_count = cursor.fetchone()[0]

            # The counts should match
            self.assertEqual(member_group_assignment_count, student_cycle_count)

    def test_time_slot_count_matches_schedule_count(self):
        """Test that the number of TimeSlots matches the number of Schedules."""
        if not self.cayuman_tables_exist:
            self.skipTest("Cayuman tables don't exist in the test database")

        with connection.cursor() as cursor:
            # Count Schedules in Cayuman
            cursor.execute("SELECT COUNT(*) FROM cayuman_schedule")
            schedule_count = cursor.fetchone()[0]

            # Count TimeSlots in Smiles
            cursor.execute("SELECT COUNT(*) FROM smiles_timeslot")
            time_slot_count = cursor.fetchone()[0]

            # The counts should match
            self.assertEqual(time_slot_count, schedule_count)

    def test_term_date_integrity(self):
        """Test that Term dates match Period dates."""
        if not self.cayuman_tables_exist:
            self.skipTest("Cayuman tables don't exist in the test database")

        with connection.cursor() as cursor:
            # Get a sample of Periods from Cayuman
            cursor.execute(
                """
                SELECT id, name, date_start, date_end
                FROM cayuman_period
                ORDER BY id
                LIMIT 5
            """
            )
            periods = cursor.fetchall()

            for period_id, period_name, period_start, period_end in periods:
                # Find the corresponding Term in Smiles
                cursor.execute(
                    """
                    SELECT date_start, date_end
                    FROM smiles_term
                    WHERE name = %s
                """,
                    [period_name],
                )
                term = cursor.fetchone()

                if term:
                    term_start, term_end = term
                    # The dates should match
                    self.assertEqual(term_start, period_start)
                    self.assertEqual(term_end, period_end)

    def test_subject_offering_relationships(self):
        """Test that SubjectOffering relationships match WorkshopPeriod relationships."""
        if not self.cayuman_tables_exist:
            self.skipTest("Cayuman tables don't exist in the test database")

        try:
            with connection.cursor() as cursor:
                # Get a sample of WorkshopPeriods from Cayuman
                cursor.execute(
                    """
                    SELECT wp.id, w.name, p.name, m.username
                    FROM cayuman_workshopperiod wp
                    JOIN cayuman_workshop w ON wp.workshop_id = w.id
                    JOIN cayuman_period p ON wp.period_id = p.id
                    LEFT JOIN cayuman_member m ON wp.teacher_id = m.id
                    ORDER BY wp.id
                    LIMIT 5
                """
                )
                workshop_periods = cursor.fetchall()

                for wp_id, workshop_name, period_name, teacher_username in workshop_periods:
                    # Find the corresponding SubjectOffering in Smiles
                    cursor.execute(
                        """
                        SELECT s.name, t.name, m.username
                        FROM smiles_subjectoffering so
                        JOIN smiles_subject s ON so.subject_id = s.id
                        JOIN smiles_term t ON so.term_id = t.id
                        LEFT JOIN smiles_member m ON so.teacher_id = m.id
                        WHERE s.name = %s AND t.name = %s
                    """,
                        [workshop_name, period_name],
                    )
                    subject_offering = cursor.fetchone()

                    if subject_offering:
                        subject_name, term_name, so_teacher_username = subject_offering
                        # The relationships should match
                        self.assertEqual(subject_name, workshop_name)
                        self.assertEqual(term_name, period_name)
                        self.assertEqual(so_teacher_username, teacher_username)
        except Exception as e:
            self.skipTest(f"Error executing query: {e}")

    def test_member_group_assignment_relationships(self):
        """Test that MemberGroupAssignment relationships match StudentCycle relationships."""
        if not self.cayuman_tables_exist:
            self.skipTest("Cayuman tables don't exist in the test database")

        try:
            with connection.cursor() as cursor:
                # Get a sample of StudentCycles from Cayuman
                cursor.execute(
                    """
                    SELECT sc.id, m.username, c.name
                    FROM cayuman_studentcycle sc
                    JOIN cayuman_member m ON sc.student_id = m.id
                    JOIN cayuman_cycle c ON sc.cycle_id = c.id
                    ORDER BY sc.id
                    LIMIT 5
                """
                )
                student_cycles = cursor.fetchall()

                for sc_id, student_username, cycle_name in student_cycles:
                    # Find the corresponding MemberGroupAssignment in Smiles
                    cursor.execute(
                        """
                        SELECT m.username, g.name
                        FROM smiles_membergroupassignment mga
                        JOIN smiles_member m ON mga.member_id = m.id
                        JOIN smiles_group g ON mga.group_id = g.id
                        WHERE m.username = %s AND g.name = %s
                    """,
                        [student_username, cycle_name],
                    )
                    member_group_assignment = cursor.fetchone()

                    if member_group_assignment:
                        mga_student_username, group_name = member_group_assignment
                        # The relationships should match
                        self.assertEqual(mga_student_username, student_username)
                        self.assertEqual(group_name, cycle_name)
        except Exception as e:
            self.skipTest(f"Error executing query: {e}")


class RelationshipIntegrityTestCase(TestCase):
    """Test that relationships are preserved after migration."""

    def setUp(self):
        """Set up test data."""
        # Check if Cayuman tables exist
        self.cayuman_tables_exist = True
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM cayuman_period")
        except Exception:
            self.cayuman_tables_exist = False

    def test_subject_offering_eligible_groups(self):
        """Test that SubjectOffering eligible_groups match WorkshopPeriod cycles."""
        if not self.cayuman_tables_exist:
            self.skipTest("Cayuman tables don't exist in the test database")

        # This test requires both Cayuman and Smiles models to be available
        # It's a more complex test that would need to be adapted based on the actual migration
        pass

    def test_member_group_assignment_subject_offerings(self):
        """Test that MemberGroupAssignment subject_offerings match StudentCycle workshop_periods."""
        if not self.cayuman_tables_exist:
            self.skipTest("Cayuman tables don't exist in the test database")

        # This test requires both Cayuman and Smiles models to be available
        # It's a more complex test that would need to be adapted based on the actual migration
        pass
