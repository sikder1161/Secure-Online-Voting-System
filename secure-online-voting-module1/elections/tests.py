import base64
import os
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Election, Candidate, VoterEligibility, VoterParticipation, EncryptedVote
from .services import cast_ballot
from accounts.models import VoterProfile, EmailVerification

User = get_user_model()


class Module2Tests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username='eadmin', email='eadmin@example.com', password='t', role='ELECTION_ADMIN')
        self.voter = User.objects.create_user(username='voter2', email='voter2@example.com', password='t', role='VOTER')
        self.election = Election.objects.create(
            title='Student Council', description='Demo',
            starts_at=timezone.now() - timedelta(minutes=5), ends_at=timezone.now() + timedelta(hours=1),
            status=Election.Status.SCHEDULED, created_by=self.admin_user,
        )
        # create candidate while draft: avoid bypassing candidate edit guard.
        self.candidate = Candidate.objects.create(election=self.election, name='Candidate A')
        VoterEligibility.objects.create(election=self.election, voter=self.voter, decision='APPROVED', reviewed_by=self.admin_user, reviewed_at=timezone.now())

    def test_invalid_election_times(self):
        election = Election(title='Invalid', starts_at=timezone.now(), ends_at=timezone.now() - timedelta(hours=1), created_by=self.admin_user)
        with self.assertRaises(ValidationError):
            election.full_clean()

    def test_candidate_changes_locked_after_start(self):
        candidate = Candidate(election=self.election, name='Unauthorized edit')
        with self.assertRaises(ValidationError):
            candidate.full_clean()

    def test_scheduled_election_candidate_cannot_be_edited_or_deleted(self):
        import time

        EmailVerification.objects.update_or_create(
            user=self.admin_user,
            defaults={
                'verified_email': self.admin_user.email,
                'verified_at': timezone.now(),
            },
        )
        self.client.force_login(self.admin_user)
        session = self.client.session
        session['email_otp_auth_user'] = self.admin_user.pk
        session['email_otp_auth_email'] = self.admin_user.email
        session['email_otp_auth_until'] = time.time() + 3600
        session.save()

        original_name = self.candidate.name
        original_information = self.candidate.information

        edit_response = self.client.post(
            reverse('elections:candidate_edit', kwargs={'pk': self.candidate.pk}),
            {'name': 'Changed Candidate', 'information': 'Changed information'},
        )
        self.assertEqual(edit_response.status_code, 403)

        delete_response = self.client.post(
            reverse('elections:candidate_remove', kwargs={'pk': self.candidate.pk}),
        )
        self.assertEqual(delete_response.status_code, 403)

        self.candidate.refresh_from_db()
        self.assertEqual(self.candidate.name, original_name)
        self.assertEqual(self.candidate.information, original_information)
        self.assertTrue(Candidate.objects.filter(pk=self.candidate.pk).exists())

    def test_invalid_candidate_rejected_without_participation(self):
        with patch.dict(os.environ, {'VOTE_ENCRYPTION_KEY': base64.urlsafe_b64encode(os.urandom(32)).decode()}):
            with self.assertRaises(ValidationError):
                cast_ballot(voter=self.voter, election_id=self.election.pk, candidate_id=999999)
        self.assertFalse(VoterParticipation.objects.exists())
        self.assertFalse(EncryptedVote.objects.exists())

    def test_candidate_from_different_election_rejected_without_records(self):
        other_election = Election.objects.create(
            title='Other Election',
            starts_at=timezone.now() + timedelta(hours=1),
            ends_at=timezone.now() + timedelta(hours=2),
            status=Election.Status.DRAFT,
            created_by=self.admin_user,
        )
        other_candidate = Candidate.objects.create(
            election=other_election,
            name='Candidate B',
        )

        profile, _ = VoterProfile.objects.get_or_create(
            user=self.voter, defaults={'institutional_id': 'VOTE-CROSS-ELECTION'}
        )
        profile.date_of_birth = date(2000, 1, 1)
        profile.verification_status = VoterProfile.Verification.APPROVED
        profile.save()
        EmailVerification.objects.update_or_create(
            user=self.voter,
            defaults={
                'verified_email': self.voter.email,
                'verified_at': timezone.now(),
            },
        )

        with patch.dict(os.environ, {'VOTE_ENCRYPTION_KEY': base64.urlsafe_b64encode(os.urandom(32)).decode()}):
            with self.assertRaises(ValidationError):
                cast_ballot(
                    voter=self.voter,
                    election_id=self.election.pk,
                    candidate_id=other_candidate.pk,
                )

        self.assertFalse(
            VoterParticipation.objects.filter(
                election=self.election,
                voter=self.voter,
            ).exists()
        )
        self.assertFalse(EncryptedVote.objects.filter(election=self.election).exists())

    def test_missing_key_fails_closed(self):
        with patch.dict(os.environ, {'VOTE_ENCRYPTION_KEY': ''}):
            with self.assertRaises(RuntimeError):
                cast_ballot(voter=self.voter, election_id=self.election.pk, candidate_id=self.candidate.pk)
        self.assertFalse(VoterParticipation.objects.exists())

    def test_duplicate_constraint_exists(self):
        names = {c.name for c in VoterParticipation._meta.constraints}
        self.assertIn('one_vote_per_voter_election', names)

    def test_voter_cannot_create_election(self):
     import time

    # Mark the test voter's email as verified.
     EmailVerification.objects.update_or_create(
        user=self.voter,
        defaults={
            'verified_email': self.voter.email,
            'verified_at': timezone.now(),
        },
    )

    # Authenticate the test voter.
     self.client.force_login(self.voter)

    # Simulate a successfully completed email OTP login.
     session = self.client.session
     session['email_otp_auth_user'] = self.voter.pk
     session['email_otp_auth_email'] = self.voter.email
     session['email_otp_auth_until'] = time.time() + 3600
     session.save()

    # A voter must not create an election.
     res = self.client.get('/elections/create/')
     self.assertEqual(res.status_code, 403)

    def test_one_encrypted_ballot_and_no_second_vote(self):
        # Setup the prerequisite Module 1 profile and verified email.
        profile, _ = VoterProfile.objects.get_or_create(
            user=self.voter, defaults={'institutional_id': 'VOTE-DEMO-2'}
        )
        profile.date_of_birth = date(2000, 1, 1)
        profile.verification_status = VoterProfile.Verification.APPROVED
        profile.save()
        EmailVerification.objects.update_or_create(
            user=self.voter,
            defaults={'verified_email': self.voter.email, 'verified_at': timezone.now()},
        )
        with patch.dict(os.environ, {'VOTE_ENCRYPTION_KEY': base64.urlsafe_b64encode(os.urandom(32)).decode()}):
            self.assertTrue(cast_ballot(voter=self.voter, election_id=self.election.pk, candidate_id=self.candidate.pk))
            self.assertEqual(VoterParticipation.objects.count(), 1)
            self.assertEqual(EncryptedVote.objects.count(), 1)
            ballot = EncryptedVote.objects.get()
            self.assertNotIn(str(self.candidate.pk).encode(), ballot.ciphertext)
            with self.assertRaises(ValidationError):
                cast_ballot(voter=self.voter, election_id=self.election.pk, candidate_id=self.candidate.pk)
        self.assertEqual(VoterParticipation.objects.count(), 1)
        self.assertEqual(EncryptedVote.objects.count(), 1)
