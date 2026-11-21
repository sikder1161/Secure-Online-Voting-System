"""Security-critical voting operations. No plaintext choices are persisted."""
import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Candidate, Election, VoterEligibility, VoterParticipation, EncryptedVote


def ballot_cipher():
    encoded = os.environ.get('VOTE_ENCRYPTION_KEY', '')
    if not encoded:
        raise RuntimeError('VOTE_ENCRYPTION_KEY is not configured: voting is disabled.')
    try:
        key = base64.urlsafe_b64decode(encoded)
    except Exception as exc:
        raise RuntimeError('Invalid VOTE_ENCRYPTION_KEY encoding.') from exc
    if len(key) != 32:
        raise RuntimeError('VOTE_ENCRYPTION_KEY must encode exactly 32 bytes.')
    return AESGCM(key)


def basic_eligibility(voter):
    if not voter.is_active or voter.role != voter.Role.VOTER:
        return False
    try:
        return bool(voter.voter_profile.can_vote)
    except (AttributeError, ObjectDoesNotExist):
        return False


def cast_ballot(*, voter, election_id, candidate_id):
    """Atomically record one participation and one anonymous encrypted ballot."""
    # Initialization happens before any write; invalid/missing key means fail closed.
    cipher = ballot_cipher()
    try:
        with transaction.atomic():
            election = Election.objects.select_for_update().get(pk=election_id)
            if not election.is_open:
                raise ValidationError('This election is not accepting votes.')
            if not basic_eligibility(voter):
                raise ValidationError('Your voter account does not have basic approval.')
            approved = VoterEligibility.objects.filter(
                election=election, voter=voter, decision=VoterEligibility.Decision.APPROVED
            ).exists()
            if not approved:
                raise ValidationError('You are not approved for this specific election.')
            if not Candidate.objects.filter(pk=candidate_id, election=election).exists():
                raise ValidationError('Invalid candidate for this election.')
            if VoterParticipation.objects.filter(election=election, voter=voter).exists():
                raise ValidationError('You have already submitted a vote in this election.')

            # DB unique constraint is final defense against concurrent requests.
            VoterParticipation.objects.create(election=election, voter=voter)
            nonce = os.urandom(12)
            associated_data = str(election.pk).encode('ascii')
            ciphertext = cipher.encrypt(nonce, str(candidate_id).encode('ascii'), associated_data)
            EncryptedVote.objects.create(election=election, nonce=nonce, ciphertext=ciphertext)
    except IntegrityError as exc:
        raise ValidationError('Duplicate or conflicting vote submission.') from exc
    return True
