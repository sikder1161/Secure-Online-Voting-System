from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Election(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        SCHEDULED = 'SCHEDULED', 'Scheduled'
        CANCELLED = 'CANCELLED', 'Cancelled'

    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_elections')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-starts_at',)

    def clean(self):
        super().clean()
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({'ends_at': 'End time must be after start time.'})
        if self.pk:
            old = Election.objects.filter(pk=self.pk).first()
            if old and old.starts_at <= timezone.now():
                for field in ('title', 'description', 'starts_at', 'ends_at'):
                    if getattr(old, field) != getattr(self, field):
                        raise ValidationError('An election cannot be edited after its scheduled start.')

    @property
    def is_open(self):
        now = timezone.now()
        return self.status == self.Status.SCHEDULED and self.starts_at <= now < self.ends_at

    @property
    def can_edit_candidates(self):
        return self.status == self.Status.DRAFT and timezone.now() < self.starts_at

    def __str__(self):
        return self.title


class Candidate(models.Model):
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='candidates')
    name = models.CharField(max_length=150)
    information = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['election', 'name'], name='unique_candidate_name_per_election')]
        ordering = ('name',)

    def clean(self):
        super().clean()
        if self.election_id and not self.election.can_edit_candidates:
            raise ValidationError('Candidates may only be changed while election is in draft preparation.')

    def __str__(self):
        return self.name


class VoterEligibility(models.Model):
    class Decision(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='eligibilities')
    voter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='election_eligibilities')
    decision = models.CharField(max_length=10, choices=Decision.choices, default=Decision.PENDING)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='reviewed_election_eligibilities')
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['election', 'voter'], name='one_eligibility_per_voter_election')]


class VoterParticipation(models.Model):
    election = models.ForeignKey(Election, on_delete=models.PROTECT, related_name='participations')
    voter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='election_participations')
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['election', 'voter'], name='one_vote_per_voter_election')]


class EncryptedVote(models.Model):
    # Deliberately no voter ID, candidate ID or participation FK: preserve ballot separation.
    election = models.ForeignKey(Election, on_delete=models.PROTECT, related_name='encrypted_votes')
    nonce = models.BinaryField(max_length=12, unique=True)
    ciphertext = models.BinaryField()
    submitted_at = models.DateTimeField(auto_now_add=True)
