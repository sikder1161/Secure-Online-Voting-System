import base64
import os
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
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

    def test_invalid_candidate_rejected_without_participation(self):
        with patch.dict(os.environ, {'VOTE_ENCRYPTION_KEY': base64.urlsafe_b64encode(os.urandom(32)).decode()}):
            with self.assertRaises(ValidationError):
                cast_ballot(voter=self.voter, election_id=self.election.pk, candidate_id=999999)
        self.assertFalse(VoterParticipation.objects.exists())
        self.assertFalse(EncryptedVote.objects.exists())

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
        from datetime import date
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
